#!/usr/bin/env python3
import shutil
from pathlib import Path
import sys

shutil.copyfile(Path(__file__).resolve().parent / "source/runtime-dependencies.json",
                Path(sys.argv[1]) / "runtime-dependencies.json")
