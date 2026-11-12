"""Test bootstrap: optional Google client stubs when [all] extras are not installed."""

import sys
from unittest.mock import MagicMock

if "googleapiclient.http" not in sys.modules:
    google_pkg = MagicMock()
    sys.modules.setdefault("googleapiclient", google_pkg)
    sys.modules.setdefault("googleapiclient.http", MagicMock())
    sys.modules.setdefault("googleapiclient.discovery", MagicMock())
