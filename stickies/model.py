"""Модель данных и хранение в JSON."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field


@dataclass
class Task:
    text: str = ""
    done: bool = False
    description: str = ""


@dataclass
class Note:
    id: str
    color: str = "yellow"
    title: str = ""
    tasks: list[Task] = field(default_factory=list)
    tag: str = ""
    deadline: str | None = None  # ISO-дата, например "2026-11-03"
    collapsed: bool = False
    pinned: bool = False
    x: int = 120
    y: int = 120
    w: int = 300
    h: int = 340

    @staticmethod
    def new(color: str = "yellow", x: int = 120, y: int = 120) -> "Note":
        return Note(id=uuid.uuid4().hex, color=color, x=x, y=y)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "color": self.color, "title": self.title,
            "tasks": [{"text": t.text, "done": t.done, "description": t.description} for t in self.tasks],
            "tag": self.tag, "deadline": self.deadline, "pinned": self.pinned, "collapsed": self.collapsed,
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
        }

    @staticmethod
    def from_dict(d: dict) -> "Note":
        return Note(
            id=str(d.get("id") or uuid.uuid4().hex),
            color=d.get("color", "yellow"),
            title=d.get("title", ""),
            tasks=[Task(str(t.get("text", "")), bool(t.get("done", False)),
                        str(t.get("description", "")))
                   for t in d.get("tasks", [])],
            tag=d.get("tag", ""),
            deadline=d.get("deadline"),
            collapsed=bool(d.get("collapsed", False)),
            pinned=bool(d.get("pinned", False)),
            x=int(d.get("x", 120)), y=int(d.get("y", 120)),
            w=int(d.get("w", 300)), h=int(d.get("h", 340)),
        )


class Store:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def load(self) -> list[Note]:
        try:
            with open(self.path, encoding="utf-8") as f:
                return [Note.from_dict(d) for d in json.load(f)]
        except (OSError, ValueError, TypeError, AttributeError):
            return []

    def save(self, notes: list[Note]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump([n.to_dict() for n in notes], f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # атомарная запись, чтобы не потерять заметки
