from __future__ import annotations

import builtins
import importlib.util
from pathlib import Path


def test_yaml_compat_uses_pyyaml_for_block_lists():
    from trpg_bot import yaml_compat as yaml

    data = yaml.safe_load("inventory:\n  - 手电筒\n  - 笔记本\n")
    assert data["inventory"] == ["手电筒", "笔记本"]


def test_yaml_compat_falls_back_without_pyyaml(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("no yaml")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    path = Path(__file__).parents[1] / "trpg_bot" / "yaml_compat.py"
    spec = importlib.util.spec_from_file_location("yaml_compat_fallback_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.safe_load("a: 1") == {"a": 1}

