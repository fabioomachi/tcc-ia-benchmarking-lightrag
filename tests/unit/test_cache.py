import numpy as np

from ragbench.infrastructure.semantic_cache import SemanticCache, SlidingWindowHistory


def test_semantic_cache_hit_and_miss():
    cache = SemanticCache(threshold=0.90)

    vec_a = np.array([1.0, 0.0, 0.0])
    vec_b = np.array([0.95, 0.05, 0.0])
    vec_c = np.array([0.0, 1.0, 0.0])

    cache.add(vec_a, "Resposta para Vetor A")

    # Hit esperado para vetor muito próximo
    resp, sim = cache.get(vec_b)
    assert resp == "Resposta para Vetor A"
    assert sim >= 0.90

    # Miss esperado para vetor ortogonal
    resp, sim = cache.get(vec_c)
    assert resp is None
    assert sim < 0.90


def test_sliding_window_history():
    history = SlidingWindowHistory(max_turns=2)
    history.add_turn("Oi 1", "Resp 1")
    history.add_turn("Oi 2", "Resp 2")
    history.add_turn("Oi 3", "Resp 3")

    messages = history.get_messages()
    # 2 turnos = 4 mensagens no total (turnos 2 e 3)
    assert len(messages) == 4
    assert messages[0]["content"] == "Oi 2"
    assert messages[-1]["content"] == "Resp 3"
