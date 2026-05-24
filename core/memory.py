import json
import os
import logging
from typing import List, Optional, Dict, Any
from core.schema import MemoryEntry
from pathlib import Path

logger = logging.getLogger("agent-harness")

class MemoryManager:
    def __init__(self, project_root: str):
        self.memory_dir = Path(project_root) / ".claude_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.memory_dir / "MEMORY.md"
        self.storage_dir = self.memory_dir / "storage"
        self.storage_dir.mkdir(exist_ok=True)
        self._cache: List[MemoryEntry] = []

    def save_memory(self, entry: MemoryEntry) -> str:
        """Saves a memory entry to a file and updates the index."""
        logger.info(f"Saving {entry.category} memory: {entry.content[:50]}...")

        # Generate a unique filename based on content hash or timestamp
        import uuid
        mem_id = str(uuid.uuid4())[:8]
        filename = f"{entry.category}_{mem_id}.json"
        filepath = self.storage_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(entry.model_dump_json(indent=2))

        self._cache.append(entry)
        self._update_index(filename, entry)
        return mem_id

    def _update_index(self, filename: str, entry: MemoryEntry):
        """Appends the memory pointer to MEMORY.md."""
        with open(self.index_file, 'a', encoding='utf-8') as f:
            f.write(f"- [{entry.category}] {filename} — {entry.content[:60]}...\n")

    def load_all_memories(self) -> List[MemoryEntry]:
        """Loads all memories from the storage directory with caching."""
        if self._cache:
            return self._cache

        memories = []
        for file in self.storage_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    memories.append(MemoryEntry(**data))
            except Exception as e:
                logger.error(f"Failed to load memory {file}: {e}")

        self._cache = memories
        return memories

    def get_relevant_memories(self, query: str) -> str:
        """
        Simple keyword-based retrieval.
        In a production system, this would use embeddings/vector search.
        """
        memories = self.load_all_memories()
        relevant = [m.content for m in memories if any(word in m.content.lower() for word in query.lower().split())]

        if not relevant:
            return "No relevant memories found."

        return "\n".join([f"Memory ({m.category}): {m.content}" for m in relevant])
