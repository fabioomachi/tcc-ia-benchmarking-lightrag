"""Chatbot tradicional por árvore de decisão: POPs codificadas à mão.

Braço simbólico do TCC: zero LLM, zero grafo, zero retrieval. As regras dos
oito POPs viram ramos `if/elif` com templates de resposta redigidos a partir
dos trechos normativos (cada ramo cita a seção do POP em comentário).
Slot faltante → pergunta de esclarecimento; nada casou → fallback honesto
"não coberto", nunca chute. Tudo puro e determinístico (testável sem rede).
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import numpy as np

from ragbench.config import BenchmarkSettings, get_settings
from ragbench.conversational.clarifier import extract_slots, find_missing_slots
from ragbench.conversational.router import next_discriminative_slot
from ragbench.core.interfaces import BaseRAGPipeline
from ragbench.core.models import SearchMode
from ragbench.infrastructure.logging import get_logger

logger = get_logger("ragbench.engine.tree")

TREE_VERSION = "pop-v2.0"
TREE_MODEL_NAME = "decision-tree-pop-v1"

FALLBACK_ANSWER = (
    "Não tenho regra codificada para este caso nos 8 POPs (senhas, CDC, "
    "cartões/SAC, fatura por e-mail, INSS/benefícios, limites do cartão, "
    "bloqueio judicial, Alfa Rende Fácil). Diga o assunto (ex: contestação "
    "de compra, código de barras, benefício INSS, limite, bloqueio judicial, "
    "adesão) ou procure uma agência."
)

ACESSO_KEYWORDS = (
    "senha",
    "bloqueio",
    "desbloqueio",
    "alfa code",
    "alfacode",
    "biometria",
    "conta de acesso",
    "senha-8",
    "codigo de acesso",
    "titular",
    "solidari",
    "taa",
    "chip",
    "sms",
    "portador adicional",
    "exterior",
    "toquio",
    "deficiente visual",
)
CDC_KEYWORDS = (
    "cdc",
    "parcela",
    "boleto",
    "consign",
    "amortiz",
    "liquid",
    "cancelamento",
    "renova",
    "limite especial",
    "reaverb",
    "convenio",
    "convênio",
    "anc",
    "margem",
    "fraude",
    "correspondente",
    "fatura",
    "fgts",
    "irpf",
    "13º",
    "13o",
    "decimo",
    "repactu",
    "autoriza",
    "debito",
    "contracheque",
    "descont",
    "folha",
    "salario",
    "doc 800020",
)


CARTOES_KEYWORDS = (
    "cartao",
    "sac",
    "contestacao",
    "desacordo",
    "falsidade",
    "ppf",
    "parcelado",
    "contratacao",
    "nfc",
    "contactless",
    "carteiras digitais",
    "segunda via",
    "anuidade",
    "alfa-e",
    "virtual",
    "seguros",
    "fisico",
    "portabilidade",
    "fraude",
)

FATURA_KEYWORDS = (
    "fatura",
    "email",
    "reenvio",
    "codigo de barras",
    "boleto",
    "whatsapp",
    "impressa",
    "inibir",
    "token",
    "ura",
    "siscad",
    "sisneg",
    "cadastro",
    "emit",
    "spam",
    "endereco",
)

INSS_KEYWORDS = (
    "inss",
    "sispag",
    "beneficio",
    "pasep",
    "recadastramento",
    "auxilio",
    "extrato",
    "ini.pgto",
    "disponib",
    "conta-beneficio",
    "nao disponivel",
    "convenio",
    "encaminhado",
)

LIMITES_KEYWORDS = (
    "limite",
    "anc vigente",
    "50190",
    "17.01.01",
    "aumento de limite",
    "reducao de limite",
    "token",
    "ura",
    "50148",
)

JUDICIAL_KEYWORDS = (
    "judicial",
    "sisjud",
    "juizo",
    "vara",
    "tribunal",
    "protocolo",
    "proventos",
    "previdenciario",
    "ordem",
    "fcr",
    "recebe proventos",
)

ALFA_KEYWORDS = (
    "rende facil",
    "duplo sim",
    "cdb",
    "aplicacao automatica",
    "adesao",
    "30 dias",
    "pendentes de confirmacao",
)

NEW_DOC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "POP_Cartoes_SAC_anonimizado.md": CARTOES_KEYWORDS,
    "POP_Fatura_Envio_Email_anonimizado.md": FATURA_KEYWORDS,
    "POP_INSS_Beneficios_Sociais_anonimizado.md": INSS_KEYWORDS,
    "POP_Limites_Cartao_Credito_PF_anonimizado.md": LIMITES_KEYWORDS,
    "POP_Bloqueio_Judicial_anonimizado.md": JUDICIAL_KEYWORDS,
    "POP_Alfa_Rende_Facil_Adesao_anonimizado.md": ALFA_KEYWORDS,
}


@dataclass(frozen=True)
class Decision:
    """Resultado puro da árvore para uma pergunta."""

    answer: str
    branch: str
    doc: str  # um dos 8 POPs indexados, ou ""
    confident: bool
    missing: tuple[str, ...] = ()


def _norm(text: str) -> str:
    from ragbench.conversational.router import normalize

    return normalize(text)


def _count_keywords(norm: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for k in keywords if k in norm)


def detect_doc(filled: dict[str, str], norm: str) -> str:
    """Qual POP a pergunta pertence (slots acesso-específicos decidem primeiro).

    Regra de desempate que preserva o legado: um POP novo só vence se superar
    ESTRITAMENTE e com folga única a pontuação de acesso/CDC; empates com os
    legados mantêm acesso/CDC, empates entre novos devolvem "" (honesto).
    """
    # "bloqueio"/"desbloqueio" pertencem ao POP de Senhas, salvo quando há
    # marcadores judiciais explícitos (senão todo bloqueio judicial vira acesso).
    acesso_kws = ACESSO_KEYWORDS
    if any(
        k in norm
        for k in ("judicial", "sisjud", "juizo", "proventos", "previdenciario", "vara", "tribunal")
    ):
        acesso_kws = tuple(k for k in ACESSO_KEYWORDS if k not in ("bloqueio", "desbloqueio"))
    n_acesso = _count_keywords(norm, acesso_kws)
    n_cdc = _count_keywords(norm, CDC_KEYWORDS)
    # "anc" como substring casa em "banco"/"cancelar" (mesma armadilha que o
    # ramo CDC_ANC_SEM_LIMITE já trata com \b): só conta com fronteira de palavra.
    if "anc" in norm and not re.search(r"\banc\b", norm):
        n_cdc -= 1
    new_scores = {doc: _count_keywords(norm, kws) for doc, kws in NEW_DOC_KEYWORDS.items()}
    max_other = max([n_cdc, *new_scores.values()])
    # Atalho por slots acesso-específicos — ignorado se for falso positivo do
    # extrator (ex: '7' de '700002', 'D' de 'débito'): evidência forte (≥2 hits
    # e maior que a de acesso) de outro POP prevalece.
    if any(filled.get(s) for s in ("codigo_bloqueio", "alfa_code", "biometria_dias")):
        if not (max_other >= 2 and max_other > n_acesso):
            return "pop_acesso_pf.md"
    legacy = ""
    legacy_score = 0
    if n_acesso > n_cdc:
        legacy, legacy_score = "pop_acesso_pf.md", n_acesso
    elif n_cdc > n_acesso:
        legacy, legacy_score = "pop_cdc_pf.md", n_cdc
    best_doc = max(new_scores, key=lambda d: new_scores[d])
    best_score = new_scores[best_doc]
    unique = sum(1 for s in new_scores.values() if s == best_score) == 1
    if best_score > legacy_score and unique:
        return best_doc
    return legacy


def _bio_dias(filled: dict[str, str]) -> int | None:
    try:
        return int(str(filled.get("biometria_dias", "")).strip())
    except (ValueError, TypeError):
        return None


def decide_acesso(filled: dict[str, str], norm: str) -> Decision:  # noqa: C901, PLR0912
    """Ramos do POP de Senhas e Código de Acesso (pop_acesso_pf.md)."""
    cod = str(filled.get("codigo_bloqueio", "")).upper()
    alfa = str(filled.get("alfa_code", "")).lower()
    dias = _bio_dias(filled)
    canal = _norm(str(filled.get("canal_tentado", "")))

    # §3.1.4: bloqueio "U" não admite desbloqueio, só alteração.
    if cod == "U" and ("site" in norm or canal == "site"):
        # §3.1.2: site veda U/8 sem Alfa; biometria exige >7 dias.
        if alfa in ("não", "nao", "") or (dias is not None and dias < 7):
            return Decision(
                "Bloqueio 'U' não admite desbloqueio, só alteração (§3.1.4). "
                "O site institucional não permite alterar senha com bloqueio "
                "'U' ou '8' sem Alfa Code, e a biometria exige mais de 7 dias "
                "(§3.1.2). Regularize presencialmente em uma agência, "
                "alterando primeiro a senha de 8 dígitos e depois a de 6.",
                "ACESSO_U_SITE_AGENCIA",
                "pop_acesso_pf.md",
                True,
            )
    if cod == "U":
        return Decision(
            "Bloqueio 'U' (monitoramento de segurança) não admite desbloqueio, "
            "só alteração (§3.1.4, §3.2.4). Procure uma agência (inclusive com "
            "bloqueio 'U', §3.1.2) ou, fora 'U', os canais de alteração: App, "
            "TAA com biometria há mais de 7 dias, site com Alfa Code.",
            "ACESSO_U_GERAL",
            "pop_acesso_pf.md",
            True,
        )
    # §3.2.2/§3.2.4: bloqueio "8" da senha de 8 dígitos.
    if cod == "8":
        return Decision(
            "Bloqueio '8' (agência ou autoatendimento) segue alteração: sem a "
            "senha atual, use App 'Esqueci minha senha', TAA (com ou sem senha, "
            "inclusive bloqueios) ou agência (§3.2.2). Sem senha anterior e com "
            "'U' ou '4', siga a Alteração, não o Desbloqueio (§3.2.4).",
            "ACESSO_8_ALTERACAO",
            "pop_acesso_pf.md",
            True,
        )
    # §4.2.2: sequestro + Senha-8 vs Conta de Acesso.
    if any(w in norm for w in ("assalto", "roubo", "sequestr")):
        return Decision(
            "Em assalto, roubo ou sequestro, contate SAC QP/QC ou a Plataforma "
            "de Relacionamento para a rotina de segurança no SISRET X98, "
            "código de rota 800050, informando a conta do cartão (§4.2.2). O "
            "bloqueio da Senha-8 (App Cartão Alfa) não bloqueia a Conta de "
            "Acesso (App Alfa): são credenciais distintas.",
            "ACESSO_SEQUESTRO_X98",
            "pop_acesso_pf.md",
            True,
        )
    # Nota (c): titulares solidários compartilham senhas.
    if "solidari" in norm or "marido" in norm or "titular" in norm:
        return Decision(
            "Titulares solidários compartilham as mesmas senhas de 6 e 8 "
            "dígitos e o código de acesso: o bloqueio por um titular impede os "
            "demais de transacionar (Nota inicial c). Regularize por alteração "
            "das senhas; agência resolve inclusive bloqueio 'U'.",
            "ACESSO_SOLIDARIO",
            "pop_acesso_pf.md",
            True,
        )
    # §5.a: dispensa do código para deficientes visuais.
    if "visual" in norm or "deficiente" in norm:
        return Decision(
            "Cliente com deficiência visual total pode ser dispensado do "
            "código de acesso, mediante registro da característica no cadastro "
            "pela agência (§5.a). Em conta conjunta, a dispensa vale só para o "
            "titular com a deficiência.",
            "ACESSO_DEFICIENTE_CODIGO",
            "pop_acesso_pf.md",
            True,
        )
    # §7: exterior + bloqueio U (e-mail não vale para U).
    if "exterior" in norm or "fora do pais" in norm or "toquio" in norm:
        return Decision(
            "No exterior, use a Central de Senhas no App Alfa (cartão ativo, "
            "dispositivo liberado, Alfa Code/Push). Agências no exterior só "
            "operam senhas em Tóquio (§7). A declaração por e-mail do MCI vale "
            "só para bloqueio por erro, nunca para bloqueio 'U' (fraude); "
            "neste caso, use representante legal com procuração no Brasil.",
            "ACESSO_EXTERIOR_U",
            "pop_acesso_pf.md",
            True,
        )
    # §8: portador adicional não correntista.
    if "adicional" in norm:
        return Decision(
            "Portador adicional não correntista cadastra nova senha de 6 "
            "dígitos presencialmente em qualquer agência (§8). Adicional "
            "correntista usa a própria senha da sua conta.",
            "ACESSO_ADICIONAL",
            "pop_acesso_pf.md",
            True,
        )
    # §6: SMS só para alteração.
    if "sms" in norm:
        return Decision(
            "Envio de senha por SMS serve só para ALTERAÇÃO, nunca para "
            "primeira senha 'não cadastrada/a cadastrar' (§6). Neste caso: 8 "
            "dígitos via App Alfa (dispositivo autorizado com Alfa Code/push) "
            "e 6 dígitos presencial na agência.",
            "ACESSO_SMS_ALTERACAO",
            "pop_acesso_pf.md",
            True,
        )
    # §3.1.2: chip precisa de atualização na TAA.
    if "chip" in norm:
        return Decision(
            "Após alterar a senha de 6 dígitos de cartão com chip, atualize o "
            "chip em qualquer TAA, ou a nova senha não funciona no presencial "
            "(§3.1.2). Carteiras digitais seguem normais após a troca.",
            "ACESSO_CHIP_TAA",
            "pop_acesso_pf.md",
            True,
        )
    # §2.2: código Q aguarda TAA com biometria >7 dias.
    if "codigo q" in norm or ("'q'" in norm) or ('"q"' in norm):
        return Decision(
            "Código 'Q' indica alteração pendente de confirmação na TAA com "
            "biometria cadastrada há mais de 7 dias (§2.2). Abaixo disso, "
            "aguarde completar 7 dias ou use atendimento assistido.",
            "ACESSO_CODIGO_Q",
            "pop_acesso_pf.md",
            True,
        )
    # §4.2.1/§4.2.2: Conta de Acesso vs Senha-8.
    if "app alfa" in norm and ("senha" in norm or "acesso" in norm):
        return Decision(
            "Conta de Acesso (App Alfa) e Senha-8 (App Cartão Alfa) são "
            "credenciais distintas: quem tem só Senha-8 não entra no App Alfa "
            "(§4.2.2). Identifique o tipo via SISRET X69 ou Plataforma "
            "Gerenciamento de Senhas 3.0 (§4.2.1) e cadastre senha separada "
            "via 'Esqueci senha' para o outro app.",
            "ACESSO_CONTA_VS_SENHA8",
            "pop_acesso_pf.md",
            True,
        )
    # §3.1.2/§3.2.2: alçadas do SAC para bloqueio U (código pode vir sem
    # aspas na pergunta curta; "bloqueio" no texto já qualifica).
    if "sac" in norm and (cod in ("U", "8") or "bloqueio" in norm):
        return Decision(
            "Bloqueio 'U': SAC Receptivo QP → Célula de Segurança (rotina "
            "50130); SAC Soluções QP → 50131; SAC QC → 50112 (§3.1.2, §3.2.2). "
            "Não use geração de senha comum para 'U'.",
            "ACESSO_SAC_ALCADA_U",
            "pop_acesso_pf.md",
            True,
        )
    # §3.1.2: site sem Alfa + biometria >7 dias é permitido.
    if ("site" in norm or canal == "site") and alfa in ("não", "nao"):
        if dias is not None and dias >= 7:
            return Decision(
                "Sem Alfa Code, o site permite alterar a senha de 6 dígitos "
                "com confirmação em TAA com biometria há mais de 7 dias "
                "(§3.1.2). Com menos de 7 dias, ou bloqueio 'U'/'8', o site "
                "não permite — use agência ou TAA.",
                "ACESSO_SITE_BIOMETRIA_OK",
                "pop_acesso_pf.md",
                True,
            )
        return Decision(
            "Sem Alfa Code, o site exige confirmação em TAA com biometria há "
            "mais de 7 dias (§3.1.2). Informe há quantos dias a biometria está "
            "cadastrada para seguir.",
            "ACESSO_SITE_BIOMETRIA_PENDENTE",
            "pop_acesso_pf.md",
            False,
        )
    # Genérico de acesso quando o doc foi detectado.
    return Decision(
        "Pelo POP de Senhas: 6 dígitos confirma transações e acessos; 8 "
        "dígitos acessa site/App; código de acesso serve à TAA/Banco24H. "
        "Alteração: App (celular >30 dias + Alfa Code/Push), site (com Alfa "
        "ou TAA + biometria >7 dias), TAA ou agência (inclusive 'U'). "
        "Bloqueio 'U' só altera, nunca desbloqueia.",
        "ACESSO_GENERICO",
        "pop_acesso_pf.md",
        True,
    )


def decide_cdc(filled: dict[str, str], norm: str) -> Decision:  # noqa: C901, PLR0912
    """Ramos do POP de CDC (pop_cdc_pf.md)."""
    # §4: cancelamento linha 2881 por convênio.
    if "2881" in norm or "renovacao" in norm or "renovação" in norm:
        if "700017" in norm or "convenio 17" in norm or "convênio 17" in norm:
            return Decision(
                "Cancelamento da linha 2881 para o Convênio Especial 17 "
                "(700017) é restrito à Superintendência Regional III (código "
                "800030), ver rotina 50108 (§4).",
                "CDC_CANCEL_2881_C17",
                "pop_cdc_pf.md",
                True,
            )
        return Decision(
            "Cancelamento da linha 2881 (Renovação Consignação), convênios "
            "700001–700016, é restrito ao DOC – Diretoria de Operações de "
            "Crédito (800020). É preciso haver margem para reaverbação das "
            "operações vinculadas (§4). Atendente não cancela direto.",
            "CDC_CANCEL_2881_DOC",
            "pop_cdc_pf.md",
            True,
        )
    # §2 CDC Automático: duplicidade boleto + débito.
    if "duplic" in norm or ("boleto" in norm and ("debito" in norm or "conta" in norm)):
        return Decision(
            "Confirmada duplicidade sem estorno (campo 'Dt. Canc.' vazio): "
            "estorne primeiro o Boleto Bancário e depois o Recebimento "
            "Automático, só sem débitos pendentes e sem gerar saldo devedor "
            "ou atraso. Supervisor recebe o valor correto em CDC 13.23; "
            "confirme a data retroativa em CDC 13.61 (§2, CDC Automático).",
            "CDC_DUPLICIDADE_BOLETO",
            "pop_cdc_pf.md",
            True,
        )
    # §5.1: linear vedado no consignado (antes do ramo consignação, que é
    # mais genérico e o engoliria).
    if "linear" in norm:
        return Decision(
            "Amortização linear é vedada para CDC Consignado (e para operações "
            "fora do status Normal, com pagamento parcial, em cobrança ou com "
            "Pula-Parcela, §5.1). Para Consignação/Renovação prefira ordem "
            "decrescente, evitando duplicidade em folha.",
            "CDC_LINEAR_VEDADO",
            "pop_cdc_pf.md",
            True,
        )
    # §2 Consignação: prazos de devolução.
    if "consign" in norm or "inss" in norm or "mpdg" in norm or "900001" in norm:
        return Decision(
            "Liquidado/renovado com consignação indevida: estorno automático "
            "em conta em até D+2 dias úteis, exceto convênio 900001 (INSS, a "
            "partir do 5º dia útil) e 900002 (MPDG, até o 1º dia útil). "
            "Confirme em CDC 15.13 e SISCONSIG 22.01.01 (§2, Consignação).",
            "CDC_CONSIG_DEVOLUCAO",
            "pop_cdc_pf.md",
            True,
        )
    # §5.2: operações em perdas.
    if "perdas" in norm or "prejuizo" in norm or "prejuízo" in norm:
        return Decision(
            "Não informe ao cliente que a operação está em prejuízo (§5.2). "
            "Com saldo suficiente: liquidação via CDC 13-34 com supervisor em "
            "CDC 13-36; parcial via CDC 13-35 com gerente de grupo. Boleto "
            "exige ocorrência.",
            "CDC_PERDAS",
            "pop_cdc_pf.md",
            True,
        )
    # §3: ANC vencida / sem limite. "anc" com fronteira de palavra: "cancelar"
    # contém "anc" e não pode casar aqui.
    if re.search(r"\banc\b", norm) or (
        "limite" in norm and ("sem limite" in norm or "renda" in norm)
    ):
        return Decision(
            "Sem limite (ANC vencida/impedida/cancelada ou margem zerada): "
            "oriente ida a qualquer agência com RG/CPF e comprovantes de "
            "residência e renda de menos de 90 dias; ver rotina 50105 para "
            "restabelecimento (§3).",
            "CDC_ANC_SEM_LIMITE",
            "pop_cdc_pf.md",
            True,
        )
    # §7.2: fraude via correspondente.
    if "fraude" in norm or "correspondente" in norm or "golpe" in norm:
        return Decision(
            "Registre ocorrência e responsabilize correspondentes/antifraude "
            "(800010): 50113 (não reconhecida/divergente), 50114 (suspeita de "
            "fraude/golpe com transferência a terceiros), 50115 (pendente de "
            "confirmação). Produto/modalidade é obrigatório no registro "
            "(§7.2).",
            "CDC_FRAUDE_CORRESPONDENTE",
            "pop_cdc_pf.md",
            True,
        )
    # §8.1: limite em uso.
    if "limite especial" in norm and ("cancel" in norm or "usando" in norm):
        return Decision(
            "Com o Limite Especial em uso não cancele: oriente cobrir o saldo "
            "(sonde o motivo; ofereça reduzir a R$ 100; sem tarifa). Com saldo "
            "e autenticação, cancele na plataforma com deferimento do "
            "supervisor; em Ouvidoria, cancele direto sem sondagem (§8.1).",
            "CDC_LIMITE_CANCELAMENTO",
            "pop_cdc_pf.md",
            True,
        )
    # §2 13º: aniversário.
    if "13" in norm and ("aniversario" in norm or "aniversário" in norm):
        return Decision(
            "Com convênio, o CDC 13º debita na data de cobrança ou no "
            "vencimento (30 dias após o crédito), o que ocorrer primeiro; se "
            "vinculado ao aniversário, ambos caem no mês de aniversário. Sem "
            "convênio, debita no vencimento contratado (§2, 13º Salário).",
            "CDC_13_ANIVERSARIO",
            "pop_cdc_pf.md",
            True,
        )
    # §2 IRPF vs FGTS.
    if "irpf" in norm or "ir " in norm or "restituicao" in norm or "fgts" in norm:
        return Decision(
            "IRPF: debita na data prevista do crédito da restituição ou no "
            "vencimento, se o crédito não vier antes. FGTS Saque Aniversário: "
            "liquidação automática via repasse do FGTS; débito em conta só se "
            "o repasse for insuficiente (§2).",
            "CDC_IRPF_FGTS",
            "pop_cdc_pf.md",
            True,
        )
    # §4.4: repactuação.
    if "repactu" in norm:
        return Decision(
            "Com 'Op' pendente de confirmação no CDC 15.13, pode excluir a "
            "repactuação; se confirmada, só liquidação/pagamento total (§4.4). "
            "Convênio Especial 17 tem repactuação com suspensão (50109).",
            "CDC_REPACTUACAO",
            "pop_cdc_pf.md",
            True,
        )
    # Rotina 50104: autorização pós-01/03/21.
    if "autoriza" in norm or "01/03" in norm or "4790" in norm or "4.790" in norm:
        return Decision(
            "Desde 01/03/2021 o débito em conta exige autorização específica "
            "do cliente (Resolução CMN 4.790/2020). Sem autorização indicada, "
            "siga a rotina 50104 (§5.1, Obs. iniciais).",
            "CDC_AUTORIZACAO_2021",
            "pop_cdc_pf.md",
            True,
        )
    # Genérico de CDC quando o doc foi detectado.
    return Decision(
        "Pelo POP de CDC: consultas em CDC 15.18; cancelamento em até 7 dias "
        "corridos só para autoatendimento (presencial só no mesmo dia, §4); "
        "amortização/liquidação com leitura obrigatória e confirmação do "
        "supervisor (§5.1); fraude via correspondente gera ocorrência 50113–"
        "50115 (§7.2). Informe a operação e o canal para a regra exata.",
        "CDC_GENERICO",
        "pop_cdc_pf.md",
        True,
    )


def decide_cartoes(filled: dict[str, str], norm: str) -> Decision:  # noqa: C901, PLR0912
    """Ramos do POP SAC Cartões (POP_Cartoes_SAC_anonimizado.md)."""
    # §12 débito: fraude transfere ao Antifraude/ROI (antes do ramo genérico).
    if "debito" in norm and ("antifraude" in norm or "roi" in norm):
        return Decision(
            "Débito não reconhecido (fraude): transfira ao SAC Antifraude/ROI. "
            "Compra reconhecida no débito: item 2 da 50176 (§12).",
            "CARTOES_DEBITO_FRAUDE",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # §12: fraude no crédito não reconhecida (Token mesmo autenticado).
    if "fraude" in norm or "contestacao" in norm or "376" in norm:
        return Decision(
            "Compra no crédito não reconhecida (suspeita de fraude): valide por "
            "Token (50148) mesmo com cliente autenticado. Se falhar, bloqueio "
            "provisório no cartão — e definitivo código 376 se for Cartão "
            "Alfa-e falsificado. Conteste pela 50174, registre no SRO (FCR) e "
            "informe ao cliente o protocolo do SRO e o gerado pelo SISALFA "
            "para acompanhar (§12). Dúvida sobre Push: recurso 'Alfa, Sou Eu'.",
            "CARTOES_CONTESTACAO_FRAUDE",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # Notas (e) + item 24: SAC não contrata PPF.
    if "ppf" in norm or "parcelado" in norm:
        return Decision(
            "O SAC não contrata PPF: informe os canais da tabela do item 1 da "
            "50156. Consultas, cancelamento e antecipação de PPF seguem a "
            "própria 50156 (Notas e, item 24).",
            "CARTOES_PPF",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # Item 24: NFC/Contactless.
    if "nfc" in norm or "contactless" in norm or "aproximacao" in norm:
        return Decision(
            "Pagamento por aproximação (NFC/Contactless): rotina 50197; para "
            "ativar/desativar a insistência do cliente, siga a rotina (item 24).",
            "CARTOES_NFC",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # §12: desacordo comercial (reconhece a compra).
    if "desacordo" in norm or "encargos" in norm:
        return Decision(
            "Desacordo comercial, encargos ou andamento de contestação já feita "
            "(compra reconhecida, sem fraude): rotina 50175 (§12).",
            "CARTOES_DESACORDO",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # Item 41: segunda via (canais + tarifa).
    if "segunda via" in norm:
        return Decision(
            "Segunda via do cartão: App Alfa, App Cartão Alfa, site (área "
            "logada), Plataforma de Relacionamento (setor cartões) ou agências "
            "(item 41, 50217). Tarifa de 2ª via segue a mesma rotina.",
            "CARTOES_SEGUNDA_VIA",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # Item 4: anuidade PF.
    if "anuidade" in norm:
        return Decision(
            "Anuidade PF: oriente pela 50161; se pedir negociação/estorno ou "
            "cancelamento do cartão, siga a mesma rotina (item 4).",
            "CARTOES_ANUIDADE",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # §39: seguros por bandeira.
    if "seguro" in norm and ("viagem" in norm or "visa" in norm or "master" in norm):
        return Decision(
            "Seguros de viagem: identifique bandeira e modalidade (§39). Visa: "
            "acidentes e médico 50209, locação 50211; Master: acidentes 50210, "
            "locação 50212; Visa Infinite proteção de compras 50213; demais "
            "assistências 50214 (Visa/Master/Elo) e 50215 (Master).",
            "CARTOES_SEGUROS",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # Item 7: bloqueio/inibição/cancelamento/reativação de cartões.
    if "bloque" in norm and "cartao" in norm:
        return Decision(
            "Bloqueio de cartão (perda, roubo, TAA): rotina 50164 — avise que "
            "também dá pelo App Alfa/App Cartão Alfa. Inibir crédito: 50165; "
            "cancelar: 50166; desistência/reativação: itens 4 e 5 da 50167 "
            "(item 7).",
            "CARTOES_BLOQUEIO",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # Item 26 + Notas (e): contratação e adicional só por canais.
    if "contratacao" in norm or "contratar" in norm:
        return Decision(
            "SAC não contrata cartão: correntistas (Visa/Elo) e não correntistas "
            "via App Alfa, agências ou TAA, conforme modalidade (item 26, "
            "50153). Adicional: só canais do item 5 da 50155 (Notas e).",
            "CARTOES_CONTRATACAO",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    # §23: limites físico e virtual.
    if "limite" in norm:
        return Decision(
            "Limites do físico e do Alfa-e virtual: máximos diários/compras/"
            "saques 50189; consultar disponível 50150 item 2; aumentar/reduzir "
            "50190 item 1; virtual 50191 item 1.1.1; transferência com Limite "
            "Especial 50192 (§23).",
            "CARTOES_LIMITES",
            "POP_Cartoes_SAC_anonimizado.md",
            True,
        )
    return Decision(
        "Pelo SAC Cartões: contestação com fraude usa Token + 50174 (§12); "
        "PPF o SAC não contrata (50156); fatura e pagamentos seguem 50182–"
        "50185/50195; segunda via e anuidade têm canais próprios (50217/50161). "
        "Diga o assunto (nº do índice 1–42) para a rotina exata.",
        "CARTOES_GENERICO",
        "POP_Cartoes_SAC_anonimizado.md",
        True,
    )


def decide_fatura(filled: dict[str, str], norm: str) -> Decision:  # noqa: C901, PLR0912
    """Ramos do POP de Fatura por e-mail (POP_Fatura_Envio_Email_anonimizado.md)."""
    # Item 6: código de barras exige Token.
    if "codigo de barras" in norm or "boleto" in norm:
        return Decision(
            "Código de barras exige Token validado (50148): sem sucesso, indique "
            "os canais da 50182. Informe +11 zeros no fim (14 dígitos no último "
            "campo), valor e vencimento. Canais: site, App Alfa, WhatsApp Alfa "
            "('Código de Barras') e rodapé do extrato na TAA (Item 6).",
            "FATURA_CODIGO_BARRAS",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    # Item 4: não recebeu a impressa (SIM/EML/NÃO + motivos).
    if ("nao receb" in norm or "motivo" in norm) and (
        "impressa" in norm or "emit" in norm or "fatura" in norm
    ):
        return Decision(
            "Verifique em SISALFA 17.01.01.01 (coluna 'Emit', 'M' = motivo): SIM "
            "impressa, EML e-mail, NÃO não emitida. Motivos comuns: endereço "
            "inválido; débito automático < R$ 800,01 (inibe a impressa, por "
            "e-mail recebe qualquer valor); saldo zero/credor; negociação no "
            "SISNEG; cobrança terceirizada (Item 4). Anteriores: WhatsApp Alfa.",
            "FATURA_NAO_RECEBIDA",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    # §1.1 Opção B: e-mail alternativo exige Token + oferece cadastro.
    if "opcao b" in norm or "alternativo" in norm or "outro" in norm:
        return Decision(
            "Opção B (e-mail diferente do cadastrado): Token obrigatório mesmo "
            "autenticado; validado, ofereça cadastrar/atualizar o e-mail (1.3). "
            "Sem Token: só canais da 50182. PDF chega em ~2 min ('Segunda Via "
            "Fatura', senha = 5 primeiros dígitos do CPF); confira spam (§1.1).",
            "FATURA_OPCAO_B",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    # §1.1 Opção A: e-mail cadastrado (autenticado OU Token).
    if "opcao a" in norm or "cadastrado" in norm:
        return Decision(
            "Opção A (e-mail já cadastrado): cliente autenticado OU validado por "
            "Token. Envie todas as faturas de modalidades diferentes num só "
            "contato; informe conta cartão, modalidade e bandeira (§1.1).",
            "FATURA_OPCAO_A",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    # §1.2: mudança definitiva (duplo sim, 7 dias, SISCAD).
    if "mudanca" in norm or "definitiva" in norm or "duplo sim" in norm or "siscad" in norm:
        return Decision(
            "Mudança definitiva (17.01.01.04.41.19 → 'COM emissão via e-mail'): "
            "gera duplo sim a confirmar em 7 dias (App/AAPF/TAA); 'não "
            "habilitado' → SISCAD 06.11 (3 campos N→S, avisa sobre promoções). "
            "Vale da próxima fatura a fechar (§1.2).",
            "FATURA_MUDANCA_DEFINITIVA",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    # Segurança: sem URA/Token não envia nem altera.
    if "token" in norm or "ura" in norm or "autentic" in norm:
        return Decision(
            "Sem URA, envie Token (50148); sem Token validado, NÃO envie a "
            "fatura nem altere a forma de envio — só autoatendimento (50182). "
            "Dúvidas de lançamentos/valores: 50149 (processo inicial).",
            "FATURA_TOKEN_OBRIGATORIO",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    # §1.3: atualização de e-mail.
    if "atualiz" in norm and "email" in norm:
        return Decision(
            "Atualizar e-mail PF: Token (50148); com sucesso, SAC Próprio/QC "
            "Especializado/Generalista/Bancada atualizam em "
            "17.01.01.04.41.18 (sem duplo sim). Site/App/Plataforma/agências "
            "também atualizam (50220 item 3); PJ: Alfa Digital PJ (§1.3).",
            "FATURA_ATUALIZAR_EMAIL",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    # Item 2: inibir impressa; Item 3: reativar.
    if "inibir" in norm or "sustentab" in norm:
        return Decision(
            "Inibir a impressa: agilidade, sustentabilidade e segurança com "
            "senha (Item 2). Reativar: confira endereço; se correto, "
            "17.01.01.04.41.19 'Com emissão' (próximo ciclo, correio) e ofereça "
            "o reenvio por e-mail (Item 3).",
            "FATURA_INIBIR_REATIVAR",
            "POP_Fatura_Envio_Email_anonimizado.md",
            True,
        )
    return Decision(
        "Fatura por e-mail: reenvio atual (Opção A/B, §1.1), mudança definitiva "
        "com duplo sim (§1.2), código de barras e não recebimento (Itens 6 e "
        "4) — tudo com Token validado (50148). Diga a demanda exata.",
        "FATURA_GENERICO",
        "POP_Fatura_Envio_Email_anonimizado.md",
        True,
    )


def decide_inss(filled: dict[str, str], norm: str) -> Decision:
    """Ramos do POP INSS/Benefícios (POP_INSS_Beneficios_Sociais_anonimizado.md)."""
    # §2.1: benefício não disponível (antes do ramo de valores: "valores"
    # aparece em perguntas de indisponibilidade sem ser o tema).
    if "nao disponivel" in norm or "indispon" in norm:
        return Decision(
            "Benefício NÃO DISPONÍVEL: informe que não está liberado para saque "
            "e oriente a procurar o órgão responsável pelo motivo. Extrato em "
            "18>47 F4 (movimentações atualizam no dia seguinte) (§2.1).",
            "INSS_INDISPONIVEL",
            "POP_INSS_Beneficios_Sociais_anonimizado.md",
            True,
        )
    # §2.1: INSS informa disponibilidade SEM valores; Outros informam valor.
    if "inss" in norm or "encaminhado" in norm or "ini.pgto" in norm:
        return Decision(
            "Convênio INSS: informe a disponibilidade, SEM valor disponível nem "
            "encaminhado — valores no App Alfa, TAA, site ou Meu INSS. Outros "
            "benefícios: o valor PODE ser informado. Ini.pgto = início da "
            "disponibilidade; pagamento em branco = disponível não movimentado; "
            "preenchida = dia da 1ª movimentação (§2.1, SISPAG 18>41 F4).",
            "INSS_VALORES",
            "POP_INSS_Beneficios_Sociais_anonimizado.md",
            True,
        )
    # §2.1: localizar número/extrato.
    if "sispag" in norm or "extrato" in norm or "numero do beneficio" in norm:
        return Decision(
            "Número do benefício: SISPAG 18>41 ou 47 (F4, agência/conta/CPF/"
            "MCI). Extrato: 18>47 F4 (§2.1).",
            "INSS_LOCALIZAR",
            "POP_INSS_Beneficios_Sociais_anonimizado.md",
            True,
        )
    return Decision(
        "INSS/benefícios (SISPAG 18>41/47): disponibilidade sem valores no "
        "convênio INSS (Meu INSS/App/TAA p/ valores); indisponível → órgão "
        "responsável; extrato atualiza no dia seguinte (§2.1).",
        "INSS_GENERICO",
        "POP_INSS_Beneficios_Sociais_anonimizado.md",
        True,
    )


def decide_limites(filled: dict[str, str], norm: str) -> Decision:
    """Ramos do POP de Limites (POP_Limites_Cartao_Credito_PF_anonimizado.md)."""
    # Token 50148 FALHOU (ou sem senha): só canais, não prossegue. Primeiro,
    # pois "consulta" aparece também nessas perguntas sem ser o tema.
    if ("token" in norm or "ura" in norm or "50148" in norm) and (
        "falh" in norm or "sem sucesso" in norm or "negad" in norm or "sem senha" in norm
    ):
        return Decision(
            "Token (50148) é obrigatório: sem sucesso — ou sem autenticação por "
            "senha — NÃO prossiga; indique só os canais do item 3 da 50190.",
            "LIMITES_TOKEN",
            "POP_Limites_Cartao_Credito_PF_anonimizado.md",
            True,
        )
    # Consulta: SISALFA + dever de informar canais.
    if "canais" in norm or "consultar" in norm or "consulta" in norm:
        return Decision(
            "Consulte em SISALFA 17.01.01.9.22 F10 ('Limite Créd. Dispon.') e "
            "INFORME os canais: WhatsApp Alfa ('limite Cartão Alfa'), App Alfa/"
            "App Cartão Alfa, internet, URA e caixa eletrônico. Encerrar sem "
            "informar é conduta incompleta.",
            "LIMITES_CANAIS",
            "POP_Limites_Cartao_Credito_PF_anonimizado.md",
            True,
        )
    # Aumento/redução com Token ok (antes do Token genérico).
    if "aumentar" in norm or "reduzir" in norm or "aumento" in norm or "reducao" in norm:
        return Decision(
            "Aumento/redução: com Token validado, altere o limite único (ANC "
            "vigente + disponível); sem Token, só canais do item 3 da 50190.",
            "LIMITES_ALTERAR",
            "POP_Limites_Cartao_Credito_PF_anonimizado.md",
            True,
        )
    # Token genérico (sem falha explícita).
    if "token" in norm or "ura" in norm or "50148" in norm:
        return Decision(
            "Token (50148) é obrigatório: com sucesso, consulte/altere o limite "
            "único (correntista e não correntista com ANC vigente).",
            "LIMITES_TOKEN",
            "POP_Limites_Cartao_Credito_PF_anonimizado.md",
            True,
        )
    return Decision(
        "Limites do cartão PF: Token 50148 obrigatório; consulta em SISALFA "
        "17.01.01.9.22 F10 com dever de informar canais; sem Token, só canais "
        "da 50190 item 3.",
        "LIMITES_GENERICO",
        "POP_Limites_Cartao_Credito_PF_anonimizado.md",
        True,
    )


def decide_judicial(filled: dict[str, str], norm: str) -> Decision:
    """Ramos do POP de Bloqueio Judicial (POP_Bloqueio_Judicial_anonimizado.md)."""
    # §3.1: consulta limitada a 365 dias.
    if "365" in norm or "400" in norm or "prazo" in norm or "ano" in norm:
        return Decision(
            "SISJUD-10/14 aceitam no máximo 365 dias (1 ano): fracione intervalos "
            "maiores (ex: 2023 = 01/01 a 31/12). 'D' detalha juízo/partes/valor. "
            "Nada encontrado: informe, registre FCR (SAC: ocorrência se preferir) "
            "(§3.1).",
            "JUDICIAL_PRAZO",
            "POP_Bloqueio_Judicial_anonimizado.md",
            True,
        )
    # §3.1: bloqueio identificado (extração F2) e proibição de exceder o consta.
    if "identificado" in norm or "protocolo" in norm or "processo" in norm:
        return Decision(
            "Identificado: em SISJUD-17 selecione o protocolo com 'X' duas vezes, "
            "anote o processo e, em F2, vara/juízo e tribunal. O banco acata a "
            "ordem: repasse SÓ o que consta (§3.1, Obs.) e oriente a procurar o "
            "órgão. Proventos + discordância: comunique/requeira ao juízo.",
            "JUDICIAL_IDENTIFICADO",
            "POP_Bloqueio_Judicial_anonimizado.md",
            True,
        )
    # §3.1: proventos previdenciários.
    if "proventos" in norm or "previdenciario" in norm:
        return Decision(
            "Conta de proventos bloqueada: o banco não desbloqueia — oriente a "
            "comunicar o fato ou pedir alteração/extinção da ordem ao juízo "
            "competente (§3.1).",
            "JUDICIAL_PROVENTOS",
            "POP_Bloqueio_Judicial_anonimizado.md",
            True,
        )
    # §3.1: desbloqueio identificado = disponível.
    if "desbloqueio" in norm and ("disponivel" in norm or "liberado" in norm):
        return Decision(
            "Desbloqueio identificado no SISJUD: conta/valor disponível para movimentação (§3.1).",
            "JUDICIAL_DESBLOQUEIO",
            "POP_Bloqueio_Judicial_anonimizado.md",
            True,
        )
    return Decision(
        "Bloqueio judicial: telas SISJUD 10/14/15/16/17 (máx. 365 dias); não "
        "achou → FCR; achou → processo + F2 (vara/juízo/tribunal), banco acata, "
        "repasse só o que consta; proventos → juízo competente (§1, §3.1).",
        "JUDICIAL_GENERICO",
        "POP_Bloqueio_Judicial_anonimizado.md",
        True,
    )


def decide_alfa(filled: dict[str, str], norm: str) -> Decision:
    """Ramos do POP Alfa Rende Fácil (POP_Alfa_Rende_Facil_Adesao_anonimizado.md)."""
    # §3.1: Duplo Sim obrigatório na contratação.
    if "duplo sim" in norm and ("sem" in norm or "omit" in norm or "falt" in norm):
        return Decision(
            "A contratação EXIGE Duplo Sim na Plataforma (Operações Contratadas "
            "ou Investimentos>CDB>Aplicação automática). Omitido no registro, "
            "a confirmação posterior não sana: a adesão é inconforme (§3.1).",
            "ALFA_DUPLO_SIM_OBRIGATORIO",
            "POP_Alfa_Rende_Facil_Adesao_anonimizado.md",
            True,
        )
    # §3.1: confirmação em até 30 dias.
    if "30 dias" in norm or "31" in norm or "prazo" in norm or "confirm" in norm:
        return Decision(
            "Após o registro, o cliente confirma em 'Pendentes de confirmação' "
            "em até 30 dias. No 31º dia o sistema não permite mais: a adesão "
            "não se efetiva (§3.1).",
            "ALFA_PRAZO_30",
            "POP_Alfa_Rende_Facil_Adesao_anonimizado.md",
            True,
        )
    # §3.1: como contratar.
    if "contratar" in norm or "contratacao" in norm or "adesao" in norm:
        return Decision(
            "PF: Plataforma de Relacionamento (Operações Contratadas) ou Menu > "
            "Investimentos > CDB > Aplicação automática > Alfa Rende Fácil, "
            "sempre com Duplo Sim + confirmação em 30 dias (§3.1).",
            "ALFA_COMO_CONTRATAR",
            "POP_Alfa_Rende_Facil_Adesao_anonimizado.md",
            True,
        )
    return Decision(
        "Alfa Rende Fácil PF: contratação na Plataforma com Duplo Sim "
        "obrigatório e confirmação em até 30 dias (§3.1).",
        "ALFA_GENERICO",
        "POP_Alfa_Rende_Facil_Adesao_anonimizado.md",
        True,
    )


def decide(query: str) -> Decision:
    """Ponto único: extrai slots, detecta o POP e percorre os ramos.

    Puro e determinístico: mesma pergunta, mesma resposta, sempre.
    """
    filled = extract_slots(query)
    norm = _norm(query)
    doc = detect_doc(filled, norm)
    if doc == "pop_acesso_pf.md":
        return decide_acesso(filled, norm)
    if doc == "pop_cdc_pf.md":
        return decide_cdc(filled, norm)
    if doc == "POP_Cartoes_SAC_anonimizado.md":
        return decide_cartoes(filled, norm)
    if doc == "POP_Fatura_Envio_Email_anonimizado.md":
        return decide_fatura(filled, norm)
    if doc == "POP_INSS_Beneficios_Sociais_anonimizado.md":
        return decide_inss(filled, norm)
    if doc == "POP_Limites_Cartao_Credito_PF_anonimizado.md":
        return decide_limites(filled, norm)
    if doc == "POP_Bloqueio_Judicial_anonimizado.md":
        return decide_judicial(filled, norm)
    if doc == "POP_Alfa_Rende_Facil_Adesao_anonimizado.md":
        return decide_alfa(filled, norm)
    missing = find_missing_slots(filled)
    target = next_discriminative_slot(missing)
    if target:
        from ragbench.conversational.clarifier import _SLOT_BY_NAME

        slot = _SLOT_BY_NAME.get(target)
        if slot:
            return Decision(
                f"Para responder preciso de um dado: {slot.question}",
                "ESCLARECER",
                "",
                False,
                (target,),
            )
    return Decision(FALLBACK_ANSWER, "FALLBACK", "", False, tuple(missing))


class DecisionTreeEngine(BaseRAGPipeline):
    """Baseline simbólico: POPs codificadas, zero LLM, zero retrieval."""

    def __init__(self, settings: BenchmarkSettings | None = None):
        self.settings = settings or get_settings()

    @property
    def llm_model(self) -> str:
        """Nome do 'modelo' para telemetria (árvore versionada, sem LLM)."""
        return f"{TREE_MODEL_NAME}-{TREE_VERSION}"

    async def initialize(self) -> None:
        """Sem storages: no-op."""

    async def finalize(self) -> None:
        """Sem storages: no-op."""

    async def ainsert(self, text: str) -> None:
        """Árvore não indexa: chamada ignorada com aviso."""
        logger.warning("DecisionTreeEngine.ainsert ignorado (regras fixas).")

    async def get_query_embeddings(self, texts: list[str]) -> np.ndarray:
        """Sem retrieval: retorna zeros (cache fica inócuo no run-tree)."""
        return np.zeros((len(texts), 3))

    async def aquery(
        self,
        query: str,
        mode: SearchMode | str = SearchMode.HYBRID,
        top_k: int = 5,
        stream: bool = False,
        **kwargs,
    ) -> str | AsyncGenerator[str, None]:
        """Percorre a árvore e retorna o template (sempre str, nunca stream)."""
        decision = decide(query)
        logger.debug("Árvore ramo=%s doc=%s", decision.branch, decision.doc)
        return decision.answer
