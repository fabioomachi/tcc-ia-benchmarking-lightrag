"""Proteção contra vazamento de credenciais (ex: Google AI Studio key).

Camadas:
- `SecretStr` no `config.py`: repr/print/model_dump nunca expõem o valor.
- `scrub_text` + `SecretScrubFilter`: removem padrões de chave que porventura
  cheguem a mensagens de log/exceção antes da persistência em `logs/`.
"""

import logging
import re

from pydantic import SecretStr

# Chave Google AI Studio: "AIza" + 35 chars [A-Za-z0-9_-].
_GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]{20,}")

# Header de auth em dumps de requisição: "x-goog-api-key": "<valor>".
_API_KEY_HEADER_RE = re.compile(r"(?i)(x-goog-api-key['\"]?\s*[:=]\s*['\"]?)([^'\"\s,}]+)")


def redact_key(value: SecretStr | str | None) -> str:
    """Resume presença sem expor valor: `*** (definida, N chars)` ou `ausente`."""
    raw = value.get_secret_value() if isinstance(value, SecretStr) else (value or "")
    if not raw:
        return "ausente"
    return f"*** (definida, {len(raw)} chars)"


def scrub_text(text: str) -> str:
    """Remove valores de chave de um texto livre (idempotente)."""
    if not text:
        return text
    scrubbed = _GOOGLE_KEY_RE.sub("AIza***REDATADO***", text)
    return _API_KEY_HEADER_RE.sub(r"\1***REDATADO***", scrubbed)


class SecretScrubFilter(logging.Filter):
    """Filtro de logging que redige chaves antes de console/arquivo."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = scrub_text(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {key: scrub_text(str(val)) for key, val in record.args.items()}
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        scrub_text(str(arg)) if isinstance(arg, str) else arg for arg in record.args
                    )
        except Exception:
            pass
        return True
