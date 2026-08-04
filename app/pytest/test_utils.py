import os
import shutil
import subprocess

from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[2] / "utils.sh"


def write_command(directory: Path, name: str, body: str):
    command = directory / name
    command.write_text(f"#!/bin/sh\nset -eu\n{body}\n")
    command.chmod(0o755)


def run_utils(tmp_path: Path, commands: dict[str, str]):
    shutil.copy2(SCRIPT_PATH, tmp_path / "utils.sh")
    (tmp_path / ".env").touch()

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_command(bin_dir, "git", 'echo "test-version"')
    write_command(bin_dir, "docker", "exit 0")
    for name, body in commands.items():
        write_command(bin_dir, name, body)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    return subprocess.run(
        [tmp_path / "utils.sh", "noop"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_utils_detects_linux_ip(tmp_path):
    result = run_utils(
        tmp_path,
        {
            "ip": 'echo "1.1.1.1 via 192.0.2.1 dev eth0 src 192.0.2.10 uid 1000"',
        },
    )

    assert result.returncode == 0
    assert "WAS Web UI URL is http://192.0.2.10:8502" in result.stdout
