"""Clarificador rule-based para o spike da hipótese (puro, sem I/O).

Hipótese: conversar para coletar os dados faltantes antes de consultar o
grafo gera resposta mais acurada do que o single-turn direto.

Extração por regex/keywords para os slots legados de acesso/CDC, com
fallback genérico para slots de novos POPs (qualquer `expected_slot`
desconhecido é aceito como valor literal). Não usa LLM aqui para manter
o teste determinístico e barato; o LLM/grafo entra só na resposta final.
"""

from __future__ import annotations

import re


class BankingSlot:
    """Definição de um slot a coletar."""

    def __init__(self, name: str, question: str, description: str = "") -> None:
        self.name = name
        self.question = question
        self.description = description


BANKING_SLOTS: list[BankingSlot] = [
    BankingSlot(
        name="codigo_bloqueio",
        question="Qual o código de bloqueio exibido? (ex: 'U', '8')",
        description="Código de bloqueio da senha de 6/8 dígitos.",
    ),
    BankingSlot(
        name="alfa_code",
        question="Você possui Alfa Code habilitado? (sim/não)",
        description="Se o cliente tem Alfa Code para alteração via site.",
    ),
    BankingSlot(
        name="biometria_dias",
        question="Há quantos dias a biometria está cadastrada?",
        description="Regra de 7 dias mínimos para validação de segurança.",
    ),
    BankingSlot(
        name="canal_tentado",
        question="Qual canal você tentou usar? (site/app/agência)",
        description="Canal onde o desbloqueio foi tentado.",
    ),
    BankingSlot(
        name="tipo_cliente",
        question="Você é correntista? (sim/não)",
        description="Correntista vs não correntista muda o fluxo.",
    ),
]

_SLOT_BY_NAME = {s.name: s for s in BANKING_SLOTS}

_BLOQUEIO_RE = re.compile(r"bloqueio\s*['\"]([A-Za-z0-9])['\"]", re.IGNORECASE)
# "código de barras" (fatura) não é código de bloqueio: o caractere
# capturado não pode ser continuação de palavra ("d" de "de").
_CODIGO_ISOLADO_RE = re.compile(r"c[oó]digo\s*['\"]?([A-Za-z0-9])(?![A-Za-z0-9])", re.IGNORECASE)
_QUOTED_CODE_RE = re.compile(r"['\"]([A-Za-z0-9])['\"]", re.IGNORECASE)
_BIOMETRIA_RE = re.compile(r"biometria[^0-9]{0,20}(\d+)\s*dias?", re.IGNORECASE)
_DIAS_RE = re.compile(r"(\d+)\s*dias?", re.IGNORECASE)


def extract_slots(text: str, expected_slot: str | None = None) -> dict[str, str]:
    """Extrai slots de um texto livre (pergunta ou resposta do usuário).

    Retorna apenas os slots detectados; ausentes ficam de fora (não None).
    `expected_slot` dá contexto da pergunta de clarificação atual, permitindo
    interpretar respostas curtas ("U", "não", "5 dias"). Função pura.
    """
    found: dict[str, str] = {}
    low = text.lower()
    stripped = text.strip()

    m = _BLOQUEIO_RE.search(text) or _CODIGO_ISOLADO_RE.search(text)
    if m:
        found["codigo_bloqueio"] = m.group(1).upper()
    elif re.search(r"bloqueio\s+['\"]U['\"]|['\"]U['\"].*bloqueio|bloqueio.*['\"]U['\"]", text):
        found["codigo_bloqueio"] = "U"
    elif expected_slot == "codigo_bloqueio":
        # Só aceita código avulso entre aspas (ex: resposta '"8"'); evita
        # capturar letras de palavras como "bloqueio pelo".
        m_quoted = _QUOTED_CODE_RE.search(text)
        if m_quoted and len(stripped) <= 5:
            found["codigo_bloqueio"] = m_quoted.group(1).upper()

    if "alfa code" in low or "alfacode" in low:
        if any(
            neg in low for neg in ["sem alfa", "não tenho alfa", "nao tenho alfa", "não possui"]
        ):
            found["alfa_code"] = "não"
        elif any(pos in low for pos in ["tenho alfa", "possui alfa", "habilitado", "sim"]):
            # "sem alfa" já tratado acima; aqui cobre casos positivos
            if "sem alfa" not in low and "não" not in low.split("alfa")[0][-20:]:
                found["alfa_code"] = "sim"
            else:
                found["alfa_code"] = "não"
        else:
            found["alfa_code"] = "mencionado"
    if "sem alfa code" in low or "não possui alfa" in low:
        found["alfa_code"] = "não"

    m_bio = _BIOMETRIA_RE.search(text)
    if m_bio:
        found["biometria_dias"] = m_bio.group(1)
    elif "biometria" in low:
        m_dias = _DIAS_RE.search(text)
        if m_dias:
            found["biometria_dias"] = m_dias.group(1)

    for canal in ["site", "app", "agência", "agencia"]:
        if canal in low:
            found["canal_tentado"] = "agência" if "agencia" in canal else canal
            break

    if "correntista" in low or "não correntista" in low or "nao correntista" in low:
        if "não correntista" in low or "nao correntista" in low or "não sou correntista" in low:
            found["tipo_cliente"] = "não correntista"
        else:
            found["tipo_cliente"] = "correntista"

    # Fallback contextual para respostas curtas do loop de clarificação.
    if expected_slot and expected_slot not in found:
        if expected_slot == "codigo_bloqueio":
            m_short = re.fullmatch(r"['\"]?([A-Za-z0-9])['\"]?", stripped)
            if m_short:
                found["codigo_bloqueio"] = m_short.group(1).upper()
        elif expected_slot == "alfa_code":
            if stripped.lower() in {"sim", "s", "tenho", "possui", "habilitado"}:
                found["alfa_code"] = "sim"
            elif stripped.lower() in {"não", "nao", "n", "sem", "não tenho"}:
                found["alfa_code"] = "não"
        elif expected_slot == "biometria_dias":
            m_dias = re.fullmatch(r"(\d+)\s*(dias?)?", stripped.lower())
            if m_dias:
                found["biometria_dias"] = m_dias.group(1)
        elif expected_slot == "canal_tentado":
            for canal in ["site", "app", "agência", "agencia"]:
                if canal in low:
                    found["canal_tentado"] = "agência" if "agencia" in canal else canal
                    break
            else:
                if stripped:
                    found["canal_tentado"] = stripped
        elif expected_slot == "tipo_cliente":
            if stripped.lower() in {"sim", "s", "sou", "correntista"}:
                found["tipo_cliente"] = "correntista"
            elif stripped.lower() in {"não", "nao", "n", "não correntista"}:
                found["tipo_cliente"] = "não correntista"
        elif stripped and len(stripped) <= 120:
            # Slot genérico de novo POP: aceita o valor literal para que
            # qualquer cenário simulado flua sem tabela por documento.
            found[expected_slot] = stripped

    return found


def merge_slots(base: dict[str, str], new: dict[str, str]) -> dict[str, str]:
    """Mescla slots sem mutar os originais (spike: sobrescreve com o novo)."""
    merged = dict(base)
    merged.update(new)
    return merged


def find_missing_slots(filled: dict[str, str], extra_slots: list[str] | None = None) -> list[str]:
    """Retorna os slots ainda não preenchidos (canônicos + extras genéricos).

    `extra_slots` carrega chaves simuladas de novos POPs que não estão em
    `BANKING_SLOTS`; elas entram após as canônicas, sem duplicar.
    """
    missing = [s.name for s in BANKING_SLOTS if not filled.get(s.name)]
    if extra_slots:
        for slot in extra_slots:
            if slot not in missing and not filled.get(slot):
                missing.append(slot)
    return missing


def question_for_slot(slot: str) -> str:
    """Pergunta de clarificação para qualquer slot (legado ou genérico)."""
    known = _SLOT_BY_NAME.get(slot)
    if known:
        return known.question
    human = slot.replace("_", " ")
    return f"Por favor, informe {human}?"


def next_clarifying_question(missing: list[str]) -> str | None:
    """Retorna a próxima pergunta de clarificação, ou None se não há pendência."""
    if not missing:
        return None
    return question_for_slot(missing[0])


def should_ask_more(missing: list[str], turns_used: int, max_turns: int) -> bool:
    """Critério de parada: há slots faltando E ainda há turnos disponíveis."""
    return bool(missing) and turns_used < max_turns


def build_enriched_query(original: str, filled: dict[str, str]) -> str:
    """Monta a query enriquecida para o grafo a partir dos slots coletados.

    Formato legado `k=v` preservado byte-igual (testes e runs históricas
    dependem da substring); ver `build_routed_query()` para o bloco
    adicional em linguagem natural.
    """
    if not filled:
        return original
    parts = [f"{k}={v}" for k, v in sorted(filled.items())]
    return f"{original}\n[Dados coletados via clarificação: {'; '.join(parts)}]"


def build_routed_instruction(
    filled: dict[str, str],
    route_doc: str | None = None,
    margin: float | None = None,
    mode: str | None = None,
    top_k: int | None = None,
) -> str:
    """Instrução em linguagem natural com tudo que a IA precisa (pura).

    Traduz o `k=v` máquina para frases + rota prevista, para a IA não
    precisar adivinhar o significado dos códigos.
    """
    if not filled:
        facts = "Nenhum dado adicional foi coletado; responda com o contexto."
    else:
        phrases = [f"{k.replace('_', ' ')} é '{v}'" for k, v in sorted(filled.items())]
        facts = "O cliente informou que " + "; ".join(phrases) + "."
    route = ""
    if route_doc:
        detail = f"Rota prevista: {route_doc}"
        extras = []
        if margin is not None:
            extras.append(f"margem {margin:.4f}")
        if mode is not None and top_k is not None:
            extras.append(f"estratégia {mode}/k{top_k}")
        if extras:
            detail += f" ({', '.join(extras)})"
        detail += ". Trate os dados coletados como fatos verdadeiros."
        route = " " + detail
    return (
        "[Resumo para o assistente: "
        f"{facts}{route} Responda estritamente com base no contexto "
        "recuperado e nesses fatos.]"
    )


def build_routed_query(
    original: str,
    filled: dict[str, str],
    route_doc: str | None = None,
    margin: float | None = None,
    mode: str | None = None,
    top_k: int | None = None,
) -> str:
    """Query roteada completa: legada `k=v` + bloco natural aditivo (pura).

    A primeira linha após o original é sempre a legada, para compatibilidade
    com probes e testes que buscam `"k=v" in enriched`.
    """
    base = build_enriched_query(original, filled)
    if not filled:
        return base
    return f"{base}\n{build_routed_instruction(filled, route_doc, margin, mode, top_k)}"


def clarify_history_turn(question: str, answer: str) -> list[dict[str, str]]:
    """Um turno de clarificação como mensagens de histórico (puro)."""
    return [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
