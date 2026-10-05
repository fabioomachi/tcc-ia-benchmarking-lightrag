import numpy as np
from pydantic import BaseModel, ConfigDict

from ragbench.core.interfaces import BaseCache


class CachedItem(BaseModel):
    """Par (vetor, resposta) do cache semântico (contrato tipado)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    embedding: np.ndarray
    response: str


class SemanticCache(BaseCache):
    """Cache semântico vetorial em memória para short-circuit de consultas repetidas."""

    def __init__(self, threshold: float = 0.92):
        self.threshold = threshold
        self.cache: list[CachedItem] = []

    @staticmethod
    def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def get(self, query_emb: np.ndarray) -> tuple[str | None, float]:
        """Verifica se existe resposta similar no cache acima do limiar (vetorizado)."""
        if not self.cache:
            return None, 0.0
        matrix = np.stack([item.embedding for item in self.cache])
        query_norm = np.linalg.norm(query_emb)
        if query_norm == 0:
            return None, 0.0
        norms = np.linalg.norm(matrix, axis=1)
        denom = norms * query_norm
        sims = np.divide(matrix @ query_emb, denom, out=np.zeros_like(denom), where=denom != 0)
        best = int(np.argmax(sims))
        if sims[best] >= self.threshold:
            return self.cache[best].response, float(sims[best])
        return None, 0.0

    def add(self, query_emb: np.ndarray, response: str) -> None:
        """Armazena o par (vetor, resposta) no cache."""
        self.cache.append(CachedItem(embedding=query_emb, response=response))

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
