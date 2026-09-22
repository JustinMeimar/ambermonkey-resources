#!/usr/bin/env python3

import os
from pathlib import Path
import sys

from mozbuild.base import MozbuildObject
from mozharness.mozilla.testing.raptor import Raptor


def main():
    firefox = Path(os.environ.get("AMBERMONKEY_FIREFOX", "/workspace/firefox"))
    objdir = Path(MozbuildObject.from_environment(cwd=str(firefox)).topobjdir)
    (objdir / "testing").mkdir(parents=True, exist_ok=True)
    config = {
        "run_local": True,
        "repo_path": str(firefox),
        "raptor_path": str(firefox / "testing/raptor"),
        "obj_path": str(objdir),
        "base_work_dir": str(firefox / "testing/mozharness"),
        "virtualenv_path": str(objdir / "testing/raptor-venv"),
        "mozbuild_path": os.environ.get("MOZBUILD_STATE_PATH", str(Path.home() / ".mozbuild")),
        "exes": {"python": sys.executable},
        "raptor_cmd_line_args": ["--app", "firefox"],
        "log_name": "raptor-setup",
        "pip_index": True,
    }
    # Use the pinned harness's dependency list without launching a browser.
    harness = Raptor(
        config=config,
        option_args=[],
        default_actions=["populate-webroot", "create-virtualenv"],
    )
    raise SystemExit(harness.run())


if __name__ == "__main__":
    main()
