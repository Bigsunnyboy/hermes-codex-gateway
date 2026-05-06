import json
import subprocess
from pathlib import Path

from hermes_agent_gateway.config import GatewayConfig
from hermes_agent_gateway.task_service import create_agent_task


class FakeRunner:
    def __init__(self) -> None:
        self.commands = []

    def run(
        self,
        *,
        project_path: Path,
        prompt: str,
        mode: str,
        stdout_path: Path,
        stderr_path: Path,
        agent_session_id: str | None = None,
    ):
        command = ["codex", "exec", "--cd", str(project_path), "--sandbox", "read-only", "--json", prompt]
        self.commands.append(command)
        stdout_path.write_text('{"event":"done"}\n', encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return {
            "command": command,
            "returncode": 0,
            "duration_seconds": 0.01,
        }


def _init_git_repo(repo: Path) -> None:
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)


def _commit_file(repo: Path, name: str = "tracked.txt", content: str = "initial\n") -> None:
    (repo / name).write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", name], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", f"add {name}"], check=True, capture_output=True, text=True)


def test_create_read_task_records_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=FakeRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Analyze only.",
    )

    assert result["success"] is True
    assert result["mode"] == "read"
    assert result["project_path"] == str(repo.resolve())

    artifact_dir = Path(result["artifact_dir"])
    assert (artifact_dir / "task.json").exists()
    assert (artifact_dir / "agent_stdout.jsonl").read_text(encoding="utf-8") == '{"event":"done"}\n'
    assert (artifact_dir / "agent_stderr.log").read_text(encoding="utf-8") == ""

    task_payload = json.loads((artifact_dir / "task.json").read_text(encoding="utf-8"))
    assert task_payload["prompt"] == "Analyze only."
    assert task_payload["command"][0:2] == ["codex", "exec"]


def test_git_task_runs_in_isolated_worktree_and_ignores_main_workspace_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    _commit_file(repo)

    class MutatingMainRunner:
        def run(
            self,
            *,
            project_path: Path,
            prompt: str,
            mode: str,
            stdout_path: Path,
            stderr_path: Path,
            agent_session_id: str | None = None,
        ):
            assert project_path != repo.resolve()
            assert tmp_path / "worktrees" in project_path.parents
            (repo / "main_workspace_change.txt").write_text("concurrent change\n", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return {
                "command": ["codex", "exec", "--cd", str(project_path)],
                "returncode": 0,
                "duration_seconds": 0.01,
            }

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=MutatingMainRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Analyze only.",
    )

    assert result["success"] is True
    assert result["workspace_changed"] is False
    assert result["isolation_mode"] == "git-worktree"
    assert result["execution_path"] != result["project_path"]


def test_workspace_id_reuses_worktree_and_saved_agent_session(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    _commit_file(repo)

    class SessionRunner:
        def __init__(self) -> None:
            self.calls = []

        def run(
            self,
            *,
            project_path: Path,
            prompt: str,
            mode: str,
            stdout_path: Path,
            stderr_path: Path,
            agent_session_id: str | None = None,
        ):
            self.calls.append((project_path, agent_session_id))
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return {
                "command": ["codex", "exec", "--cd", str(project_path)],
                "returncode": 0,
                "duration_seconds": 0.01,
                "agent_session_id": agent_session_id or "session-1",
            }

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )
    runner = SessionRunner()

    first = create_agent_task(
        cfg,
        runner=runner,
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Analyze only.",
        workspace_id="browser-fix",
    )
    second = create_agent_task(
        cfg,
        runner=runner,
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Continue.",
        workspace_id="browser-fix",
    )

    assert first["execution_path"] == second["execution_path"]
    assert first["workspace_id"] == "browser-fix"
    assert second["agent_session_id"] == "session-1"
    assert runner.calls[0][1] is None
    assert runner.calls[1][1] == "session-1"
    session_payload = json.loads((tmp_path / "sessions" / "browser-fix.json").read_text(encoding="utf-8"))
    assert session_payload["agent_session_id"] == "session-1"


def test_read_task_marks_workspace_change_as_unsuccessful(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    (repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True, capture_output=True, text=True)

    class MutatingRunner:
        def run(
            self,
            *,
            project_path: Path,
            prompt: str,
            mode: str,
            stdout_path: Path,
            stderr_path: Path,
            agent_session_id: str | None = None,
        ):
            (project_path / "generated.txt").write_text("mutation\n", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return {
                "command": ["codex", "exec"],
                "returncode": 0,
                "duration_seconds": 0.01,
            }

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=MutatingRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Analyze only.",
    )

    assert result["success"] is False
    assert result["workspace_changed"] is True
    assert "Read-only task changed workspace content/status" in result["error"]


def test_read_task_detects_non_git_workspace_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    (repo / "existing.txt").write_text("initial\n", encoding="utf-8")

    class MutatingRunner:
        def run(
            self,
            *,
            project_path: Path,
            prompt: str,
            mode: str,
            stdout_path: Path,
            stderr_path: Path,
            agent_session_id: str | None = None,
        ):
            (project_path / "existing.txt").write_text("changed\n", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return {
                "command": ["codex", "exec"],
                "returncode": 0,
                "duration_seconds": 0.01,
            }

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=MutatingRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Analyze only.",
    )

    assert result["success"] is False
    assert result["workspace_changed"] is True


def test_read_task_detects_already_dirty_file_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    _commit_file(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("dirty before\n", encoding="utf-8")

    class MutatingRunner:
        def run(
            self,
            *,
            project_path: Path,
            prompt: str,
            mode: str,
            stdout_path: Path,
            stderr_path: Path,
            agent_session_id: str | None = None,
        ):
            (project_path / "tracked.txt").write_text("dirty after\n", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return {
                "command": ["codex", "exec"],
                "returncode": 0,
                "duration_seconds": 0.01,
            }

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=MutatingRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Analyze only.",
    )

    assert result["success"] is False
    assert result["workspace_changed"] is True


def test_runner_exception_still_writes_task_artifact(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)

    class FailingRunner:
        def run(
            self,
            *,
            project_path: Path,
            prompt: str,
            mode: str,
            stdout_path: Path,
            stderr_path: Path,
            agent_session_id: str | None = None,
        ):
            raise RuntimeError("codex crashed")

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=FailingRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="read",
        prompt="Analyze only.",
    )

    assert result["success"] is False
    assert result["returncode"] is None
    assert "RuntimeError: codex crashed" in result["error"]
    artifact_dir = Path(result["artifact_dir"])
    assert (artifact_dir / "after_status.txt").exists()
    task_payload = json.loads((artifact_dir / "task.json").read_text(encoding="utf-8"))
    assert task_payload["error"] == result["error"]


def test_write_task_requires_approval_before_runner_executes(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    _commit_file(repo)

    class UnexpectedRunner:
        def run(self, **kwargs):
            raise AssertionError("runner must not execute without approval")

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=UnexpectedRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="write",
        prompt="Fix tests.",
        workspace_id="write-fix",
    )

    assert result["success"] is False
    assert result["status"] == "APPROVAL_REQUIRED"
    assert "approval" in result["error"].lower()


def test_read_task_rejects_verify_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    try:
        create_agent_task(
            cfg,
            runner=FakeRunner(),
            runner_name="codex",
            repo="example-repo",
            path=None,
            mode="read",
            prompt="Analyze only.",
            verify_commands=["touch should_not_run"],
        )
    except ValueError as exc:
        assert "verify_commands" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_approved_write_task_runs_verification_commands(tmp_path: Path) -> None:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    _commit_file(repo)

    class WritingRunner:
        def run(
            self,
            *,
            project_path: Path,
            prompt: str,
            mode: str,
            stdout_path: Path,
            stderr_path: Path,
            agent_session_id: str | None = None,
        ):
            (project_path / "generated.txt").write_text("generated\n", encoding="utf-8")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text("", encoding="utf-8")
            return {
                "command": ["codex", "exec", "--cd", str(project_path)],
                "returncode": 0,
                "duration_seconds": 0.01,
            }

    cfg = GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )

    result = create_agent_task(
        cfg,
        runner=WritingRunner(),
        runner_name="codex",
        repo="example-repo",
        path=None,
        mode="write",
        prompt="Fix tests.",
        workspace_id="write-fix",
        approved=True,
        verify_commands=["test -f generated.txt"],
    )

    assert result["success"] is True
    assert result["status"] == "DONE"
    assert result["workspace_changed"] is True
    assert result["verify_results"][0]["command"] == "test -f generated.txt"
    assert result["verify_results"][0]["returncode"] == 0
    artifact_dir = Path(result["artifact_dir"])
    verify_payload = json.loads((artifact_dir / "verify_results.json").read_text(encoding="utf-8"))
    assert verify_payload[0]["returncode"] == 0
