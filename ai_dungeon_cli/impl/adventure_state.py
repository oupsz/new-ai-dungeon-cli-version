import os
import time

import yaml


class AdventureStateStore:
    def __init__(self, path=None):
        self.path = path or self.default_path()

    @staticmethod
    def default_path():
        return os.path.expanduser("~/.config/ai-dungeon-cli/adventures.yml")

    @staticmethod
    def _empty_state():
        return {
            "last": None,
            "recent": [],
        }

    @staticmethod
    def _normalize_record(record):
        if not isinstance(record, dict):
            return None

        adventure_id = record.get("adventure_id")
        short_id = record.get("short_id")
        short_code = record.get("short_code")

        if not adventure_id and not short_id and not short_code:
            return None

        return {
            "adventure_id": str(adventure_id) if adventure_id else None,
            "short_id": str(short_id) if short_id else None,
            "short_code": str(short_code) if short_code else None,
            "character_name": record.get("character_name"),
            "auth_token": record.get("auth_token"),
            "refresh_token": record.get("refresh_token"),
            "saved_at": record.get("saved_at"),
        }

    @classmethod
    def _normalize_state(cls, state):
        if not isinstance(state, dict):
            return cls._empty_state()

        recent = []
        for record in state.get("recent", []):
            normalized = cls._normalize_record(record)
            if normalized:
                recent.append(normalized)

        last = cls._normalize_record(state.get("last"))
        if last is None and recent:
            last = recent[0]

        return {
            "last": last,
            "recent": recent,
        }

    @staticmethod
    def matches(record, target):
        if not record or not target:
            return False

        target = str(target)
        return target in [
            record.get("adventure_id"),
            record.get("short_id"),
            record.get("short_code"),
        ]

    @classmethod
    def find_record(cls, records, target):
        for record in records or []:
            if cls.matches(record, target):
                return record
        return None

    def load(self):
        try:
            with open(self.path, "r") as handle:
                payload = yaml.load(handle, Loader=yaml.FullLoader)
        except IOError:
            return self._empty_state()

        return self._normalize_state(payload)

    def save(self, adventure_id, short_id=None, short_code=None, character_name=None,
             auth_token=None, refresh_token=None):
        state = self.load()
        saved_at = int(time.time())
        record = self._normalize_record({
            "adventure_id": adventure_id,
            "short_id": short_id,
            "short_code": short_code,
            "character_name": character_name,
            "auth_token": auth_token,
            "refresh_token": refresh_token,
            "saved_at": saved_at,
        })

        recent = []
        for existing in state["recent"]:
            if self.matches(existing, record["adventure_id"]) or \
               self.matches(existing, record["short_id"]) or \
               self.matches(existing, record["short_code"]):
                continue
            recent.append(existing)

        next_state = {
            "last": record,
            "recent": [record] + recent[:19],
        }

        parent_dir = os.path.dirname(self.path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(self.path, "w") as handle:
            yaml.safe_dump(next_state, handle, sort_keys=False)

        return record

    def get_last(self):
        return self.load()["last"]

    def find(self, target):
        state = self.load()
        if target in [None, "", "last"]:
            return state["last"]
        return self.find_record(state["recent"], target)
