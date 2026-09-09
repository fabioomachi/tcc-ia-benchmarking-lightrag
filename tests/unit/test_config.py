from ragbench.config import BenchmarkSettings, OllamaSettings


def test_default_config():
    settings = BenchmarkSettings()
    assert settings.ollama.base_url == "http://localhost:11434/v1/"
    assert settings.lightrag.llm_model == "qwen2.5:3b"
    assert settings.lightrag.embed_model == "all-minilm"
    assert settings.ragas.judge_model == "qwen2.5:7b"
    assert settings.concurrency_limit == 10
    assert settings.cache_threshold == 0.92


def test_custom_ollama_settings():
    ollama = OllamaSettings(base_url="http://custom:11434/v1/", request_timeout=30.0)
    assert ollama.base_url == "http://custom:11434/v1/"
    assert ollama.request_timeout == 30.0
