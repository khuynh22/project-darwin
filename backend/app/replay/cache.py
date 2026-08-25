"""Content-addressed cache of recorded agent decisions.

This is what makes the reproducibility claim falsifiable: a released run can be
re-executed offline, through the real engine, with no API key and no cost. The
claim it supports is precise -- *the environment* reproduces given fixed model
outputs. The models themselves do not, and this does not pretend otherwise.

The key includes the rendered system and user prompts because those encode the
world state. That is what makes the key correct rather than a proxy for
correctness: two turns that present the model with the same world share a key,
and two that do not, do not.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Fan out over the first two hex characters so a 2000-response run does not
# land 2000 files in one directory.
_SHARD_LEN = 2


class CacheMiss(Exception):
    """A key was absent in strict mode. Loud on purpose.

    Silence here would let a "reproduction" quietly become a fresh run, which
    is the one failure mode that would make the published numbers unverifiable.
    """


class EnvVersionMismatch(Exception):
    """The cache was recorded against a different environment version.

    Every cached key is bound to the env version that produced it, because a
    mechanic change alters the world brief and therefore every prompt. Serving
    a stale entry would silently mix two environments in one run.
    """


@dataclass(frozen=True)
class CacheStats:
    hits: int = 0
    misses: int = 0
    writes: int = 0


def decision_key(
    *,
    env_version: str,
    model: str,
    prompt_version: str,
    system_prompt: str,
    user_prompt: str,
    tool_names: list[str],
    temperature: float,
) -> str:
    payload = json.dumps(
        {
            "env_version": env_version,
            "model": model,
            "prompt_version": prompt_version,
            "system": system_prompt,
            "user": user_prompt,
            "tools": sorted(tool_names),
            "temperature": temperature,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    # sha256, not hash(): Python randomises string hashing per process, so a
    # key built from it would differ between the recording run and the replay.
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    """One directory per run, sharded by key prefix."""

    def __init__(self, root: Path, *, env_version: str) -> None:
        self.root = Path(root)
        self.env_version = env_version
        self._hits = 0
        self._misses = 0
        self._writes = 0

    def _path(self, key: str) -> Path:
        return self.root / key[:_SHARD_LEN] / f"{key}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.exists():
            self._misses += 1
            return None
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("unreadable cache entry %s: %s", key, exc)
            self._misses += 1
            return None

        recorded = row.get("env_version", "")
        if recorded != self.env_version:
            raise EnvVersionMismatch(
                f"cache entry {key[:12]} was recorded against env_version "
                f"{recorded!r}, replaying against {self.env_version!r}"
            )
        self._hits += 1
        return row["decision"]

    def put(self, key: str, decision: dict) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"env_version": self.env_version, "key": key, "decision": decision},
                default=str,
            ),
            encoding="utf-8",
        )
        self._writes += 1

    def recorded_env_version(self) -> str | None:
        """The env version this cache was recorded against, or None if empty.

        Used to pre-flight a replay: checking one entry up front is far better
        than discovering the mismatch turn by turn, especially since the engine
        survives agent errors and would otherwise finish a whole wrong run.
        """
        if not self.root.is_dir():
            return None
        for path in self.root.rglob("*.json"):
            try:
                return json.loads(path.read_text(encoding="utf-8")).get("env_version", "")
            except (json.JSONDecodeError, OSError):
                continue
        return None

    def stats(self) -> CacheStats:
        return CacheStats(hits=self._hits, misses=self._misses, writes=self._writes)

    def __len__(self) -> int:
        if not self.root.is_dir():
            return 0
        return sum(1 for _ in self.root.rglob("*.json"))
