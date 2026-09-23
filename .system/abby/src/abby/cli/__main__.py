"""Module execution entrypoint for python -m abby.cli."""

from __future__ import annotations

import sys
from abby.cli.handlers import main

if __name__ == "__main__":
    sys.exit(main())

