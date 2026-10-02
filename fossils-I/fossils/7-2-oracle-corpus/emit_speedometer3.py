#!/usr/bin/env python3
import sys
from pathlib import Path
from scripts.benchmark_table import emit

emit("speedometer3", Path(sys.argv[1]) / "speedometer3.json")
