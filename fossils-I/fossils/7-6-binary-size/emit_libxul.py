#!/usr/bin/env python3
import sys
from pathlib import Path
from scripts.measure import build_libxul_table, emit

emit(build_libxul_table, Path(sys.argv[1]) / "libxul.json")
