"""Exceções customizadas do domínio ragbench."""


class RagBenchException(Exception):
    """Exceção base para o ragbench."""

    pass


class StorageNotFoundError(RagBenchException):
    """Lançada quando o banco de grafos/vetores não foi encontrado."""

    pass


class OllamaConnectionError(RagBenchException):
    """Lançada quando a API do Ollama está inacessível ou rejeita requisições."""

    pass


class DatasetError(RagBenchException):
    """Lançada quando arquivos de entrada ou golden dataset estão ausentes ou corrompidos."""

    pass


class EvaluationError(RagBenchException):
    """Lançada quando o pipeline RAGAS falha ao processar amostras."""

    pass
