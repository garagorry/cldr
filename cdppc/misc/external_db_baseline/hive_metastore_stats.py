#!/usr/bin/env python3

import subprocess
import psycopg2
import json
from datetime import datetime
import argparse
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def get_connection_params():
    sls_file = '/srv/pillar/postgresql/postgre.sls'

    def jq_query(query):
        result = subprocess.run(
            f"sed -n '2,$p' {sls_file} | jq -r '{query}'",
            shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            logging.error(f"Failed to extract parameter: {query}")
            logging.error(result.stderr.strip())
            sys.exit(1)
        return result.stdout.strip()

    return {
        'password': jq_query('.[].hive.remote_admin_pw'),
        'database': jq_query('.[].hive.database'),
        'user': jq_query('.[].hive.remote_admin'),
        'port': jq_query('.[].hive.remote_db_port'),
        'host': jq_query('.[].hive.remote_db_url')
    }

QUERIES = {
    "partitions_per_table": '''
        SELECT "DBS"."NAME" AS db_name, "TBLS"."TBL_NAME" AS table_name, COUNT(*) AS number_of_partitions
        FROM "PARTITIONS"
        JOIN "TBLS" ON "TBLS"."TBL_ID" = "PARTITIONS"."TBL_ID"
        JOIN "DBS" ON "DBS"."DB_ID" = "TBLS"."DB_ID"
        GROUP BY "DBS"."NAME", "TBLS"."TBL_NAME"
        ORDER BY number_of_partitions DESC;
    ''',
    "tables_per_database": '''
        SELECT "DBS"."NAME" AS db_name, COUNT(*) AS number_of_tables
        FROM "DBS"
        JOIN "TBLS" ON "DBS"."DB_ID" = "TBLS"."DB_ID"
        GROUP BY "DBS"."NAME"
        ORDER BY number_of_tables DESC;
    ''',
    "total_tables": '''
        SELECT COUNT(*) AS total_tables
        FROM "DBS"
        JOIN "TBLS" ON "DBS"."DB_ID" = "TBLS"."DB_ID";
    ''',
    "tables_by_database": '''
        SELECT "DBS"."NAME" AS db_name, COUNT(*) AS number_of_tables
        FROM "DBS"
        JOIN "TBLS" ON "DBS"."DB_ID" = "TBLS"."DB_ID"
        GROUP BY "DBS"."NAME"
        ORDER BY number_of_tables DESC;
    ''',
    "partitioned_tables": '''
        SELECT COUNT(DISTINCT("TBL_ID")) AS total_partitioned_tables
        FROM "PARTITIONS";
    ''',
    "external_tables": '''
        SELECT COUNT("TBLS"."TBL_NAME") AS external_table_count
        FROM "TBLS"
        WHERE "TBLS"."TBL_TYPE" = 'EXTERNAL_TABLE';
    ''',
    "managed_tables": '''
        SELECT COUNT("TBLS"."TBL_NAME") AS managed_table_count
        FROM "TBLS"
        WHERE "TBLS"."TBL_TYPE" = 'MANAGED_TABLE';
    ''',
    "total_views": '''
        SELECT COUNT("TBLS"."TBL_NAME") AS total_views
        FROM "TBLS"
        WHERE "TBLS"."TBL_TYPE" = 'VIRTUAL_VIEW';
    '''
}

def run_queries(params):
    results = {}
    try:
        conn = psycopg2.connect(
            dbname=params['database'],
            user=params['user'],
            password=params['password'],
            host=params['host'],
            port=params['port']
        )
    except Exception as e:
        logging.error("Failed to connect to PostgreSQL")
        logging.error(str(e))
        sys.exit(1)

    with conn:
        with conn.cursor() as cur:
            for name, query in QUERIES.items():
                logging.info(f"Running query: {name}")
                cur.execute(query)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                results[name] = [dict(zip(columns, row)) for row in rows]

    conn.close()
    return results

def main():
    parser = argparse.ArgumentParser(description='Run Hive Metastore statistics queries on PostgreSQL and save results as JSON.')
    parser.add_argument(
        '-o', '--output', type=str,
        help='Path to output JSON file. Defaults to ./hive_stats_<timestamp>.json'
    )
    args = parser.parse_args()

    params = get_connection_params()
    results = run_queries(params)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = args.output or f'hive_stats_{timestamp}.json'

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    logging.info(f"Results saved to {output_file}")

if __name__ == "__main__":
    main()
