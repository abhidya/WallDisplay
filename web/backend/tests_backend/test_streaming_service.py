from types import SimpleNamespace


def test_streaming_service_runtime_lookup_falls_back_to_app_runtime(monkeypatch):
    import importlib

    from web.backend.core import streaming_service as streaming_service_module

    runtime_calls = []
    runtime = SimpleNamespace(get_device=lambda name: runtime_calls.append(name) or {"name": name})
    runtime_module = importlib.import_module("services.app_runtime")

    monkeypatch.setattr(runtime_module, "get_app_runtime", lambda: runtime)

    service = streaming_service_module.StreamingService(runtime=None)

    assert service._get_runtime_device("Projector A") == {"name": "Projector A"}
    assert runtime_calls == ["Projector A"]
    assert service.runtime is runtime
