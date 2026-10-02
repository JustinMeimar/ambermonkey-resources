import os
from pathlib import Path
import sys


def use_project_python():
    project = Path(__file__).resolve().parents[1]
    environment = project / ".venv"
    if Path(sys.prefix) == environment:
        return
    python = environment / "bin" / "python"
    if not python.is_file():
        raise SystemExit(f"Set up figure dependencies first: uv sync --project {project}")
    os.execv(python, [str(python), *sys.argv])
