#!/usr/bin/env python3
import sys
from pathlib import Path
from scripts.benchmark_table import emit

emit("jetstream3", Path(sys.argv[1]) / "jetstream3.json")
