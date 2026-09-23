"""Test package initialization for Abby test suite.

Ensures the 'src' directory is automatically on sys.path, enabling zero-configuration
test execution with standard unittest discovery from any working directory:
    python3 -m unittest discover tests
"""

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

SRC_DIR = PACKAGE_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
