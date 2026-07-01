#!/usr/bin/env python3
"""Launch PyBrowser: `python main.py [url ...]`."""

import sys

from browser.app import main

if __name__ == "__main__":
    sys.exit(main())
