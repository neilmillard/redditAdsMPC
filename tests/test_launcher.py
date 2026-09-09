import sys
from pathlib import Path

from reddit_ads_mcp import launcher


def test_find_uv_returns_none_when_not_on_path(monkeypatch):
  monkeypatch.setattr(launcher.shutil, "which", lambda name: None)

  assert launcher.find_uv() is None


def test_find_uv_returns_the_resolved_path(monkeypatch):
  monkeypatch.setattr(launcher.shutil, "which", lambda name: "/opt/uv/uv")

  assert launcher.find_uv() == "/opt/uv/uv"


def test_uv_command_runs_the_server_via_uv_run():
  project_root = Path("/path/to/redditAdsMPC")

  assert launcher.uv_command(project_root) == [
    "uv",
    "run",
    "--project",
    "/path/to/redditAdsMPC",
    "reddit-ads-mcp",
  ]


def test_read_runtime_dependencies_reads_project_dependencies_from_pyproject(tmp_path):
  pyproject = tmp_path / "pyproject.toml"
  pyproject.write_text('[project]\nname = "x"\ndependencies = ["mcp>=2.1.1", "httpx>=0.28.1"]\n')

  assert launcher.read_runtime_dependencies(pyproject) == ["mcp>=2.1.1", "httpx>=0.28.1"]


def test_pip_install_command_targets_the_deps_dir_without_a_venv():
  deps_dir = Path("/tmp/deps")

  command = launcher.pip_install_command(deps_dir, ["mcp>=2.1.1", "httpx>=0.28.1"])

  assert command == [
    sys.executable,
    "-m",
    "pip",
    "install",
    "--break-system-packages",
    "--target",
    "/tmp/deps",
    "mcp>=2.1.1",
    "httpx>=0.28.1",
  ]


def test_fallback_command_runs_the_server_module_directly():
  assert launcher.fallback_command() == [sys.executable, "-m", "reddit_ads_mcp.server"]


def test_fallback_env_prepends_deps_and_src_to_pythonpath():
  env = launcher.fallback_env({"PATH": "/usr/bin"}, Path("/tmp/deps"), Path("/repo/src"))

  assert env["PYTHONPATH"] == "/tmp/deps" + launcher.os.pathsep + "/repo/src"
  assert env["PATH"] == "/usr/bin"


def test_fallback_env_preserves_an_existing_pythonpath():
  env = launcher.fallback_env({"PYTHONPATH": "/existing"}, Path("/tmp/deps"), Path("/repo/src"))

  assert env["PYTHONPATH"] == launcher.os.pathsep.join(["/tmp/deps", "/repo/src", "/existing"])


def test_dependencies_installed_is_false_when_deps_dir_is_missing(tmp_path):
  assert launcher.dependencies_installed(tmp_path / "does-not-exist") is False


def test_dependencies_installed_is_false_when_a_package_is_missing(tmp_path):
  (tmp_path / "mcp").mkdir()

  assert launcher.dependencies_installed(tmp_path) is False


def test_dependencies_installed_is_true_when_both_packages_are_present(tmp_path):
  (tmp_path / "mcp").mkdir()
  (tmp_path / "httpx").mkdir()

  assert launcher.dependencies_installed(tmp_path) is True


def test_ensure_dependencies_skips_pip_when_already_installed(tmp_path, monkeypatch):
  deps_dir = tmp_path / "deps"
  deps_dir.mkdir()
  (deps_dir / "mcp").mkdir()
  (deps_dir / "httpx").mkdir()
  pyproject = tmp_path / "pyproject.toml"
  pyproject.write_text('[project]\nname = "x"\ndependencies = []\n')

  calls = []
  monkeypatch.setattr(launcher.subprocess, "run", lambda *a, **k: calls.append((a, k)))

  launcher.ensure_dependencies(deps_dir, pyproject)

  assert calls == []


def test_ensure_dependencies_installs_when_missing(tmp_path, monkeypatch):
  deps_dir = tmp_path / "deps"
  pyproject = tmp_path / "pyproject.toml"
  pyproject.write_text('[project]\nname = "x"\ndependencies = ["mcp>=2.1.1", "httpx>=0.28.1"]\n')

  calls = []
  monkeypatch.setattr(launcher.subprocess, "run", lambda command, **k: calls.append((command, k)))

  launcher.ensure_dependencies(deps_dir, pyproject)

  assert deps_dir.is_dir()
  [(command, kwargs)] = calls
  assert command == launcher.pip_install_command(deps_dir, ["mcp>=2.1.1", "httpx>=0.28.1"])
  assert kwargs == {"check": True}


def test_main_execs_uv_when_available(monkeypatch):
  monkeypatch.setattr(launcher, "find_uv", lambda: "/opt/uv/uv")
  calls = []
  monkeypatch.setattr(
    launcher.os, "execvpe", lambda file, args, env: calls.append((file, args, env))
  )

  launcher.main()

  assert len(calls) == 1
  file, args, env = calls[0]
  assert file == "/opt/uv/uv"
  assert args == launcher.uv_command(launcher.PROJECT_ROOT)
  assert env is launcher.os.environ


def test_main_falls_back_to_pip_and_pythonpath_when_uv_is_missing(monkeypatch):
  monkeypatch.delenv("PYTHONPATH", raising=False)
  monkeypatch.setattr(launcher, "find_uv", lambda: None)
  ensure_calls = []
  monkeypatch.setattr(
    launcher,
    "ensure_dependencies",
    lambda deps_dir, pyproject_path: ensure_calls.append((deps_dir, pyproject_path)),
  )
  exec_calls = []
  monkeypatch.setattr(
    launcher.os, "execvpe", lambda file, args, env: exec_calls.append((file, args, env))
  )

  launcher.main()

  assert ensure_calls == [(launcher.FALLBACK_DEPS_DIR, launcher.PROJECT_ROOT / "pyproject.toml")]
  assert len(exec_calls) == 1
  file, args, env = exec_calls[0]
  assert file == sys.executable
  assert args == launcher.fallback_command()
  assert env["PYTHONPATH"] == launcher.os.pathsep.join(
    [str(launcher.FALLBACK_DEPS_DIR), str(launcher.SRC_DIR)]
  )
