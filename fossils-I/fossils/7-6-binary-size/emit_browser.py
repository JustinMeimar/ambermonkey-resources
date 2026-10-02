#!/usr/bin/env python3
import sys
from pathlib import Path
from scripts.measure import build_browser_table, emit

emit(build_browser_table, Path(sys.argv[1]) / "browser.json")
