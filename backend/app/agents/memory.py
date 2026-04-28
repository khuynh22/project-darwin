"""Per-agent vector memory using Chroma (local, file-backed)."""
from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)


class AgentMemory:
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._collection = None

    def _ensure(self) -> Any:
        if self._collection is not None:
            return self._collection
        try:
            import chromadb

            client = chromadb.PersistentClient(path=get_settings().chroma_path)
            self._collection = client.get_or_create_collection(name=f"darwin_{self.agent_id}")
        except Exception as e:  # noqa: BLE001
            log.warning("Chroma unavailable for %s: %s — memory disabled", self.agent_id, e)
            self._collection = None
        return self._collection

    def add(self, *, turn: int, kind: str, text: str, metadata: dict | None = None) -> None:
        col = self._ensure()
        if col is None:
            return
        col.add(
            documents=[text],
            metadatas=[{"turn": turn, "kind": kind, **(metadata or {})}],
            ids=[f"{self.agent_id}-{turn}-{kind}-{hash(text) & 0xffffffff:x}"],
        )

    def recall(self, query: str, *, k: int = 4) -> list[str]:
        col = self._ensure()
        if col is None:
            return []
        try:
            res = col.query(query_texts=[query], n_results=k)
            docs = res.get("documents", [[]])
            return docs[0] if docs else []
        except Exception as e:  # noqa: BLE001
            log.debug("recall failed for %s: %s", self.agent_id, e)
            return []
