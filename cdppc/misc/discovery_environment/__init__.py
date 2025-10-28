"""
CDP Environment Discovery Tool

A modular Python program to discover and gather details about all resources
attached to a Cloudera Data Platform (CDP) environment.

Supports:
- Environment and FreeIPA (with recipes)
- DataLake (with recipes and runtime info)
- DataHub clusters (with recipes and runtime info)
- Kubernetes-based Data Services (CDE, CAI, CDW, CDF)
- VM-based Services (COD - Operational Database as specialized DataHub)
- Multi-cloud: AWS, Azure, GCP
"""

__version__ = "1.0.0"
__author__ = "Cloudera"

from .main import main, EnvironmentDiscoveryOrchestrator
from .common import CDPClient, DiscoveryConfig
from .modules import (
    EnvironmentDiscovery,
    DatalakeDiscovery,
    DatahubDiscovery,
    CDEDiscovery,
    CAIDiscovery,
    CDWDiscovery,
    CDFDiscovery,
    CODDiscovery
)

__all__ = [
    'main',
    'EnvironmentDiscoveryOrchestrator',
    'CDPClient',
    'DiscoveryConfig',
    'EnvironmentDiscovery',
    'DatalakeDiscovery',
    'DatahubDiscovery',
    'CDEDiscovery',
    'CAIDiscovery',
    'CDWDiscovery',
    'CDFDiscovery',
    'CODDiscovery'
]

