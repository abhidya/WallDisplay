import os
import shutil
import stat
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_run_direct_rejects_foreign_health_listener(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / "web" / "backend").mkdir(parents=True)
    (project_root / "web" / "frontend").mkdir(parents=True)
    (project_root / "scripts").mkdir()

    for relative_path in ("web/run_direct.sh", "web/stop_direct.sh", "scripts/common_env.sh"):
        source_path = ROOT_DIR / relative_path
        destination_path = project_root / relative_path
        destination_path.write_text(source_path.read_text())
        destination_path.chmod(source_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (project_root / "web" / "backend" / "requirements.txt").write_text("")
    (project_root / "web" / "backend" / "main.py").write_text("app = object()\n")

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_state_dir = tmp_path / "state"
    fake_state_dir.mkdir()
    fake_logs_dir = tmp_path / "logs"
    fake_logs_dir.mkdir()
    fake_venv_dir = tmp_path / "venv"
    fake_venv_dir.mkdir()

    fake_python = fake_bin / "fake-python"
    _write_executable(
        fake_python,
        """#!/bin/bash
set -e

if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
    exit 0
fi

if [ "$1" = "-c" ]; then
    exit 0
fi

if [ "$1" = "run.py" ]; then
    touch "$FAKE_STATE_DIR/backend_started"
    exec python3 -c "import time; time.sleep(30)"
fi

exit 0
""",
    )

    _write_executable(
        fake_bin / "lsof",
        """#!/bin/bash
if [[ "$*" == *"8000"* ]] && [ -f "$FAKE_STATE_DIR/backend_started" ]; then
    echo "4242"
fi
""",
    )

    _write_executable(
        fake_bin / "curl",
        """#!/bin/bash
if [[ "$*" == *"/health"* ]] && [ -f "$FAKE_STATE_DIR/backend_started" ]; then
    exit 0
fi
exit 1
""",
    )

    _write_executable(
        fake_bin / "pkill",
        """#!/bin/bash
exit 0
""",
    )

    _write_executable(
        fake_bin / "pgrep",
        """#!/bin/bash
exit 1
""",
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:{env['PATH']}",
            "FAKE_STATE_DIR": str(fake_state_dir),
            "NANODLNA_ROOT_DIR": str(project_root),
            "NANODLNA_FRONTEND_ENABLED": "0",
            "NANODLNA_INSTALL_PLAYWRIGHT": "0",
            "NANODLNA_PYTHON_BIN": str(fake_python),
            "NANODLNA_VENV_DIR": str(fake_venv_dir),
            "NANODLNA_LOG_DIR": str(fake_logs_dir),
            "NANODLNA_BACKEND_START_TIMEOUT": "3",
            "NANODLNA_PORT_RELEASE_TIMEOUT": "1",
        }
    )

    completed = subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(project_root / "web" / "run_direct.sh")],
        cwd=project_root / "web",
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )

    combined_output = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode != 0
    assert "owned by PID 4242 instead of the launched backend PID" in combined_output
    assert "Backend is running." not in combined_output
