# Security Model

Hermes Agent Gateway is an automation control plane for governed local agent
execution. It is not a sandbox escape boundary.

## Read Mode

Read mode:
- does not require approval;
- maps to the selected runner's safest available read behavior;
- fails the task if workspace content or status changes after execution;
- captures before and after artifacts.

## Write Mode

Write mode:
- requires explicit approval before runner execution;
- uses an isolated git worktree when possible;
- supports changed-path allowlists;
- runs verification commands before reporting success;
- records artifacts and audit data.

## Path Guard

The gateway blocks or fails sensitive targets and unexpected writes. Protected
paths include secrets, credentials, VCS metadata, Hermes runtime state, runner
auth state, and this plugin's own governance files.

## Verification Gate

A write task is successful only when all of these are true:

```text
runner_success
AND path_guard_passed
AND verify_passed
AND artifact_capture_completed
```

## Artifact And Audit Data

Each task writes:
- before and after workspace status;
- stdout and stderr artifacts;
- verification results when configured;
- `task.json` with neutral gateway fields such as `runner` and
  `agent_session_id`.

## Operator Guidance

Keep credentials outside this repository, configure approval allowlists in
shared chats, and run the gateway host with OS-level permissions appropriate to
the repositories it may modify.
