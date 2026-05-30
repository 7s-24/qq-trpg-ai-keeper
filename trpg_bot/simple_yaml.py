"""Small fallback YAML subset used for tests/local MVP when PyYAML is unavailable.
Supports simple mappings, nested mappings by indentation, scalars, and [] lists.
Install PyYAML in production for full YAML support.
"""
from __future__ import annotations

from typing import Any

class YAMLError(Exception):
    pass


def safe_dump(data: Any, allow_unicode: bool = True, sort_keys: bool = False) -> str:
    return _dump_value(data, 0, sort_keys).lstrip("\n")


def _dump_value(value: Any, indent: int, sort_keys: bool) -> str:
    sp = " " * indent
    if isinstance(value, dict):
        items = sorted(value.items()) if sort_keys else value.items()
        lines = []
        for k, v in items:
            if isinstance(v, dict):
                lines.append(f"{sp}{k}:")
                lines.append(_dump_value(v, indent + 2, sort_keys).rstrip("\n"))
            elif isinstance(v, list):
                if not v:
                    lines.append(f"{sp}{k}: []")
                else:
                    lines.append(f"{sp}{k}:")
                    for item in v:
                        lines.append(f"{' ' * (indent + 2)}- {_scalar(item)}")
            else:
                lines.append(f"{sp}{k}: {_scalar(v)}")
        return "\n".join(lines) + "\n"
    return sp + _scalar(value) + "\n"


def _scalar(value: Any) -> str:
    if value == "":
        return '""'
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return str(value)


def safe_load(text: str) -> Any:
    lines = [line.rstrip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for line in lines:
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if stripped.startswith("-"):
            raise YAMLError("fallback YAML parser only supports inline [] lists")
        if ":" not in stripped:
            raise YAMLError(f"invalid line: {line}")
        key, raw = stripped.split(":", 1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if raw.strip() == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(raw.strip())
    return root


def _parse_scalar(raw: str) -> Any:
    if raw in {'""', "''"}:
        return ""
    if raw == "[]":
        return []
    if raw == "{}":
        return {}
    if raw.lower() in {"null", "none"}:
        return None
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    try:
        return int(raw)
    except ValueError:
        return raw.strip('"').strip("'")
