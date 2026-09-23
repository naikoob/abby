"""Module execution entrypoint for python -m abby."""

import sys
from abby.cli import main

if __name__ == "__main__":
    sys.exit(main())
