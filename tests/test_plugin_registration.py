import importlib.util
from pathlib import Path


def test_create_codex_task_schema_uses_hermes_function_shape() -> None:
    plugin_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("hermes_local_agent_gateway_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.CREATE_CODEX_TASK_SCHEMA["name"] == "create_codex_task"
    assert "description" in module.CREATE_CODEX_TASK_SCHEMA
    parameters = module.CREATE_CODEX_TASK_SCHEMA["parameters"]
    assert parameters["type"] == "object"
    assert parameters["required"] == ["mode", "prompt"]

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

    assert ctx.calls[0]["schema"] == module.CREATE_CODEX_TASK_SCHEMA
    assert ctx.hooks[0][0] == "pre_gateway_dispatch"


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

    spec = importlib.util.spec_from_file_location("hermes_local_agent_gateway_plugin", plugin_root / "__init__.py")
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
