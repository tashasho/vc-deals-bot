"""Persists which item IDs have already been sent so they don't repeat."""

import json
import logging
import os
from typing import Set

log = logging.getLogger(__name__)
MAX_SEEN = 5000


class SeenState:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._seen: Set[str] = set()
        self._ordered: list = []
        self._load()

    def _load(self):
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath) as f:
                data = json.load(f)
            self._ordered = data.get("seen", [])
            self._seen = set(self._ordered)
            log.info(f"Loaded {len(self._seen)} seen items from {self.filepath}")
        except Exception as e:
            log.warning(f"Could not load state file: {e}. Starting fresh.")

    def has_seen(self, item_id: str) -> bool:
        return item_id in self._seen

    def mark_seen(self, item_id: str):
        if item_id not in self._seen:
            self._seen.add(item_id)
            self._ordered.append(item_id)
            if len(self._ordered) > MAX_SEEN:
                evicted = self._ordered.pop(0)
                self._seen.discard(evicted)

    def save(self):
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump({"seen": self._ordered}, f, indent=2)
        log.info(f"State saved ({len(self._ordered)} entries) → {self.filepath}")
