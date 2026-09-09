"""Fallback launcher used by `bin/reddit-ads-mcp` when `uv` isn't on PATH.

Multica agent runtimes have repeatedly failed to start this MCP connector with
`ENOENT: Executable not found in $PATH: uv`, even though `uv` works fine
elsewhere. `uv` itself isn't the problem — the runtime just doesn't have it on
PATH. This module tries `uv` first (fast, respects the lockfile) and, if it's
missing, falls back to installing the runtime dependencies with `pip install
--target` (no venv, no `uv`) and running the server module directly with
`PYTHONPATH` pointed at that target dir and at `src/`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
FALLBACK_DEPS_DIR = PROJECT_ROOT / ".fallback-deps"


def find_uv() -> str | None:
  return shutil.which("uv")


def uv_command(project_root: Path) -> list[str]:
  return ["uv", "run", "--project", str(project_root), "reddit-ads-mcp"]


def read_runtime_dependencies(pyproject_path: Path) -> list[str]:
  data = tomllib.loads(pyproject_path.read_text())
  return data["project"]["dependencies"]


def pip_install_command(target_dir: Path, dependencies: list[str]) -> list[str]:
  return [
    sys.executable,
    "-m",
    "pip",
    "install",
    "--break-system-packages",
    "--target",
    str(target_dir),
    *dependencies,
  ]


def fallback_command() -> list[str]:
  return [sys.executable, "-m", "reddit_ads_mcp.server"]


def fallback_env(base_env: dict[str, str], deps_dir: Path, src_dir: Path) -> dict[str, str]:
  env = dict(base_env)
  existing = env.get("PYTHONPATH", "")
  parts = [str(deps_dir), str(src_dir)] + ([existing] if existing else [])
  env["PYTHONPATH"] = os.pathsep.join(parts)
  return env


def dependencies_installed(deps_dir: Path) -> bool:
  return (deps_dir / "mcp").is_dir() and (deps_dir / "httpx").is_dir()


def ensure_dependencies(deps_dir: Path, pyproject_path: Path) -> None:
  if dependencies_installed(deps_dir):
    return
  deps_dir.mkdir(parents=True, exist_ok=True)
  dependencies = read_runtime_dependencies(pyproject_path)
  subprocess.run(pip_install_command(deps_dir, dependencies), check=True)


def main() -> None:
  uv = find_uv()
  if uv:
    os.execvpe(uv, uv_command(PROJECT_ROOT), os.environ)
    return  # pragma: no cover - execvpe replaces the process on success

  ensure_dependencies(FALLBACK_DEPS_DIR, PROJECT_ROOT / "pyproject.toml")
  command = fallback_command()
  env = fallback_env(os.environ, FALLBACK_DEPS_DIR, SRC_DIR)
  os.execvpe(command[0], command, env)


if __name__ == "__main__":
  main()
