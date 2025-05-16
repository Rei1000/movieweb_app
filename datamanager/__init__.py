

"""
datamanager package
Dieses Paket enthält die DataManager-Implementierungen.
This package contains the DataManager implementations.
"""

from .data_manager_interface import DataManagerInterface
from .sqlite_data_manager import SQLiteDataManager

__all__ = ['DataManagerInterface', 'SQLiteDataManager']