from typing import Any

import numpy as np


class SemanticCache:
    """Cache semântico vetorial em memória para short-circuit de consultas repetidas."""

    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        self.cache: list[dict[str, Any]] = []

    @staticmethod
    def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def get(self, query_emb: np.ndarray) -> tuple[str | None, float]:
        """Verifica se existe resposta similar no cache acima do limiar."""
        for item in self.cache:
            similarity = self._cosine_similarity(query_emb, item["embedding"])
            if similarity >= self.threshold:
                return item["response"], similarity
        return None, 0.0

    def add(self, query_emb: np.ndarray, response: str) -> None:
        """Armazena o par (vetor, resposta) no cache."""
        self.cache.append({"embedding": query_emb, "response": response})

    def clear(self) -> None:
        """Limpa o cache em memória."""
        self.cache.clear()

    @property
    def size(self) -> int:
        return len(self.cache)


class SlidingWindowHistory:
    """Controlador de histórico de sessão com janela deslizante estrita."""

    def __init__(self, max_turns: int = 3):
        self.max_turns = max_turns
        self.messages: list[dict[str, str]] = []

    def add_turn(self, user_msg: str, asst_msg: str) -> None:
        self.messages.append({"role": "user", "content": user_msg})
        self.messages.append({"role": "assistant", "content": asst_msg})
        if len(self.messages) > self.max_turns * 2:
            self.messages = self.messages[-self.max_turns * 2 :]

    def get_messages(self) -> list[dict[str, str]]:
        return list(self.messages)

    def clear(self) -> None:
        self.messages.clear()
