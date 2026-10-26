#!/usr/bin/env python3
import sys
from pathlib import Path
from scripts.measure import build_image_table, emit

emit(build_image_table, Path(sys.argv[1]) / 'image.json')
