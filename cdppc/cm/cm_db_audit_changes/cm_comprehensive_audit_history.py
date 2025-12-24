#!/usr/bin/env python3
"""
Cloudera Manager Comprehensive Audit History Script

This script creates a comprehensive history of commands and configuration changes
in a Cloudera Manager by querying multiple audit and history tables
in the PostgreSQL database.

The script extends the functionality of the original script by:
- Querying multiple audit sources (configs, commands, audits, services, clusters, roles)
- Combining results into a unified chronological history
- Supporting multiple output formats (JSON, CSV, text)
- Providing detailed filtering and search capabilities
- Including proper error handling and logging
"""

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("ERROR: psycopg2 is required. Install it with: pip install psycopg2-binary")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("ERROR: tqdm is required. Install it with: pip install tqdm")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class CMDatabaseConnection:
    """
    Handles connection to Cloudera Manager PostgreSQL database.
    
    Reads database configuration from the standard CM server properties file
    and provides methods to execute queries and retrieve results.
    """
    
    def __init__(self, db_properties_file: str = "/etc/cloudera-scm-server/db.properties"):
        """
        Initialize database connection parameters.
        
        Args:
            db_properties_file: Path to the Cloudera Manager database properties file.
                              Defaults to /etc/cloudera-scm-server/db.properties
        """
        self.db_properties_file = db_properties_file
        self.connection = None
        self.db_params = {}
        
    def load_db_properties(self) -> Dict[str, str]:
        """
        Load database connection parameters from properties file.
        
        Returns:
            Dictionary containing host, database, user, and password
            
        Raises:
            FileNotFoundError: If the properties file doesn't exist
            ValueError: If required properties are missing
        """
        if not os.path.exists(self.db_properties_file):
            raise FileNotFoundError(
                f"Cannot find database properties file: {self.db_properties_file}"
            )
        
        logger.info(f"Loading database properties from {self.db_properties_file}")
        
        # Property keys may vary, try both formats
        property_keys = {
            'host': ['db.host', 'com.cloudera.cmf.db.host'],
            'database': ['db.name', 'com.cloudera.cmf.db.name'],
            'user': ['db.user', 'com.cloudera.cmf.db.user'],
            'password': ['db.password', 'com.cloudera.cmf.db.password']
        }
        
        params = {}
        with open(self.db_properties_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    for param_name, possible_keys in property_keys.items():
                        if key in possible_keys:
                            params[param_name] = value
                            break
        
        required = ['host', 'database', 'user', 'password']
        missing = [p for p in required if p not in params or not params[p]]
        if missing:
            raise ValueError(
                f"Missing required database parameters: {', '.join(missing)}"
            )
        
        self.db_params = params
        logger.info(f"Database: {params['database']} on {params['host']}")
        return params
    
    def connect(self) -> None:
        """
        Establish connection to PostgreSQL database.
        
        Raises:
            psycopg2.Error: If connection fails
        """
        if not self.db_params:
            self.load_db_properties()
        
        try:
            logger.info(f"Connecting to PostgreSQL on {self.db_params['host']}...")
            self.connection = psycopg2.connect(
                host=self.db_params['host'],
                database=self.db_params['database'],
                user=self.db_params['user'],
                password=self.db_params['password'],
                connect_timeout=10
            )
            logger.info("✅ Database connection successful")
        except psycopg2.Error as e:
            logger.error(f"❌ Failed to connect to database: {e}")
            raise
    
    def execute_query(self, query: str, params: Optional[Tuple] = None, show_progress: bool = False) -> List[Dict]:
        """
        Execute a SQL query and return results as list of dictionaries.
        
        Args:
            query: SQL query string
            params: Optional tuple of parameters for parameterized queries
            show_progress: If True, show progress bar for long-running queries
            
        Returns:
            List of dictionaries, each representing a row
            
        Raises:
            psycopg2.Error: If query execution fails
        """
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if show_progress:
                    # Execute query with progress indicator
                    with tqdm(desc="Executing query", unit="", ncols=100, leave=False, bar_format='{desc}: {elapsed}') as pbar:
                        cursor.execute(query, params)
                        pbar.set_description("Fetching results")
                        
                        # Fetch in chunks to show progress
                        results = []
                        chunk_size = 1000
                        while True:
                            chunk = cursor.fetchmany(chunk_size)
                            if not chunk:
                                break
                            results.extend([dict(row) for row in chunk])
                            pbar.update(len(chunk))
                            pbar.set_postfix(rows=len(results))
                        return results
                else:
                    cursor.execute(query, params)
                    return [dict(row) for row in cursor.fetchall()]
        except psycopg2.Error as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Query: {query[:200]}...")
            raise
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")


class CMAuditHistoryCollector:
    """
    Collects comprehensive audit history from multiple Cloudera Manager tables.
    
    Queries various audit and history tables to build a unified chronological
    view of all changes and commands in the system.
    """
    
    def __init__(self, db_connection: CMDatabaseConnection):
        """
        Initialize the audit history collector.
        
        Args:
            db_connection: CMDatabaseConnection instance for database access
        """
        self.db = db_connection
        self.excluded_users = ['cloudbreak', 'cmmgmt']
    
    def get_config_changes(self, start_time: Optional[int] = None,
                          end_time: Optional[int] = None) -> List[Dict]:
        """
        Retrieve configuration changes from configs_aud table.
        
        Args:
            start_time: Optional start timestamp (Unix epoch milliseconds)
            end_time: Optional end timestamp (Unix epoch milliseconds)
            
        Returns:
            List of configuration change records
        """
        logger.info("Querying configuration changes...")
        
        query = """
        SELECT
            u.user_id,
            u.user_name,
            r.revision_id,
            r.timestamp,
            r.message,
            ca.config_id,
            ca.revtype,
            ca.attr,
            ca.value,
            ca.service_id,
            ca.role_id,
            ca.role_config_group_id,
            ca.host_id,
            ca.config_container_id,
            ca.external_account_id,
            s.name as service_name,
            s.service_type,
            s.display_name as service_display_name,
            c.name as cluster_name,
            c.display_name as cluster_display_name,
            ro.name as role_name,
            ro.role_type,
            h.name as host_name,
            h.host_identifier
        FROM
            users u
        JOIN
            revisions r ON u.user_id = r.user_id
        JOIN
            configs_aud ca ON r.revision_id = ca.rev
        LEFT JOIN
            services s ON ca.service_id = s.service_id
        LEFT JOIN
            clusters c ON s.cluster_id = c.cluster_id
        LEFT JOIN
            roles ro ON ca.role_id = ro.role_id
        LEFT JOIN
            hosts h ON ca.host_id = h.host_id
        WHERE
            u.user_name NOT IN %s
        """
        
        params = [tuple(self.excluded_users)]
        
        if start_time:
            query += " AND r.timestamp >= %s"
            params.append(start_time)
        if end_time:
            query += " AND r.timestamp <= %s"
            params.append(end_time)
        
        query += " ORDER BY r.timestamp DESC"
        
        results = self.db.execute_query(query, tuple(params), show_progress=True)
        
        for row in results:
            row['event_type'] = 'CONFIG_CHANGE'
            row['revtype_name'] = self._get_revtype_name(row.get('revtype'))
        
        logger.info(f"Found {len(results)} configuration changes")
        return results
    
    def get_command_history(self, start_time: Optional[int] = None,
                           end_time: Optional[int] = None) -> List[Dict]:
        """
        Retrieve command execution history from commands table.
        
        Args:
            start_time: Optional start timestamp (Unix epoch milliseconds)
            end_time: Optional end timestamp (Unix epoch milliseconds)
            
        Returns:
            List of command execution records
        """
        logger.info("Querying command execution history...")
        
        query = """
        SELECT
            c.command_id,
            c.name as command_name,
            c.state,
            c.start_instant,
            c.end_instant,
            c.success,
            c.result_message,
            c.arguments,
            c.active,
            c.audited,
            c.creation_instant,
            c.first_updated_instant,
            c.intent_id,
            c.stick_with,
            c.cluster_id,
            c.service_id,
            c.role_id,
            c.host_id,
            c.schedule_id,
            c.parent_id,
            cl.name as cluster_name,
            cl.display_name as cluster_display_name,
            s.name as service_name,
            s.service_type,
            s.display_name as service_display_name,
            r.name as role_name,
            r.role_type,
            h.name as host_name,
            h.host_identifier,
            cs.display_name as schedule_name,
            parent_cmd.name as parent_command_name
        FROM
            commands c
        LEFT JOIN
            clusters cl ON c.cluster_id = cl.cluster_id
        LEFT JOIN
            services s ON c.service_id = s.service_id
        LEFT JOIN
            roles r ON c.role_id = r.role_id
        LEFT JOIN
            hosts h ON c.host_id = h.host_id
        LEFT JOIN
            command_schedules cs ON c.schedule_id = cs.spec_id
        LEFT JOIN
            commands parent_cmd ON c.parent_id = parent_cmd.command_id
        WHERE
            1=1
        """
        
        params = []
        if start_time:
            query += " AND (c.start_instant >= %s OR c.creation_instant >= %s)"
            params.extend([start_time, start_time])
        if end_time:
            query += " AND (c.start_instant <= %s OR c.creation_instant <= %s)"
            params.extend([end_time, end_time])
        
        query += " ORDER BY COALESCE(c.start_instant, c.creation_instant) DESC"
        
        results = self.db.execute_query(query, tuple(params) if params else None, show_progress=True)
        
        for row in results:
            row['event_type'] = 'COMMAND_EXECUTION'
            if row.get('start_instant') and row.get('end_instant'):
                row['duration_ms'] = row['end_instant'] - row['start_instant']
            else:
                row['duration_ms'] = None
        
        logger.info(f"Found {len(results)} command executions")
        return results
    
    def get_audit_logs(self, start_time: Optional[int] = None,
                      end_time: Optional[int] = None) -> List[Dict]:
        """
        Retrieve audit logs from audits table.
        
        Args:
            start_time: Optional start timestamp (Unix epoch milliseconds)
            end_time: Optional end timestamp (Unix epoch milliseconds)
            
        Returns:
            List of audit log records
        """
        logger.info("Querying audit logs...")
        
        query = """
        SELECT
            a.audit_id,
            a.audit_type,
            a.created_instant,
            a.message,
            a.allowed,
            a.ip_address,
            a.acting_user_id,
            a.user_id,
            a.command_id,
            a.cluster_id,
            a.service_id,
            a.role_id,
            a.host_id,
            a.host_template_id,
            a.config_container_id,
            a.external_account_id,
            acting_u.user_name as acting_user_name,
            target_u.user_name as target_user_name,
            cl.name as cluster_name,
            cl.display_name as cluster_display_name,
            s.name as service_name,
            s.service_type,
            s.display_name as service_display_name,
            r.name as role_name,
            r.role_type,
            h.name as host_name,
            h.host_identifier
        FROM
            audits a
        LEFT JOIN
            users acting_u ON a.acting_user_id = acting_u.user_id
        LEFT JOIN
            users target_u ON a.user_id = target_u.user_id
        LEFT JOIN
            clusters cl ON a.cluster_id = cl.cluster_id
        LEFT JOIN
            services s ON a.service_id = s.service_id
        LEFT JOIN
            roles r ON a.role_id = r.role_id
        LEFT JOIN
            hosts h ON a.host_id = h.host_id
        WHERE
            (acting_u.user_name NOT IN %s OR acting_u.user_name IS NULL)
            AND (target_u.user_name NOT IN %s OR target_u.user_name IS NULL)
        """
        
        params = [tuple(self.excluded_users), tuple(self.excluded_users)]
        
        if start_time:
            query += " AND a.created_instant >= %s"
            params.append(start_time)
        if end_time:
            query += " AND a.created_instant <= %s"
            params.append(end_time)
        
        query += " ORDER BY a.created_instant DESC"
        
        results = self.db.execute_query(query, tuple(params), show_progress=True)
        
        for row in results:
            row['event_type'] = 'AUDIT_LOG'
        
        logger.info(f"Found {len(results)} audit log entries")
        return results
    
    def get_service_changes(self, start_time: Optional[int] = None,
                          end_time: Optional[int] = None) -> List[Dict]:
        """
        Retrieve service changes from services_aud table.
        
        Args:
            start_time: Optional start timestamp (Unix epoch milliseconds)
            end_time: Optional end timestamp (Unix epoch milliseconds)
            
        Returns:
            List of service change records
        """
        logger.info("Querying service changes...")
        
        query = """
        SELECT
            r.revision_id,
            r.timestamp,
            r.message,
            r.user_id,
            u.user_name,
            sa.service_id,
            sa.revtype,
            sa.name,
            sa.service_type,
            sa.cluster_id,
            sa.display_name,
            cl.name as cluster_name,
            cl.display_name as cluster_display_name
        FROM
            services_aud sa
        JOIN
            revisions r ON sa.rev = r.revision_id
        LEFT JOIN
            users u ON r.user_id = u.user_id
        LEFT JOIN
            clusters cl ON sa.cluster_id = cl.cluster_id
        WHERE
            (u.user_name NOT IN %s OR u.user_name IS NULL)
        """
        
        params = [tuple(self.excluded_users)]
        
        if start_time:
            query += " AND r.timestamp >= %s"
            params.append(start_time)
        if end_time:
            query += " AND r.timestamp <= %s"
            params.append(end_time)
        
        query += " ORDER BY r.timestamp DESC"
        
        results = self.db.execute_query(query, tuple(params), show_progress=True)
        
        for row in results:
            row['event_type'] = 'SERVICE_CHANGE'
            row['revtype_name'] = self._get_revtype_name(row.get('revtype'))
        
        logger.info(f"Found {len(results)} service changes")
        return results
    
    def get_cluster_changes(self, start_time: Optional[int] = None,
                           end_time: Optional[int] = None) -> List[Dict]:
        """
        Retrieve cluster changes from clusters_aud table.
        
        Args:
            start_time: Optional start timestamp (Unix epoch milliseconds)
            end_time: Optional end timestamp (Unix epoch milliseconds)
            
        Returns:
            List of cluster change records
        """
        logger.info("Querying cluster changes...")
        
        query = """
        SELECT
            r.revision_id,
            r.timestamp,
            r.message,
            r.user_id,
            u.user_name,
            ca.cluster_id,
            ca.revtype,
            ca.name,
            ca.cdh_version,
            ca.display_name
        FROM
            clusters_aud ca
        JOIN
            revisions r ON ca.rev = r.revision_id
        LEFT JOIN
            users u ON r.user_id = u.user_id
        WHERE
            (u.user_name NOT IN %s OR u.user_name IS NULL)
        """
        
        params = [tuple(self.excluded_users)]
        
        if start_time:
            query += " AND r.timestamp >= %s"
            params.append(start_time)
        if end_time:
            query += " AND r.timestamp <= %s"
            params.append(end_time)
        
        query += " ORDER BY r.timestamp DESC"
        
        results = self.db.execute_query(query, tuple(params), show_progress=True)
        
        for row in results:
            row['event_type'] = 'CLUSTER_CHANGE'
            row['revtype_name'] = self._get_revtype_name(row.get('revtype'))
        
        logger.info(f"Found {len(results)} cluster changes")
        return results
    
    def get_role_changes(self, start_time: Optional[int] = None,
                        end_time: Optional[int] = None) -> List[Dict]:
        """
        Retrieve role changes from roles_aud table.
        
        Args:
            start_time: Optional start timestamp (Unix epoch milliseconds)
            end_time: Optional end timestamp (Unix epoch milliseconds)
            
        Returns:
            List of role change records
        """
        logger.info("Querying role changes...")
        
        query = """
        SELECT
            r.revision_id,
            r.timestamp,
            r.message,
            r.user_id,
            u.user_name,
            ra.role_id,
            ra.revtype,
            ra.name,
            ra.role_type,
            ra.host_id,
            ra.service_id,
            ra.role_config_group_id,
            s.name as service_name,
            s.service_type,
            s.display_name as service_display_name,
            cl.name as cluster_name,
            cl.display_name as cluster_display_name,
            h.name as host_name,
            h.host_identifier
        FROM
            roles_aud ra
        JOIN
            revisions r ON ra.rev = r.revision_id
        LEFT JOIN
            users u ON r.user_id = u.user_id
        LEFT JOIN
            services s ON ra.service_id = s.service_id
        LEFT JOIN
            clusters cl ON s.cluster_id = cl.cluster_id
        LEFT JOIN
            hosts h ON ra.host_id = h.host_id
        WHERE
            (u.user_name NOT IN %s OR u.user_name IS NULL)
        """
        
        params = [tuple(self.excluded_users)]
        
        if start_time:
            query += " AND r.timestamp >= %s"
            params.append(start_time)
        if end_time:
            query += " AND r.timestamp <= %s"
            params.append(end_time)
        
        query += " ORDER BY r.timestamp DESC"
        
        results = self.db.execute_query(query, tuple(params), show_progress=True)
        
        for row in results:
            row['event_type'] = 'ROLE_CHANGE'
            row['revtype_name'] = self._get_revtype_name(row.get('revtype'))
        
        logger.info(f"Found {len(results)} role changes")
        return results
    
    def collect_all_history(self, start_time: Optional[int] = None,
                           end_time: Optional[int] = None,
                           sources: Optional[List[str]] = None) -> List[Dict]:
        """
        Collect audit history from specified sources and combine into unified list.
        
        Args:
            start_time: Optional start timestamp (Unix epoch milliseconds)
            end_time: Optional end timestamp (Unix epoch milliseconds)
            sources: Optional list of source names to include. If None, includes all sources.
                    Valid values: 'configs', 'commands', 'audits', 'services', 'clusters', 'roles'
            
        Returns:
            Combined list of all history records, sorted chronologically
        """
        logger.info("Collecting comprehensive audit history...")
        
        all_history = []
        
        # Define all available query methods with their source identifiers
        all_query_methods = {
            'configs': ("Configuration Changes", self.get_config_changes),
            'commands': ("Command Executions", self.get_command_history),
            'audits': ("Audit Logs", self.get_audit_logs),
            'services': ("Service Changes", self.get_service_changes),
            'clusters': ("Cluster Changes", self.get_cluster_changes),
            'roles': ("Role Changes", self.get_role_changes),
        }
        
        # Determine which sources to query
        if sources is None:
            # Default: query all sources
            sources_to_query = list(all_query_methods.keys())
        else:
            # Validate and filter sources
            valid_sources = set(all_query_methods.keys())
            requested_sources = set(s.lower() for s in sources)
            invalid_sources = requested_sources - valid_sources
            if invalid_sources:
                raise ValueError(f"Invalid source(s): {', '.join(invalid_sources)}. "
                               f"Valid sources are: {', '.join(sorted(valid_sources))}")
            sources_to_query = [s for s in all_query_methods.keys() if s in requested_sources]
        
        if not sources_to_query:
            raise ValueError("At least one source must be specified")
        
        # Build list of query methods to execute
        query_methods = [(all_query_methods[src][0], all_query_methods[src][1]) 
                        for src in sources_to_query]
        
        logger.info(f"Querying {len(query_methods)} source(s): {', '.join([desc for desc, _ in query_methods])}")
        
        # Collect history with progress bar
        with tqdm(total=len(query_methods), desc="Collecting history", unit="source", ncols=100) as pbar:
            for desc, method in query_methods:
                pbar.set_description(f"Querying {desc}")
                try:
                    results = method(start_time, end_time)
                    all_history.extend(results)
                    pbar.set_postfix(records=len(results))
                except Exception as e:
                    logger.error(f"Error querying {desc}: {e}")
                    pbar.set_postfix(error=str(e)[:30])
                finally:
                    pbar.update(1)
        
        # Normalize timestamps for sorting
        for record in all_history:
            # Determine the timestamp field based on event type
            if record['event_type'] == 'CONFIG_CHANGE':
                record['_sort_timestamp'] = record.get('timestamp', 0)
            elif record['event_type'] == 'COMMAND_EXECUTION':
                record['_sort_timestamp'] = record.get('start_instant') or record.get('creation_instant', 0)
            elif record['event_type'] == 'AUDIT_LOG':
                record['_sort_timestamp'] = record.get('created_instant', 0)
            elif record['event_type'] in ['SERVICE_CHANGE', 'CLUSTER_CHANGE', 'ROLE_CHANGE']:
                record['_sort_timestamp'] = record.get('timestamp', 0)
            else:
                record['_sort_timestamp'] = 0
        
        all_history.sort(key=lambda x: x.get('_sort_timestamp', 0), reverse=True)
        
        logger.info(f"Total history records collected: {len(all_history)}")
        return all_history
    
    @staticmethod
    def _get_revtype_name(revtype: Optional[int]) -> str:
        """
        Convert revision type code to human-readable name.
        
        Args:
            revtype: Revision type code (0=ADD, 1=MOD, 2=DEL)
            
        Returns:
            Human-readable revision type name
        """
        revtype_map = {0: 'ADD', 1: 'MODIFY', 2: 'DELETE'}
        return revtype_map.get(revtype, 'UNKNOWN')


class HistoryExporter:
    """
    Exports audit history to various formats (JSON, CSV, text).
    """
    
    @staticmethod
    def export_json(history: List[Dict], output_file: str) -> None:
        """
        Export history to JSON format.
        
        Args:
            history: List of history records
            output_file: Path to output file
        """
        logger.info(f"Exporting to JSON: {output_file}")
        
        export_data = []
        for record in history:
            export_record = record.copy()
            export_record.pop('_sort_timestamp', None)
            for key in ['timestamp', 'start_instant', 'end_instant', 'created_instant', 'creation_instant']:
                if key in export_record and export_record[key]:
                    export_record[f'{key}_iso'] = datetime.fromtimestamp(
                        export_record[key] / 1000
                    ).isoformat()
            export_data.append(export_record)
        
        with open(output_file, 'w') as f:
            json.dump({
                'export_timestamp': datetime.now().isoformat(),
                'total_records': len(export_data),
                'history': export_data
            }, f, indent=2, default=str)
        
        logger.info(f"✅ Exported {len(export_data)} records to JSON")
    
    @staticmethod
    def export_csv(history: List[Dict], output_file: str) -> None:
        """
        Export history to CSV format.
        
        Args:
            history: List of history records
            output_file: Path to output file
        """
        logger.info(f"Exporting to CSV: {output_file}")
        
        if not history:
            logger.warning("No history to export")
            return
        
        all_keys = set()
        for record in history:
            all_keys.update(record.keys())
        
        all_keys.discard('_sort_timestamp')
        fieldnames = sorted(all_keys)
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            for record in history:
                record_copy = {k: v for k, v in record.items() if k != '_sort_timestamp'}
                for key in ['timestamp', 'start_instant', 'end_instant', 'created_instant', 'creation_instant']:
                    if key in record_copy and record_copy[key]:
                        try:
                            record_copy[f'{key}_iso'] = datetime.fromtimestamp(
                                record_copy[key] / 1000
                            ).isoformat()
                        except (ValueError, OSError):
                            pass
                writer.writerow(record_copy)
        
        logger.info(f"✅ Exported {len(history)} records to CSV")
    
    @staticmethod
    def export_text(history: List[Dict], output_file: str) -> None:
        """
        Export history to human-readable text format.
        
        Args:
            history: List of history records
            output_file: Path to output file
        """
        logger.info(f"Exporting to text: {output_file}")
        
        with open(output_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("Cloudera Manager Comprehensive Audit History\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Records: {len(history)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, record in enumerate(history, 1):
                f.write(f"\n--- Record {i} ---\n")
                f.write(f"Event Type: {record.get('event_type', 'UNKNOWN')}\n")
                
                timestamp = (record.get('timestamp') or 
                           record.get('start_instant') or 
                           record.get('created_instant') or 
                           record.get('creation_instant'))
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    f.write(f"Timestamp: {dt.strftime('%Y-%m-%d %H:%M:%S')} ({timestamp})\n")
                
                if record['event_type'] == 'CONFIG_CHANGE':
                    f.write(f"User: {record.get('user_name', 'N/A')}\n")
                    f.write(f"Attribute: {record.get('attr', 'N/A')}\n")
                    f.write(f"Value: {str(record.get('value', 'N/A'))[:100]}\n")
                    f.write(f"Change Type: {record.get('revtype_name', 'N/A')}\n")
                    if record.get('service_name'):
                        f.write(f"Service: {record.get('service_display_name', record.get('service_name'))}\n")
                    if record.get('cluster_name'):
                        f.write(f"Cluster: {record.get('cluster_display_name', record.get('cluster_name'))}\n")
                    if record.get('role_name'):
                        f.write(f"Role: {record.get('role_name')} ({record.get('role_type', 'N/A')})\n")
                    if record.get('message'):
                        f.write(f"Message: {record.get('message')}\n")
                
                elif record['event_type'] == 'COMMAND_EXECUTION':
                    f.write(f"Command: {record.get('command_name', 'N/A')}\n")
                    f.write(f"State: {record.get('state', 'N/A')}\n")
                    f.write(f"Success: {record.get('success', 'N/A')}\n")
                    if record.get('duration_ms'):
                        f.write(f"Duration: {record.get('duration_ms') / 1000:.2f} seconds\n")
                    if record.get('service_name'):
                        f.write(f"Service: {record.get('service_display_name', record.get('service_name'))}\n")
                    if record.get('cluster_name'):
                        f.write(f"Cluster: {record.get('cluster_display_name', record.get('cluster_name'))}\n")
                    if record.get('result_message'):
                        f.write(f"Result: {record.get('result_message')[:200]}\n")
                
                elif record['event_type'] == 'AUDIT_LOG':
                    f.write(f"Audit Type: {record.get('audit_type', 'N/A')}\n")
                    f.write(f"Acting User: {record.get('acting_user_name', 'N/A')}\n")
                    f.write(f"Allowed: {record.get('allowed', 'N/A')}\n")
                    f.write(f"IP Address: {record.get('ip_address', 'N/A')}\n")
                    if record.get('message'):
                        f.write(f"Message: {record.get('message')[:200]}\n")
                
                elif record['event_type'] in ['SERVICE_CHANGE', 'CLUSTER_CHANGE', 'ROLE_CHANGE']:
                    f.write(f"User: {record.get('user_name', 'N/A')}\n")
                    f.write(f"Change Type: {record.get('revtype_name', 'N/A')}\n")
                    if record.get('message'):
                        f.write(f"Message: {record.get('message')}\n")
                    if record['event_type'] == 'SERVICE_CHANGE':
                        f.write(f"Service: {record.get('display_name', record.get('name', 'N/A'))}\n")
                        f.write(f"Service Type: {record.get('service_type', 'N/A')}\n")
                    elif record['event_type'] == 'CLUSTER_CHANGE':
                        f.write(f"Cluster: {record.get('display_name', record.get('name', 'N/A'))}\n")
                        f.write(f"CDH Version: {record.get('cdh_version', 'N/A')}\n")
                    elif record['event_type'] == 'ROLE_CHANGE':
                        f.write(f"Role: {record.get('name', 'N/A')} ({record.get('role_type', 'N/A')})\n")
                
                f.write("\n")
        
        logger.info(f"✅ Exported {len(history)} records to text format")


def parse_timestamp(timestamp_str: str) -> int:
    """
    Parse timestamp string to Unix epoch milliseconds.
    
    Supports formats:
    - ISO format: 2025-12-15T10:30:00
    - Unix timestamp (seconds): 1734262200
    - Unix timestamp (milliseconds): 1734262200000
    
    Args:
        timestamp_str: Timestamp string to parse
        
    Returns:
        Unix epoch milliseconds
    """
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return int(dt.timestamp() * 1000)
    except ValueError:
        try:
            ts = float(timestamp_str)
            if ts < 946684800:
                return int(ts)
            else:
                return int(ts * 1000)
        except ValueError:
            raise ValueError(f"Invalid timestamp format: {timestamp_str}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Comprehensive Cloudera Manager audit history collector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all history to JSON (default output directory: /tmp)
  %(prog)s --format json
  
  # Export to custom directory with timestamped subdirectory
  %(prog)s --format json --dir /var/tmp/cm_reports
  
  # Export last 7 days to CSV
  %(prog)s --format csv --days 7 --dir /tmp
  
  # Export specific time range to text
  %(prog)s --format text --start "2025-12-01T00:00:00" --end "2025-12-15T23:59:59" --dir /tmp
  
  # Export all formats
  %(prog)s --format all --dir /tmp
  
  # Export only configuration changes (automatically exports to JSON and CSV)
  %(prog)s --changes --dir /tmp
  
  # Export configuration changes for last 30 days to custom directory
  %(prog)s --changes --days 30 --dir /var/tmp/audit_reports
  
  # Query only specific audit sources
  %(prog)s --sources configs commands --dir /tmp
  
  # Query only configuration and audit log sources
  %(prog)s --sources configs audits --days 7 --dir /tmp
        """
    )
    
    parser.add_argument(
        '--db-properties',
        default='/etc/cloudera-scm-server/db.properties',
        help='Path to Cloudera Manager database properties file (default: %(default)s)'
    )
    
    parser.add_argument(
        '--dir',
        default='/tmp',
        help='Output directory for reports (default: %(default)s). A timestamped subdirectory will be created.'
    )
    
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output file base name (default: auto-generated with timestamp). Files will be created in the timestamped directory.'
    )
    
    parser.add_argument(
        '--format',
        choices=['json', 'csv', 'text', 'all'],
        default='json',
        help='Output format (default: %(default)s)'
    )
    
    parser.add_argument(
        '--start',
        type=str,
        default=None,
        help='Start timestamp (ISO format or Unix timestamp)'
    )
    
    parser.add_argument(
        '--end',
        type=str,
        default=None,
        help='End timestamp (ISO format or Unix timestamp)'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Number of days to look back from now'
    )
    
    parser.add_argument(
        '--exclude-users',
        nargs='+',
        default=['cloudbreak', 'cmmgmt'],
        help='User names to exclude from results (default: cloudbreak cmmgmt)'
    )
    
    parser.add_argument(
        '--sources',
        nargs='+',
        choices=['configs', 'commands', 'audits', 'services', 'clusters', 'roles', 'all'],
        default=['all'],
        help='Audit sources to include in the report. Can specify multiple sources. '
             'Valid values: configs, commands, audits, services, clusters, roles, all '
             '(default: all). '
             'Examples: --sources configs commands, --sources configs audits services'
    )
    
    parser.add_argument(
        '--changes',
        action='store_true',
        help='Filter to show only configuration changes (CONFIG_CHANGE events). '
             'When used, automatically exports to both JSON and CSV formats.'
    )
    
    args = parser.parse_args()
    
    start_time = None
    end_time = None
    
    if args.days:
        from datetime import timedelta
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=args.days)).timestamp() * 1000)
        logger.info(f"Time range: last {args.days} days")
    else:
        if args.start:
            start_time = parse_timestamp(args.start)
            logger.info(f"Start time: {datetime.fromtimestamp(start_time / 1000).isoformat()}")
        if args.end:
            end_time = parse_timestamp(args.end)
            logger.info(f"End time: {datetime.fromtimestamp(end_time / 1000).isoformat()}")
    
    # Create timestamped output directory
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    output_dir = os.path.join(args.dir, f"cm_audit_{timestamp}")
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Output directory: {output_dir}")
    except OSError as e:
        logger.error(f"Failed to create output directory '{output_dir}': {e}")
        sys.exit(1)
    
    # Generate output file base name if not provided
    if not args.output:
        hostname = os.uname().nodename if hasattr(os, 'uname') else 'localhost'
        if args.changes:
            args.output = os.path.join(output_dir, f"CM_config_changes_{hostname}_{timestamp}")
        else:
            args.output = os.path.join(output_dir, f"CM_comprehensive_audit_{hostname}_{timestamp}")
    else:
        # If output is provided, ensure it's in the timestamped directory
        base_name = os.path.basename(args.output)
        args.output = os.path.join(output_dir, base_name)
    
    try:
        db = CMDatabaseConnection(args.db_properties)
        db.load_db_properties()
        db.connect()
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        sys.exit(1)
    
    try:
        collector = CMAuditHistoryCollector(db)
        collector.excluded_users = args.exclude_users
        
        # Process --sources argument
        sources_to_query = None
        if 'all' not in args.sources:
            sources_to_query = args.sources
        
        history = collector.collect_all_history(start_time, end_time, sources=sources_to_query)
        
        if not history:
            logger.warning("No history records found")
            sys.exit(0)
        
        # Filter to only CONFIG_CHANGE events if --changes flag is set
        if args.changes:
            original_count = len(history)
            history = [record for record in history if record.get('event_type') == 'CONFIG_CHANGE']
            filtered_count = len(history)
            logger.info(f"Filtered to configuration changes: {filtered_count} of {original_count} total records")
            
            if not history:
                logger.warning("No configuration change records found")
                sys.exit(0)
            
            # When --changes is used, automatically export to both JSON and CSV
            logger.info("Exporting configuration changes to JSON and CSV formats...")
            HistoryExporter.export_json(history, f"{args.output}.json")
            HistoryExporter.export_csv(history, f"{args.output}.csv")
            logger.info(f"✅ Configuration changes exported to:")
            logger.info(f"   - JSON: {args.output}.json")
            logger.info(f"   - CSV: {args.output}.csv")
            logger.info(f"   - Output directory: {output_dir}")
        else:
            if args.format == 'json' or args.format == 'all':
                HistoryExporter.export_json(history, f"{args.output}.json")
            
            if args.format == 'csv' or args.format == 'all':
                HistoryExporter.export_csv(history, f"{args.output}.csv")
            
            if args.format == 'text' or args.format == 'all':
                HistoryExporter.export_text(history, f"{args.output}.txt")
            
            logger.info("✅ Audit history collection completed successfully")
            logger.info(f"   - Output directory: {output_dir}")
        
    except Exception as e:
        logger.error(f"Error during history collection: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()

