from __future__ import annotations

import re
from datetime import datetime, timezone

MENTION_RE = re.compile(r"@(?P<id>[A-Za-z0-9_\-]+)")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def campaign_id_for_group(group_id: str) -> str:
    return f"group_{group_id}"


def extract_mentioned_user_ids(text: str) -> list[str]:
    return MENTION_RE.findall(text)


def keywords_from_text(text: str, limit: int = 12) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{3,}", text)
    seen: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
        if len(seen) >= limit:
            break
    return seen
