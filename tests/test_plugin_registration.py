import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from types import ModuleType


def _install_tool_registry_stub(monkeypatch) -> None:
    tools_module = ModuleType("tools")
    registry_module = ModuleType("tools.registry")
    registry_module.tool_result = lambda value: str(value)
    registry_module.tool_error = lambda message: f"ERROR: {message}"
    monkeypatch.setitem(sys.modules, "tools", tools_module)
    monkeypatch.setitem(sys.modules, "tools.registry", registry_module)


def test_create_agent_task_schema_uses_hermes_function_shape() -> None:
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("hermes_agent_gateway_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.CREATE_AGENT_TASK_SCHEMA["name"] == "create_agent_task"
    assert "description" in module.CREATE_AGENT_TASK_SCHEMA
    parameters = module.CREATE_AGENT_TASK_SCHEMA["parameters"]
    assert parameters["type"] == "object"
    assert parameters["required"] == ["runner", "mode", "prompt"]
    runner_description = parameters["properties"]["runner"]["description"]
    assert "enabled runner" in runner_description
    assert "codex" in runner_description
    assert "Claude" not in runner_description
    assert "Qoder" not in runner_description
    assert "DeepSeek" not in runner_description

    class Context:
        def __init__(self) -> None:
            self.calls = []
            self.hooks = []

        def register_tool(self, **kwargs) -> None:
            self.calls.append(kwargs)

        def register_hook(self, hook_name, callback) -> None:
            self.hooks.append((hook_name, callback))

    ctx = Context()
    module.register(ctx)

    assert ctx.calls[0]["schema"] == module.CREATE_AGENT_TASK_SCHEMA
    assert ctx.hooks[0][0] == "pre_gateway_dispatch"

    old_tool = "create_" + "codex" + "_task"
    assert old_tool not in {call["name"] for call in ctx.calls}


def test_plugin_manifest_lists_all_registered_tools() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    provided = set()
    in_tools = False
    for line in (plugin_root / "plugin.yaml").read_text(encoding="utf-8").splitlines():
        if line.strip() == "provides_tools:":
            in_tools = True
            continue
        if in_tools and line and not line.startswith("  - "):
            in_tools = False
        if in_tools and line.startswith("  - "):
            provided.add(line.split("- ", 1)[1].strip())

    spec = importlib.util.spec_from_file_location("hermes_agent_gateway_plugin", plugin_root / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class Context:
        def __init__(self) -> None:
            self.calls = []
            self.hooks = []

        def register_tool(self, **kwargs) -> None:
            self.calls.append(kwargs)

        def register_hook(self, hook_name, callback) -> None:
            self.hooks.append((hook_name, callback))

    ctx = Context()
    module.register(ctx)

    assert {call["name"] for call in ctx.calls} == provided


def test_run_next_agent_task_handler_injects_channel_delivery_callables(monkeypatch, tmp_path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("hermes_agent_gateway_plugin", plugin_root / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    _install_tool_registry_stub(monkeypatch)

    calls = []
    gateway = SimpleNamespace(adapters={})

    monkeypatch.setattr(
        module,
        "load_config",
        lambda: SimpleNamespace(artifact_root=tmp_path / "artifacts"),
    )
    monkeypatch.setattr(module, "_queue", lambda cfg: "queue")
    monkeypatch.setattr(module, "make_adapter_sender", lambda actual_gateway: ("sender", actual_gateway))
    monkeypatch.setattr(module, "make_card_updater", lambda actual_gateway: ("updater", actual_gateway))

    def fake_run_next_queue_task(cfg, *, queue, delivery_sender=None, card_updater=None):
        calls.append(
            {
                "queue": queue,
                "delivery_sender": delivery_sender,
                "card_updater": card_updater,
            }
        )
        return {"status": "EMPTY"}

    monkeypatch.setattr(module, "run_next_queue_task", fake_run_next_queue_task)

    result = module._handle_run_next_agent_task({}, gateway=gateway)

    assert "EMPTY" in result
    assert calls == [
        {
            "queue": "queue",
            "delivery_sender": ("sender", gateway),
            "card_updater": ("updater", gateway),
        }
    ]


def test_deliver_agent_task_result_handler_injects_channel_delivery_callables(monkeypatch, tmp_path) -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("hermes_agent_gateway_plugin", plugin_root / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    _install_tool_registry_stub(monkeypatch)

    calls = []
    gateway = SimpleNamespace(adapters={})

    monkeypatch.setattr(
        module,
        "load_config",
        lambda: SimpleNamespace(artifact_root=tmp_path / "artifacts"),
    )
    monkeypatch.setattr(module, "_queue", lambda cfg: "queue")
    monkeypatch.setattr(module, "make_adapter_sender", lambda actual_gateway: ("sender", actual_gateway))
    monkeypatch.setattr(module, "make_card_updater", lambda actual_gateway: ("updater", actual_gateway))

    def fake_deliver_task_result(queue, *, task_id=None, adapter_sender=None, card_updater=None):
        calls.append(
            {
                "queue": queue,
                "task_id": task_id,
                "adapter_sender": adapter_sender,
                "card_updater": card_updater,
            }
        )
        return {"status": "NO_DELIVERABLE"}

    monkeypatch.setattr(module, "deliver_task_result", fake_deliver_task_result)

    result = module._handle_deliver_agent_task_result({"task_id": "queued_1"}, gateway=gateway)

    assert "NO_DELIVERABLE" in result
    assert calls == [
        {
            "queue": "queue",
            "task_id": "queued_1",
            "adapter_sender": ("sender", gateway),
            "card_updater": ("updater", gateway),
        }
    ]
