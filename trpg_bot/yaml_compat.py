from __future__ import annotations

try:  # pragma: no cover - exercised indirectly when PyYAML is installed
    import yaml as _yaml
except ImportError:  # pragma: no cover - tests monkeypatch this path
    from trpg_bot import simple_yaml as _yaml

safe_dump = _yaml.safe_dump
safe_load = _yaml.safe_load
YAMLError = _yaml.YAMLError

