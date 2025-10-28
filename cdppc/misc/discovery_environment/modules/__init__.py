"""Discovery modules for CDP services."""

from .environment import EnvironmentDiscovery
from .datalake import DatalakeDiscovery
from .datahub import DatahubDiscovery
from .cde import CDEDiscovery
from .cai import CAIDiscovery
from .cdw import CDWDiscovery
from .cdf import CDFDiscovery
from .cod import CODDiscovery

__all__ = [
    'EnvironmentDiscovery',
    'DatalakeDiscovery',
    'DatahubDiscovery',
    'CDEDiscovery',
    'CAIDiscovery',
    'CDWDiscovery',
    'CDFDiscovery',
    'CODDiscovery'
]

