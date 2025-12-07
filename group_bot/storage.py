"""Simple JSON-backed warning storage."""
import json
import os
from collections import defaultdict
from typing import DefaultDict, Dict


class WarningStore:
    """Persist warnings per user per chat."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._data: DefaultDict[str, DefaultDict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            raw: Dict[str, Dict[str, int]] = json.load(fh)
        for chat_id, users in raw.items():
            for user_id, count in users.items():
                self._data[str(chat_id)][str(user_id)] = int(count)

    def _save(self) -> None:
        serializable = {chat: dict(users) for chat, users in self._data.items()}
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(serializable, fh, indent=2, ensure_ascii=False)

    def increment(self, chat_id: int, user_id: int) -> int:
        chat_key = str(chat_id)
        user_key = str(user_id)
        self._data[chat_key][user_key] += 1
        self._save()
        return self._data[chat_key][user_key]

    def reset(self, chat_id: int, user_id: int) -> None:
        chat_key = str(chat_id)
        user_key = str(user_id)
        if user_key in self._data.get(chat_key, {}):
            del self._data[chat_key][user_key]
            self._save()

    def get(self, chat_id: int, user_id: int) -> int:
        """Return warning count for a user in a chat."""

        chat_key = str(chat_id)
        user_key = str(user_id)
        return int(self._data.get(chat_key, {}).get(user_key, 0))

    def get_all(self, chat_id: int) -> Dict[str, int]:
        chat_key = str(chat_id)
        return dict(self._data.get(chat_key, {}))
