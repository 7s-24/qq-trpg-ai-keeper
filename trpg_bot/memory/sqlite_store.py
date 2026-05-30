from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from trpg_bot.config import get_settings
from trpg_bot.models import CampaignSettings, ReplyMode, RuleSystemName, TurnMessage

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS campaigns (
  id TEXT PRIMARY KEY, group_id TEXT NOT NULL, name TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS players (
  id TEXT PRIMARY KEY, nickname TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_players (
  campaign_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'player', active INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (campaign_id, user_id)
);
CREATE TABLE IF NOT EXISTS turns (
  campaign_id TEXT NOT NULL, turn_id INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, closed_at TEXT,
  PRIMARY KEY (campaign_id, turn_id)
);
CREATE TABLE IF NOT EXISTS turn_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, group_id TEXT NOT NULL, campaign_id TEXT NOT NULL, turn_id INTEGER NOT NULL,
  user_id TEXT NOT NULL, nickname TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT NOT NULL, message_type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, source_turn_id INTEGER
);
CREATE TABLE IF NOT EXISTS settings (
  campaign_id TEXT PRIMARY KEY, group_id TEXT NOT NULL, reply_mode TEXT NOT NULL, rule_system TEXT NOT NULL,
  active_players TEXT NOT NULL DEFAULT '[]', required_players TEXT NOT NULL DEFAULT '[]', kp_users TEXT NOT NULL DEFAULT '[]', current_turn_id INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS character_cards (
  campaign_id TEXT NOT NULL, user_id TEXT NOT NULL, system TEXT NOT NULL, character_name TEXT, path TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (campaign_id, user_id)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().database_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    def get_or_create_settings(self, group_id: str) -> CampaignSettings:
        settings = get_settings()
        campaign_id = f"group_{group_id}"
        now = utc_now()
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO campaigns(id, group_id, name, created_at) VALUES (?, ?, ?, ?)", (campaign_id, group_id, f"QQ群 {group_id}", now))
            row = conn.execute("SELECT * FROM settings WHERE campaign_id=?", (campaign_id,)).fetchone()
            if row is None:
                kp_users = sorted(settings.default_kps)
                conn.execute(
                    "INSERT INTO settings(campaign_id, group_id, reply_mode, rule_system, active_players, required_players, kp_users, current_turn_id) VALUES (?, ?, ?, ?, '[]', '[]', ?, 1)",
                    (campaign_id, group_id, settings.default_reply_mode.value, settings.default_rule_system.value, json.dumps(kp_users, ensure_ascii=False)),
                )
                conn.execute("INSERT OR IGNORE INTO turns(campaign_id, turn_id, status, created_at) VALUES (?, 1, 'open', ?)", (campaign_id, now))
                row = conn.execute("SELECT * FROM settings WHERE campaign_id=?", (campaign_id,)).fetchone()
            return _settings_from_row(row)

    def save_settings(self, s: CampaignSettings) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE settings SET reply_mode=?, rule_system=?, active_players=?, required_players=?, kp_users=?, current_turn_id=? WHERE campaign_id=?",
                (s.reply_mode.value, s.rule_system.value, _json_set(s.active_players), _json_set(s.required_players), _json_set(s.kp_users), s.current_turn_id, s.campaign_id),
            )

    def add_turn_message(self, msg: TurnMessage) -> None:
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO players(id, nickname, created_at, updated_at) VALUES (?, ?, ?, ?)", (msg.user_id, msg.nickname, utc_now(), utc_now()))
            conn.execute("UPDATE players SET nickname=?, updated_at=? WHERE id=?", (msg.nickname, utc_now(), msg.user_id))
            conn.execute("INSERT INTO turn_messages(group_id, campaign_id, turn_id, user_id, nickname, content, timestamp, message_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (msg.group_id, msg.campaign_id, msg.turn_id, msg.user_id, msg.nickname, msg.content, msg.timestamp.isoformat(), msg.message_type))

    def list_turn_messages(self, campaign_id: str, turn_id: int) -> list[TurnMessage]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM turn_messages WHERE campaign_id=? AND turn_id=? ORDER BY id", (campaign_id, turn_id)).fetchall()
        return [TurnMessage(r["group_id"], r["campaign_id"], r["turn_id"], r["user_id"], r["nickname"], r["content"], datetime.fromisoformat(r["timestamp"]), r["message_type"]) for r in rows]

    def clear_turn_messages(self, campaign_id: str, turn_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM turn_messages WHERE campaign_id=? AND turn_id=?", (campaign_id, turn_id))

    def close_and_next_turn(self, s: CampaignSettings) -> CampaignSettings:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("UPDATE turns SET status='closed', closed_at=? WHERE campaign_id=? AND turn_id=?", (now, s.campaign_id, s.current_turn_id))
            s.current_turn_id += 1
            conn.execute("INSERT OR IGNORE INTO turns(campaign_id, turn_id, status, created_at) VALUES (?, ?, 'open', ?)", (s.campaign_id, s.current_turn_id, now))
        self.save_settings(s)
        return s

    def upsert_character_card(self, campaign_id: str, user_id: str, system: str, character_name: str, path: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO character_cards(campaign_id, user_id, system, character_name, path, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(campaign_id, user_id) DO UPDATE SET system=excluded.system, character_name=excluded.character_name, path=excluded.path, updated_at=excluded.updated_at", (campaign_id, user_id, system, character_name, path, utc_now()))

    def add_memory(self, campaign_id: str, type_: str, title: str, content: str, tags: list[str] | None = None, source_turn_id: int | None = None) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("INSERT INTO memories(campaign_id, type, title, content, tags, created_at, updated_at, source_turn_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (campaign_id, type_, title, content, json.dumps(tags or [], ensure_ascii=False), now, now, source_turn_id))

    def search_memories(self, campaign_id: str, keywords: list[str], limit: int = 8) -> list[dict[str, Any]]:
        if not keywords:
            return []
        clauses = " OR ".join(["title LIKE ? OR content LIKE ? OR tags LIKE ?" for _ in keywords])
        params: list[Any] = [campaign_id]
        for kw in keywords:
            like = f"%{kw}%"
            params.extend([like, like, like])
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM memories WHERE campaign_id=? AND ({clauses}) ORDER BY updated_at DESC LIMIT ?", params).fetchall()
        return [dict(r) for r in rows]


def _json_set(values: set[str]) -> str:
    return json.dumps(sorted(values), ensure_ascii=False)


def _settings_from_row(row: sqlite3.Row) -> CampaignSettings:
    return CampaignSettings(
        campaign_id=row["campaign_id"], group_id=row["group_id"], reply_mode=ReplyMode(row["reply_mode"]), rule_system=RuleSystemName(row["rule_system"]),
        active_players=set(json.loads(row["active_players"] or "[]")), required_players=set(json.loads(row["required_players"] or "[]")), kp_users=set(json.loads(row["kp_users"] or "[]")), current_turn_id=int(row["current_turn_id"]),
    )
