"""Shared test configuration for TermMind tests."""

import os
import sys
from pathlib import Path

# Add the project root to sys.path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
