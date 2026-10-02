#!/usr/bin/env python3
import shutil
from pathlib import Path
import sys

shutil.copyfile(Path(__file__).resolve().parent / "source/execution-configurations.json",
                Path(sys.argv[1]) / "execution-configurations.json")
