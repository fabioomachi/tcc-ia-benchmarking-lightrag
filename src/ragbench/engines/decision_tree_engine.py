"""Chatbot tradicional por árvore de decisão: POPs codificadas à mão.

Braço simbólico do TCC: zero LLM, zero grafo, zero retrieval. As regras dos
dois POPs viram ramos `if/elif` com templates de resposta redigidos a partir
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
from ragbench.core.models import SearchMode
from ragbench.infrastructure.logging import get_logger

logger = get_logger("ragbench.engine.tree")

TREE_VERSION = "pop-v1.0"
TREE_MODEL_NAME = "decision-tree-pop-v1"

FALLBACK_ANSWER = (
    "Não tenho regra codificada para este caso nos POPs de Senhas ou CDC. "
    "Informe se o assunto é senha/acesso (código de bloqueio, Alfa Code, "
    "biometria) ou empréstimo/CDC (parcela, boleto, cancelamento), "
    "ou procure uma agência."
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


@dataclass(frozen=True)
class Decision:
    """Resultado puro da árvore para uma pergunta."""

    answer: str
    branch: str
    doc: str  # pop_acesso_pf.md | pop_cdc_pf.md | ""
    confident: bool
    missing: tuple[str, ...] = ()


def _norm(text: str) -> str:
    from ragbench.conversational.router import normalize

    return normalize(text)


def detect_doc(filled: dict[str, str], norm: str) -> str:
    """Qual POP a pergunta pertence (slots acesso-específicos decidem primeiro)."""
    if any(filled.get(s) for s in ("codigo_bloqueio", "alfa_code", "biometria_dias")):
        return "pop_acesso_pf.md"
    n_acesso = sum(1 for k in ACESSO_KEYWORDS if k in norm)
    n_cdc = sum(1 for k in CDC_KEYWORDS if k in norm)
    if n_acesso > n_cdc:
        return "pop_acesso_pf.md"
    if n_cdc > n_acesso:
        return "pop_cdc_pf.md"
    return ""


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


class DecisionTreeEngine:
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
