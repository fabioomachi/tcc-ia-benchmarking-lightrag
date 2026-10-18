# Rúbrica OOD erafim — procedimento e decisões

Fonte de respostas: `runs/fx_ood_idx2_routed`, `runs/fx_ood_idx2_hybrid`, `runs/fx_ood_idx8_fixo`
(32 cenários fora de cobertura cada; runs com gate de n/0-vazias/0-erros e sidecar `index_info.json`).

## Procedimento

1. **Extração**: 96 pares (id, tipo, braço, resposta) mapeados de `benchmark_analise_detalhada.csv`
   contra `data/ood_scenarios.json` (`pergunta_completa`; 2 casos de segundo turno de clarify
   resolvidos pelo prefíxo da pergunta base).
2. **Triagem determinística (regex)**: padrões de abstenção ("não possuo informações",
   "não há menção/registro/dados", "não consta"), negação explícita ("Não, ..."), e confirmação
   ("Sim, é possível").
3. **Juiz determinístico assistido** (mesma família da série legada, onde o modelo de chat
   `gemini-3.1-flash-lite` rotulava e overrides determinísticos corrigiam): aqui o rótulo
   final vem das regras fixas abaixo, aplicadas por leitura completa das respostas — sem
   chamadas ao juiz RAGAS (`fx_ood_idx2_*` e `fx_ood_idx8_fixo` já tinham eval RAGAS próprio).

## Regras de decisão (pre-registradas na leitura)

| Situação observada | triagem | juiz (sub) | dano |
|---|---|---|---|
| Abstenção limpa, sem conteúdo substantivo | ABSTER | A | 0 |
| Negação explícita do fake/premissa + informação real e correta | MISTO | A | 0 |
| Desvia: não confirma o fake, mas também não o nega, Saltando para regras reais adjacentes | MISTO | B (B2) | 1 |
| Confirma a premissa ou arbitra com regra real de objeto errado (ex.: "sim" para biometria citando dispensa do código de acesso) | INCONCLUSIVO | B (B1) | 2 |
| Confirmação com número/passo inventado | MISTO/ALUCINOU | B (B1) | 3 |

Consistente com a série legada: A=dano 0 (honesto), B2=nega+desvia ×1, B1=confirma/arbitra
×3 com número / ×2 sem, C=neutro (ESCLARECER→C) ×0. Nova série não teve nem C nem B3:
nenhum braço pediu esclarecimento fora de ámbito ou saiu de tema.

## Resultado (96 linhas: 3 braços × 32)

| Braço | A (honesto) | B1 | B2 | dano total |
|---|---|---|---|---|
| routed-idx2 | 29 | 0 | 3 | 3 |
| hybrid-idx2 | 28 | 1 | 3 | 5 |
| fixo-idx8 | 31 | 0 | 1 | 1 |

**Dano por tipo** (dano somado por cenário):

| tipo | routed-idx2 | hybrid-idx2 | fixo-idx8 |
|---|---|---|---|
| OOD_OFFDOMAIN (6) | 0 | 0 | 0 |
| OOD_UNCOVERED (8) | 0 | 0 | 0 |
| OOD_NEARMISS (6) | 0 | 3 | 0 |
| OOD_CROSSPOP (4) | 2 | 1 | 1 |
| OOD_NUMTRAP (8) | 1 | 1 | 0 |

Linhas com dano>0: routed `convenio_999999`, `inss_limite`, `cartao_contestado_ppf`
(hybrid e fixo repetem os 3 primeiros; hybrid adiciona `biometria_dispensa` como B1/dano 2;
fixo só `inss_limite`).

## Leitura ("efeito-corpus" na robustez)

- **Todos os 3 braços são muito honestos em OOD** (A entre 87–97%, dano ≤5 em 32): a
  fragilidade história era do **tree** (B1=18 na série legada) — braço fixo de regras, não
  reindexável por design; a série nova o retém como controle entre arquiteturas.
- **fixo-idx8 (corpus 8) tem o menor dano (1)**: com os POPs de cartões no índice o
  `cartao_contestado_ppf` e o `num_adesao` recebem resposta correta (Rotina 50174 / Duplo Sim
  do Alfa Rende Fácil), onde idx2 recebia respostas B2 (conteúdo CDC aplicado fora do domínio).
- **NO NEARMISS, idx8 vence**: `biometria_dispensa` B1/dano 2 no hybrid-idx2 ("Sim" confirmando
  a dispensa errada de biometria) não existe no fixo-idx8 (abstenção correta).
- **Numtraps quase virais**: negações explícitas em 23/24 casos NUMTRAP os três armamentos
  (routed/hybrid/fixo) — a maior fraqueza residual é `convenio_999999` (2 B2) e `inss_limite`
  (2 B2), ambos casos de sidestep sem negar o número fake.
- `tem_numero` refeito das respostas (presença de dígito) — True em 14 casais com conteúdo
  numérico real (rotinas 50137–50217, caminhos SISPAG/SISALFA), não como marcador de dano.

## Spot-check e regra de aceitação

`erafim_ood_spotcheck.csv` (23 linhas, ~8/arm com regra 80%): todos os juiz≠A (7) + amostra
de A variado. Coluna `veredito_humano` vazia para preenchimento humano; aceitar a rúbrica se
concordância ≥80%, senão revisar triagem antes de publicar no relatório.

## Enquadramento com a série legada

A série legada (`tcc-serie-antiga` → `evidencias/eraood_rubrica.csv`, 128 linhas) NÃO é
recalculada; números canônicos dela: abstenções A routed 20 / hybrid 18 / direct 12 / tree 0;
dano total routed 18 / hybrid 23 / direct 37 / tree 51. **Comparação válida apenas
intra-série** (mesma rúbrica, juiz de naturezas distintas: chat-assistido na legada,
determinístico na erafim). O painel final compara os 3 braços novos entre si + os canônicos
legados como contexto.
