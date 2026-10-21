# Relatório comparativo final — Benchmarking RAG (LightRAG) no Banco Alfa

Série **erafim** — desenho fatorial com índice condicionado. Janela: 10–18/10/2026.
Pré-registro: `git show tcc-serie-antiga:relatorio-tcc/evidencias/criterios_fatorial.md`.
Dados: `evidencias/erafim_resumo_ragas.csv`, `evidencias/erafim_ood_rubrica.csv`,
`evidencias/erafim_ood_notas.md`. Regeneração: `PROMPT-regenerar-relatorio.md`.

## 1. Resumo executivo

| Contraste | Resultado (faithfulness, salvo indicado) | Classificação (limiares pré-registrados) |
|---|---|---|
| **H2 — routed ≥ fixo pareado** | duo-16/idx2 +0.0954; esparso-16/idx8 +0.1152; **denso-64/idx8 +0.1231** (routed vence 29×17 pareados; média fixo−routed −0.1109/pergunta) | **efeito confirmado** na célula principal (n=64); sugestivo nas n=16 |
| **H1 — efeito-volume puro** (mesmas 16 perguntas, só o índice muda) | routed +0.0056 (ruído); **hybrid −0.3695 (efeito)** | **falsificada para routed; real apenas para hybrid** |
| **H4 — densidade degrada menos que corpus** | routed 0.5127→0.5492 (+0.0365); fixo 0.3975→0.4261 (+0.0286); hybrid 0.2633→0.4161 (+0.1528, melhora com mais perguntas); direct 0.1471→0.1764 (+0.0293); tree 0.7190→0.7260 (+0.0070) | **confirmada** |
| **Efeito-corpus total** (duo-16/idx2 → esparso-16/idx8) | routed −0.4388; fixo −0.4586; hybrid −0.6506; tree −0.1383; direct −0.2069 | grande, replicado em todos os braços |
| **H3 — dano OOD idx2 < idx8** | sem mesmo braço nos dois índices na rúbrica erafim (dano: routed-idx2 3 · hybrid-idx2 5 · fixo-idx8 1) | **inconclusivo intra-série** (limitação registrada) |

**Conclusão para a banca.** A queda histórica de qualidade ao crescer o corpus era
predominantemente **questionário, não distração**: para o sistema-carro-chefe (routed), o
efeito-volume puro com perguntas idênticas é ruído (+0.006) contra um efeito-corpus total de
−0.44 — são os domínios novos do questionário (layout, INSS, cartões) que derrubam o
faithfulness, não o excesso de documentos indexados. A exceção robusta é o **hybrid**, cujo
efeito-volume puro é real (−0.37): nele, a competição por contexto no índice maior degrada a
geração mesmo sem mudar as perguntas — o argumento do roteador de contratos vale sobretudo
para cargas sem roteio explícito. Fora de cobertura, os três braços novos são honestos (dano ≤5 em 32);
a fragilidade residual é NUMTRAP com *sidestep* (não confirma o número falso, mas adivinha ao
redor dele). Recomendação de deploy: **routed como padrão** (0.80 de score no denso-64, honestidade
OOD alta, custo moderado), **tree reservado a universos fechados e estáveis** (teto in-dist,
0 chamadas de inferência, mas maior dano histórico OOD — série legada), **direct como linha de
base LLM-pleno** (sem retrieval, mais frágil a armadilhas numéricas) e **fixo como piso
durável** (sem custo de confusão no corpus grande, dentro do pré-registro).

## 2. Desenho pré-registrado (resumo)

- **Fatorial 2×2** corpus {2 POPs = idx2, 8 POPs = idx8} × densidade {2, 8 perguntas/POP},
  braços {routed, fixo, hybrid, direct, tree}, probe fixa OOD-32:
  - `(2,8)` = `duo-denso-idx2` (n=16) com contra-par **`duo-denso-idx8` = mesmas 16 perguntas,
    só o índice muda** (contraste-estrela); `(2,2)` = `piloto-duo2` (n=4, só pipeline);
  - `(8,2)` = `octeto-esparso-idx8` (n=16); `(8,8)` = `octeto-denso-idx8` (n=64).
  - Célula `(2,2)`idx8 não planejada; **`octeto-esparso × idx2` excluído por pré-registro**
    (documento ausente ≠ volume).
- **Índice condicionado**: idx2 = `STORAGE_DIR=lightrag_2pops_db` (docs `6d7fa2c9`, `96b804ce`);
  idx8 = `lightrag_ollama_db` comgelado antes do D1 (8 SHAs no apêndice). Identificação em quatro
  camadas (L0 `STORAGE_DIR`, L1 run-id `fx_*_idx{2,8}_*`, L2 sidecar `index_info.json` por run,
  L3 fingerprint `rota_scores` — 1 chave por doc indexado: 2 vs 8) + canários `golden96-73` /
  `golden96-86`.
- **Amostragem**: seed 42 estratificada por tipo; 64 IDs únicos aninhados
  piloto ⊂ duo-16 ⊂ denso-64; esparso ⊂ denso (`evidencias/amostra_fatorial.json`).
- **Juiz** `gemini-3.5-flash-lite` (500 req/dia ⇒ ~1 eval-64/dia); chat `gemini-3.1-flash-lite`;
  embeddings `gemini-embedding-001/768`. **Congelamento D1–D8** (sem reindex/src/uv sync).
- **Gatilhos**: aborto de célula se >15% NaN-429; ruído do juiz = Δ<0.05 em n≤16;
  piloto n=4 sem conclusão; NaN sempre com `n_scored/n` declarado.

## 3. Registro operacional (congelamento)

- Branch `fatorial/idx-condicionado`; base `2c3dea0…dfc3e33`, rúbrica `aa0dbf7`.
- 23 runs `fx_*` com gate `n/0 vazias/0 erros` 100% PASS via **resume idempotente**
  (mesmo `--run-name`, sem `--no-resume`): 7 respostas vazias transientes no esparso (15/10)
  e 2 no denso fixo foram zeradas em retomada; sidecar `index_info.json` em todos os runs.
- **429s**: juiz secou 14/10 14:18 (retry 6h41m), 15/10 17:43 (retry 3h16m),
  16/10 19:58 (retry 1h02m→42m), 17/10 11:59 (retry 8h22m) e 18/10 16:24 (retry 4h28m) —
  padrão estável: ~1 eval-64/dia no balde `generate_content_free_tier_requests` (500/dia).
  Embeddings: burst de 30 paralelos passou (não é limite por minuto), mas o balde diário
  secou no idx2 CDC em 10/12 — resolvido com pacing (`EMBEDDING_MAX_CONCURRENCY=1`,
  `BATCH_SIZE=2`, `MICRO_PAUSE=1.5`, retries 8s/3s).
- **Incidentes com veredicto**: (i) sanidade idx2 estourou ±15% no acesso (21.8% entidades,
  CDC 9.6% OK) — decisão pré-registrada publicá-la como **"volume + vintage de extração"**,
  sem reindexação; (ii) evals interrompidos por cota **nunca foram publicados parciais**
  (redo integral); (iii) piloto contestado de 12/10 foi desfeito (`0962318`) e a série
  reiniciada no branch fatorial.
- Workarounds persistentes: `PYTHONPATH=~/.cache/ragbench-force-ipv4` (IPv6 quebrado);
  evals **um por chamada** com timeout ≥90 min (CSV só escrito no fim).

## 4. Resultados em distribuição — matriz por célula

`score_composto` = média aritmética das 4 médias RAGAS (definição da série erafim).
Coluna primária dos limiares = **f (faithfulness)**. Latência = `latencia_total_s` média.

| Célula (corpus × densidade) | Braço | n | score | **f** | recall | precision | ar | lat_s |
|---|---|---|---|---|---|---|---|---|
| (2,2) piloto idx2 | routed | 4 | 0.9694 | 1.0000 | 1.0 | 1.0 | 0.8777 | 4.1 |
| (2,2) | fixo | 4 | 0.9488 | 0.8995 | 1.0 | 1.0 | 0.8956 | 7.8 |
| (2,2) | hybrid | 4 | 0.9619 | 0.9688 | 1.0 | 1.0 | 0.8788 | 15.6 |
| (2,2) | direct | 4 | 0.8324 | 0.4548 | 1.0 | 1.0 | 0.8747 | 4.1 |
| (2,2) | tree | 4 | 0.9374 | 1.0000 | 1.0 | 1.0 | 0.7495 | 0.0 |
| **(2,8) duo-16 idx2** | routed | 16 | 0.9433 | 0.9515 | 0.9583 | 1.0 | 0.8632 | 6.2 |
| (2,8) idx2 | fixo | 16 | 0.9341 | 0.8561 | 1.0 | 1.0 | 0.8804 | 12.5 |
| (2,8) idx2 | hybrid | 16 | 0.9494 | 0.9139 | 1.0 | 1.0 | 0.8835 | 38.8 |
| (2,8) idx2 | direct | 16 | 0.8044 | 0.3540 | 1.0 | 1.0 | 0.8638 | 21.3 |
| (2,8) idx2 | tree | 16 | 0.8965 | 0.8573 | 0.9792 | 1.0 | 0.7495 | 0.0 |
| **(2,8) duo-16 idx8** (contrafactual) | routed | 16 | 0.9501 | 0.9571 | 0.9792 | 1.0 | 0.8642 | 22.0 |
| (2,8) idx8 | hybrid | 16 | 0.7753 | 0.5444 | 1.0 | 1.0 | 0.5569 | 1.7 |
| **(8,2) esparso-16 idx8** | routed | 16 | 0.7544 | 0.5127 | 0.9792 | 1.0 | 0.5258 | 55.5 |
| (8,2) | fixo | 16 | 0.7571 | 0.3975 | 1.0 | 1.0 | 0.6308 | 9.1 |
| (8,2) | hybrid | 16 | 0.6323 | 0.2633 | 1.0 | 1.0 | 0.2659 | 2.0 |
| (8,2) | direct | 16 | 0.7474 | 0.1471 | 1.0 | 1.0 | 0.8426 | 26.1 |
| (8,2) | tree | 16 | 0.8463 | 0.7190 | 1.0 | 1.0 | 0.6663 | 0.0 |
| **(8,8) denso-64 idx8** | routed | 64 | **0.8010** | **0.5492** | 0.9870 | 1.0 | 0.6676 | 5.1 |
| (8,8) | fixo | 64 | 0.7411 | 0.4261 | 0.9844 | 0.9687 | 0.5851 | 1.0 |
| (8,8) | hybrid | 64 | 0.7471 | 0.4161 | 1.0 | 1.0 | 0.5722 | 2.5 |
| (8,8) | direct | 64 | 0.7493 | 0.1764 | 1.0 | 1.0 | 0.8210 | 9.0 |
| (8,8) | tree | 64 | 0.8448 | 0.7260 | 0.9857 | 1.0 | 0.6673 | 0.0 |

Declaração de NaN: 1 em duo-16/idx2 fixo; 3 em esparso-16 tree; 1**direct** em denso-64 (n_scored 63/64); 1 em OOD fixo-idx8 RAGAS
(scores desses itens excluídos das médias; `n_scored/n` na evidência).

**Leitura.** (i) *Mundo fechado (duo-16/idx2)*: routed/fixo/hybrid/tree ≥0.89, direct 0.80 —
todos os braços funcionam quando o grafo cobre o domínio. (ii) *Corpus grande*: routed cai
menos (0.80) que fixo/hybrid (0.74) — tanto no subjetivo score quanto no f pareado (§5.2),
e *context_precision* permanece em 1.0: o que degrada é a **geração** (f, ar), não o
retrieval. (iii) O hybrid esparso colapsa no ar (0.2659): consultas de 2/POP em 8 POPs sem
roteio erram o contexto e o juiz pune releção irrelevante. (iv) `tree` mantém f=0.72 fora do
mundo pequeno sem gastar API, mas sucumbe no ar (0.6659→0.6663) — só fica atrás do routed
dentro do corpus coberto.

## 5. Contrastes pré-registrados

### 5.1 Efeito-volume puro (H1): duo-16, mesmas perguntas, só o índice muda

| Braço | f idx2 | f idx8 | Δ = efeito-volume | Classificação |
|---|---|---|---|---|
| routed | 0.9515 | 0.9571 | **+0.0056** | ruído (<0.05) — **H1 falsificada** |
| hybrid | 0.9139 | 0.5444 | **−0.3695** | efeito (≥0.10) — **distração real no hybrid** |

Para o routed, adicionar 6 POPs ao índice não derrubou a geração com perguntas idênticas:
o roteio mantém o contexto do POP coberto e o faithfulness sobe (score 0.9433→0.9501,
dentro de ruído). No hybrid (busca híbrida global, sem roteamento), o mesmo passo degrada
f em −0.37 — o custo de distrair o retrieval existe no braço sem roteador. A falsificação pré-registrada "se H1 ≈ 0, o efeito histórico era questionário"
concretizou-se em ~um submetida (routed) e, no hybrid, valeu a hipótese positiva detalhada
in-fit na §5.4.

### 5.2 routed × fixo pareado por pergunta (H2)

| Célula | n pareado | média fixo−routed | mediana | vence routed/empate/fixo | Class. |
|---|---|---|---|---|---|
| duo-16 idx2 | 15 | −0.0654 | 0.0000 | 6 / 6 / 3 | sugestivo |
| esparso-16 idx8 | 15 | −0.0562 | 0.0000 | 6 / 3 / 6 | sugestivo |
| **denso-64 idx8** | 62 | **−0.1109** | −0.0076 | **29 / 16 / 17** | **efeito — H2 confirmada** |

No corpus inteiro e denso, o **roteador vence o baseline fixo com estimativa pareada
+0.11/pergunta de f**, 1.7× o limiar de efeito; nas células n=16 dá apenas empate com mediana 0 (sugestivo).
Este é o achado decisivo: o custo operacional do roteador (clarify + chamadas extras)
se amortiza no corpus grande, onde o baseline fixo começa a errar mais o POP/tipo
relevante da consulta.

### 5.3 Densidade (H4): esparso (2/POP) → denso (8/POP), mesmo corpus idx8

| Braço | f esparso | f denso | Δ densidade | Class. |
|---|---|---|---|---|
| routed | 0.5127 | 0.5492 | +0.0365 | ruído |
| fixo | 0.3975 | 0.4261 | +0.0286 | ruído |
| hybrid | 0.2633 | 0.4161 | +0.1528 | efeito a favor do denso |
| direct | 0.1471 | 0.1764 | +0.0293 | ruído |
| tree | 0.7190 | 0.7260 | +0.0070 | ruído |

Densidade não degrada (routed/fixo em ruído; hybrid melhora — com mais perguntas por POP, o
retrieve global ganha mais sinal de intenção do cliente para desambiguar). H4 sai
confirmada: mais amostras por domínio não piorou nenhum braço.

### 5.4 Efeito-corpus total e decomposição

| Braço | total (duo-idx2 → esparso-idx8) | volume puro | densidade | residual ≈ **questionário** |
|---|---|---|---|---|
| routed | −0.4388 | +0.0056 | +0.0365 | **−0.4809** |
| fixo | −0.4586 | n/a | +0.0286 | ≈ −0.49 |
| hybrid | −0.6506 | −0.3695 | +0.1528 | ≈ −0.43 |
| tree | −0.1383 | n/a | +0.0070 | ≈ −0.15 |
| direct | −0.2069 | n/a | +0.0293 | ≈ −0.24 |

A árvore é a que menos sofre com o corpus (−0.14); o resto varia de −0.21 a −0.65. Em todos
os braços medidos, **o questionário de domínios novos explica quase todo o efeito**; os termos
volume+densidade são ≈0 para routed/fixo; no hybrid, o volume puro responde pela metade
do total. A conclusão geral sobrevive a ambos os cenários.

## 6. Robustez fora de cobertura (OOD-32) — rúbrica determinística

RAGAS não é veredito OOD (pune abstenção); como painel de referência: routed-idx2 0.3276 ·
hybrid-idx2 0.3443 · fixo-idx8 0.3801 (score composto).

**erafim (3 braços × 32 = 96 julgamentos; `erafim_ood_rubrica.csv` + `erafim_ood_notas.md`):**

| Braço | A honesto | B1 confirma | B2 sidestep | dano total |
|---|---|---|---|---|
| routed-idx2 | 29 | 0 | 3 | **3** |
| hybrid-idx2 | 28 | 1 (dano 2) | 3 | **5** |
| fixo-idx8 | 31 | 0 | 1 | **1** |

Dano por tipo: OFFDOMAIN/UNCOVERED → 0 nos três; NEARMISS → 0/3/0 (o hybrid "confirma" a
dispensa de *biometria* citando a dispensa real do *código de acesso* — `biometria_dispensa`);
CROSSPOP → 2/1/1; NUMTRAP → 1/1/0. Itens com dano>0 são os mesmos `convenio_999999`,
`inss_limite`, `cartao_contestado_ppf` (sidestep sem negar o fake) em 2–3 braços.

**Série legada** (idx8, rúbrica juiz-chat — comparação válida apenas intra-série): abstenções
A routed 20 · hybrid 18 · direct 12 · **tree 0**; dano routed 18 · hybrid 23 · direct 37 ·
**tree 51**. A inversão da segurança fora de cobertura da árvore permanece como achado
histórico; os braços novos (rotacionados por RAGAS) ensaiam honestidade de outra natureza —
`fx_ood_idx8_fixo` realiza o piso de dano (1) com 31/32 respostas honestas.

**Spot-check humano**: `erafim_ood_spotcheck.csv` (23 linhas; `veredito_humano` a preencher;
aceitação pré-registrada ≥80%). *Pendência para a banca.*

## 7. Respostas às hipóteses pré-registradas

- **H1 — falsificada para o routed** (efeito-volume +0.0056 com perguntas idênticas),
  **confirmada apenas para o hybrid** (−0.3695). O argumento histórico "o grafo absorve a
  distração" vale para o roteado; para o híbrido, o custo é real e motivou a arquitetura.
- **H2 — confirmada** na célula decisória (n=64 pareado: +0.1231 de f; 29×17 win/loss),
  sugestiva nas n=16.
- **H3 — inconclusivo intra-série**: a rúbrica erafim cobre routed/hybrid idx2 vs fixo idx8
  (sem mesmo braço nos dois índices). Preencher futuramente com `ood-idx2 fixo` +
  `ood-idx8 routed` se houver janela de cota. Legado usado apenas como referência histórica.
- **H4 — confirmada**: densidade ≈ ruído (ou melhora), corpus é a queda dominante.

## 8. Limitações e ruído declarado

1. Piloto n=4 (sem conclusão, por pré-registro); células n=16 têm limiar apenas "sugestivo";
   a evidência decisiva está no denso-64 pareado.
2. Incidência de 19–21/10: o gerenciador de shell derrubava o eval em 90 min (o tree denso
    roda ~1h20m), e as duas tentativas abortadas consumiram a cota do dia; em 21/10 a
    recuperação exigiu reconstruir o venv (o SO atualizou Python 3.12→3.14 de madrugada;
    `asyncio.get_event_loop` quebra em 3.14 e o rebuild vlanew saiu sem `langchain-openai`):
    `uv sync --all-extras --python 3.12` restaurou o ambiente validado e o eval fechou
    com 64/64 e zero NaN.
3. `answer_relevancy` do tree **idêntico a 4 casas** (0.7495) no piloto e no duo-16 idx2:
   coincidência não explicável com template determinístico — tratada como ruído do juiz; não
   influencia vereditos nem thresholds de f.
4. Sanidade idx2: acesso estourou o ±15% (21.8% entidades, vintage de extração distinto),
   registrado **antes** dos resultados — portanto comparações idx2×idx8 lêem-se
   "volume + vintage"; o contraste-estrela do duo-16 (mesmas perguntas) é o que isola o volume.
5. Latência é métrica operacional (nunca qualidade): clarify esparso do routed custa 55 s médio
   contra 5 s no denso-64 (mais turnos na escuridão esparso); tree=0.0s e direct~21–26 s.
6. H3 não pode ser testada sem `ood-idx2 fixo` e `ood-idx8 routed` (par de braços que o
   orçamento D1–D8 não cobriu).

## 9. Apêndice — versionamento, manifestos e desvios

- **Commits**: `2c3dea0` limpeza do relatório (série legada em tag `tcc-serie-antiga`);
  `7123f5e` fix health (`get_embeddings` com model — TypeError mascarava quedas);
  `b760a51`+`dfc3e33` amostragem pré-registrada (seed 42) + golden convertido p/ eval hybrid;
  `0962318` desfazer piloto contaminado; `aa0dbf7` rúbrica OOD erafim.
- **Manifesto idx8** (`lightrag_ollama_db/index_manifest.json`): pop_acesso `6d7fa2c9`,
  pop_cdc `96b804ce`, LimitesCartão `b37900c6`, Fatura `ec012f34`, INSS `c477636c`,
  Alfa `c87aa4fb`, Bloqueio `846e2e4f`, Cartões `7e4f54f8`. **idx2** (`lightrag_2pops_db`):
  pop_acesso `6d7fa2c9`, pop_cdc `96b804ce` (mesmos SHAs da fonte).
- **Datas**: index idx2 e piloto 12–14/10; esparso 15/10; denso 15–16/10; evals 13–18/10;
  rúbrica 17/10. **429 do juiz**: 14/10 14:18 (retry 6h41m) · 15/10 17:43 (3h16m) ·
  16/10 19:58→20:17 (1h02m→42m) · 17/10 11:59 (8h22m) · 18/10 16:2x (4h28m).
- **Desvios do pré-registro**: (i) `duo-denso-idx8` medido só em routed/hybrid (fixo/direct/
  tree não planejados nesta célula — não execu-> não imputados); (ii) `octeto-esparso × idx2`
  excluído (pré-registrado, não desvio); (iii) veredicto OOD determinístico na erafim vs
  juiz-chat na legada (comparação só intra-série); (iv) aborto/execução forçada remanejada
  para o dia seguinte duas vezes (regra de parar em 429/exit 3, sem parcial publicada).
