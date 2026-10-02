#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from browser import speedometer
from execution import raptor_result

raptor_result(speedometer(sys.argv[1]))
