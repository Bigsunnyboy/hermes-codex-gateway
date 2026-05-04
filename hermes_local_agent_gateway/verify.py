from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path


def run_verify_commands(
    *,
    execution_path: Path,
    artifact_dir: Path,
    commands: list[str],
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for index, command in enumerate(commands, start=1):
        argv = _verify_argv(command)
        stdout_path = artifact_dir / f"verify_{index}_stdout.log"
        stderr_path = artifact_dir / f"verify_{index}_stderr.log"
        completed = subprocess.run(
            argv,
            cwd=execution_path,
            text=True,
            capture_output=True,
            check=False,
        )
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            }
        )
    (artifact_dir / "verify_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return results


def _verify_argv(command: str) -> list[str]:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("Empty verification command.")

    executable = argv[0]
    if executable in {"pytest", "ruff"}:
        return argv
    if executable == "test" and len(argv) == 3 and argv[1] == "-f" and _is_safe_relative_path(argv[2]):
        return argv
    raise ValueError(f"Verification command is not allowed: {command}")


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts
