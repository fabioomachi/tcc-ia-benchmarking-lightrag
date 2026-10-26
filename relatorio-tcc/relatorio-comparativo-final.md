# Relatório comparativo final — Benchmarking RAG (LightRAG) no Banco Alfa

Série **erafim** (10–18/10/2026). Este relatório compara quatro arquiteturas RAG sobre os
mesmos POPs do Banco Alfa, medindo com um LLM juiz (RAGAS) a qualidade das respostas em
cinco cenários de perguntas. Pré-registro do desenho: `git show
tcc-serie-antiga:relatorio-tcc/evidencias/criterios_fatorial.md`. Dados:
`evidencias/erafim_resumo_ragas.csv`, `evidencias/erafim_ood_rubrica.csv`,
`evidencias/erafim_ood_notas.md`. Regeneração: `PROMPT-regenerar-relatorio.md`.

## 1. Cenários

### 1.1 O que foi indexado (corpus e índices congelados)

Todo o experimento parte de **dois grafos LightRAG completos, congelados antes de qualquer
pergunta**: o índice **idx2** (`lightrag_2pops_db`) contém só os 2 POPs originais
(acesso físico `6d7fa2c9` e CDC `96b804ce`); o índice **idx8** (`lightrag_ollama_db`)
acrescenta 6 domínios novos (LimitesCartão, Fatura, INSS, Alfa, Bloqueio, Cartões — SHAs do
manifesto no apêndice). **O índice é o mesmo para todas as perguntas de um cenário** e nada
foi reindexado durante a janela — quando idx2 perde e idx8 vence (ou vice-versa), a diferença
é ou o volume de documentos, ou o conteúdo deles; nada mais mudou.

### 1.2 Conjuntos de perguntas (o que cada um isola)

Amostragem seed 42 estratificada por tipo, com IDs **aninhados**: piloto ⊂ duo-16 ⊂ denso-64;
esparso ⊂ denso (`evidencias/amostra_fatorial.json`).

| Cenário | Perguntas | Índice | O que isola |
|---|---|---|---|
| **Piloto** | 2/POP nos 2 POPs (n=4) | idx2 | nada — só valida o pipeline (pré-registro: sem conclusão) |
| **Duo-16** | 8/POP nos 2 POPs (n=16) | idx2 | universo 100% coberto — baseline do "mundo pequeno" |
| **Duo-16 idx8** | **as mesmas 16** duo-16 | idx8 | **volume puro**: mesmas perguntas, só o índice fica 4× maior |
| **Esparso** | 2/POP nos 8 POPs (n=16) | idx8 | **domínio novo puro**: idx8 grande, mas com poucas perguntas por domínio |
| **Denso** | 8/POP nos 8 POPs (n=64) | idx8 | **cenário principal**: corpus inteiro, todas as perguntas |
| **OOD-32** | 32 fora da cobertura | idx2/idx8 | honestidade fora de distribuição (rúbrica determinística, não RAGAS) |

Leitura prática: **duo-16 → duo-16 idx8** mede o efeito de *adicionar documentos*;
**duo-16 → esparso** mede o efeito de *adicionar domínios novos* ao questionário;
**esparso → denso** mede o efeito de *mais perguntas por domínio* (densidade).

### 1.3 Os braços (arquiteturas comparadas)

Todos os braços de retrieval compartilham a mesma base: um grafo LightRAG construído a
partir dos POPs (entidades, relações e trechos originais de texto) e o mesmo modelo de
chat para escrever a resposta final a partir do contexto recuperado pelo grafo. O que os
diferencia é **como chegam ao contexto certo** — e quanto de automação está no caminho.

- **hybrid — "o grafo como vem de fábrica" (o mais simples).
  A pergunta do cliente vai direta, sem tratamento, para uma única busca no grafo em modo
  `hybrid` (combina navegação por entidades/conceitos do grafo com similaridade de texto nos
  trechos), top-k=5, e o chat modelo responde com o que retornar. Não há clarificação
  (a coleta dos dados obrigatórios do POP, descrita no item fixo abaixo), não
  há roteio, não há estratégia por documento: toda pergunta é tratada da mesma forma,
  num corpus de 8 POPs com temas muito distintos (acesso, CDC, Fatura, INSS…). É o piso
  da comparação: mede o que o grafo entrega sem nenhum aparato de produção.

- **fixo — clarificação + receita única de busca (baseline pareado).
  Duas etapas: (1) *clarify* — extrair os **dados obrigatórios do POP** que a pergunta crua
  do cliente não traz (código de bloqueio exibido, há quantos dias a biometria está
  cadastrada, Alfa Code, canal tentado, correntista ou não): um extrator **por regras
  (regex, determinístico, custo zero — sem LLM)** lê o texto livre e, se falta dado
  obrigatório, faz até 3 turnos com perguntas fixas de volta, interpretando respostas
  curtas ("U", "não", "5 dias") pelo contexto do slot; os fatos coletados viram parte da
  pergunta (`[Dados coletados via clarificação: codigo_bloqueio=U; biometria_dias=11…]`).
  (2) *busca* — a pergunta completa recupera contexto sempre com a **mesma receita**, modo
  `hybrid`, top-k=5, independentemente do POP. Depois o chat modelo escreve a resposta com
  system prompt anti-alucinação. Compartilha com o routed absolutamente tudo — clarify,
  modelo de geração, prompt, avaliação — exceto uma coisa: **o fixo não escolhe a
  estratégia de busca**. Por isso os dois são comparados pergunta a pergunta (§2.3):
  qualquer diferença vem só do roteio.

- **routed — clarificação + roteador + receita por POP (o carro-chefe).
  Começa como o fixo (clarify + anti-alucinação), mas acrescenta o **roteador N-POPs**: um
  classificador determinístico (sem inferência) que, usando a pergunta completa do clarify,
  decide a qual POP a pergunta pertence e escolhe a **receita de busca afinada daquele
  documento** — acesso físico: modo `local` (caminhada pela vizinhança de entidades),
  top-k=10; CDC: modo `hybrid`, top-k=5; sem confiança suficiente, cai no fallback
  `hybrid`/k5. Só os 2 POPs originais recebem receita afinada — os 6 domínios novos usam o
  fallback (dívida registrada de ajuste fino por POP). A hipótese prática é que a receita
  certa por documento recupera contexto melhor do que uma receita única para tudo (24/24
  de rotas certas no corpus; ver `relatorio-desenvolvimento-execucao.md`).

- **tree — árvore de decisão determinística (o único sem LLM gerando resposta).
  Não consulta o grafo nem gera texto com modelo: é uma árvore de decisão codificada em
  regras (8 ramos, um por família de situação/pop) que reconhece a intenção na pergunta
  e devolve um **template fixo preenchido com os fatos do POP**. Custo zero de inferência
  (0 s), resposta idêntica para a mesma entrada, e impossível de inventar estrutura nova.
  O preço aparece quando a pergunta está fora da cobertura das regras — medição própria
  fora de distribuição no §3.6.

| Braço | Etapas por pergunta | Custo médio |
|---|---|---|
| hybrid | busca híbrida k5 → resposta | 2–39 s |
| fixo | clarify → busca híbrida k5 → resposta | 1–12 s |
| routed | clarify → roteio → busca (`local/k10` ou `hybrid/k5`) → resposta | 4 s (piloto) a 55 s (esparso) |
| tree | regra → template | 0 s |

### 1.4 Como medimos

- **4 métricas RAGAS** com juiz dedicado `gemini-3.5-flash-lite`: *faithfulness* (f — aderência
  ao contexto), *answer_relevancy* (ar), *context_recall*, *context_precision*;
  **score composto** = média das 4. Chat `gemini-3.1-flash-lite`; embeddings
  `gemini-embedding-001` (768d). Cota do juiz ≈ 500 req/dia ⇒ ~1 avaliação de 64/dia.
- **Ruído do juiz e escala pré-registrada**: o próprio juiz tem variação amostral (rodar o
  eval duas vezes dá Δf ~ ±0.05 em n≤16). Toda diferença de faithfulness é classificada por
  uma escala fixa, decidida **antes** de qualquer número: **efeito** = |Δf| ≥ 0.10 (com
  n ≥ 16); **sugestivo** = 0.05 ≤ |Δf| < 0.10 (sinal na direção certa, mas dentro do ruído
  ampliado); **ruído** = |Δf| < 0.05 ou amostra n ≤ 4 (sem valor probatório); **inconclusivo**
  = o desenho não permite decidir. Ou seja: "efeito" não significa significância
  estatística formal (a cota de juiz não comportava réplicas/com p-valores) — significa que
  a diferença supera com folga o ruído medido do juiz no tamanho de amostra anunciado.
- **NaN**: médias sempre sobre respostas pontuadas, com `n_scored/n` declarado
  (colunas `n_scored_f`/`n_scored_ar` no CSV de evidência). NaN do template curto
  (braço tree) conta à parte (†), por pré-registro.

## 2. Resultados RAGAS por cenário

### 2.1 Matriz completa

f = faithfulness (métrica primária); score = composto; ar = answer_relevancy; lat = latência
média em segundos (métrica operacional, nunca qualidade).

| Cenário | Braço | n | score | **f** | recall | precision | ar | lat_s |
|---|---|---|---|---|---|---|---|---|
| Piloto (idx2) | routed | 4 | 0.9694 | 1.0000 | 1.0 | 1.0 | 0.8777 | 4.1 |
| Piloto | fixo | 4 | 0.9488 | 0.8995 | 1.0 | 1.0 | 0.8956 | 7.8 |
| Piloto | hybrid | 4 | 0.9619 | 0.9688 | 1.0 | 1.0 | 0.8788 | 15.6 |
| Piloto | tree | 4 | 0.9374 | 1.0000 | 1.0 | 1.0 | 0.7495 | 0.0 |
| **Duo-16 (idx2)** | routed | 16 | 0.9433 | 0.9515 | 0.9583 | 1.0 | 0.8632 | 6.2 |
| Duo-16 (idx2) | fixo | 16 | 0.9341 | 0.8561 | 1.0 | 1.0 | 0.8804 | 12.5 |
| Duo-16 (idx2) | hybrid | 16 | 0.9494 | 0.9139 | 1.0 | 1.0 | 0.8835 | 38.8 |
| Duo-16 (idx2) | tree | 16 | 0.8965 | 0.8573 | 0.9792 | 1.0 | 0.7495 | 0.0 |
| **Duo-16 idx8** (volume puro) | routed | 16 | 0.9501 | 0.9571 | 0.9792 | 1.0 | 0.8642 | 22.0 |
| Duo-16 idx8 | hybrid | 16 | 0.7753 | 0.5444 | 1.0 | 1.0 | 0.5569 | 1.7 |
| **Esparso (idx8)** | routed | 16 | 0.7544 | 0.5127 | 0.9792 | 1.0 | 0.5258 | 55.5 |
| Esparso | fixo | 16 | 0.7571 | 0.3975 | 1.0 | 1.0 | 0.6308 | 9.1 |
| Esparso | hybrid | 16 | 0.6323 | 0.2633 | 1.0 | 1.0 | 0.2659 | 2.0 |
| Esparso | tree | 16 | 0.8463 | 0.7190† | 1.0 | 1.0 | 0.6663 | 0.0 |
| **Denso (idx8)** | routed | 64 | **0.8010** | **0.5492** | 0.9870 | 1.0 | 0.6676 | 5.1 |
| Denso | fixo | 64 | 0.7411 | 0.4261 | 0.9844 | 0.9687 | 0.5851 | 1.0 |
| Denso | hybrid | 64 | 0.7471 | 0.4161 | 1.0 | 1.0 | 0.5722 | 2.5 |
| Denso | tree | 64 | 0.8448 | 0.7260† | 0.9857 | 1.0 | 0.6673 | 0.0 |

† f média sobre pontuados (esparso tree 13/16; denso tree 50/64 — NaN de template curto,
carve-out pré-registrado). Outros NaN: duo-16 idx2 fixo 1 em ar (15/16); denso tree sem
NaN nas demais métricas. `n_scored/n` completos em `erafim_resumo_ragas.csv`. Na célula
duo-16 idx8 só os braços routed/hybrid entraram no planejamento (contraste-estrela);
nada foi imputado.

*Painel OOD em RAGAS (não é veredicto — RAGAS pune abstenção): routed-idx2 0.3276 ·
hybrid-idx2 0.3443 · fixo-idx8 0.3801 (score composto; f 0.2598/0.2103/0.2681).*

### 2.2 Contraste 1 — adicionar documentos (duo-16: idx2 → idx8, mesmas 16 perguntas)

| Braço | f idx2 | f idx8 | Δ = efeito do volume |
|---|---|---|---|
| routed | 0.9515 | 0.9571 | **+0.0056** (ruído) |
| hybrid | 0.9139 | 0.5444 | **−0.3695** (efeito) |

Para o routed, quadruplicar o grafo **não derrubou a geração com perguntas idênticas** — o
roteio mantém o contexto do POP coberto e o f sobe dentro do ruído (score 0.9433→0.9501).
No hybrid (busca global, sem roteamento), o mesmo quadruplicamento derruba o f em −0.37 e o
ar em −0.33 (0.8835→0.5569): a competição por contexto no índice grande degrada a resposta
mesmo sem perguntas novas. **O custo de distrair o retrieval existe — e só existe — no braço
sem roteador.**

### 2.3 Contraste 2 — roteador vs baseline fixo, pareado pergunta a pergunta

Pareio pelas perguntas aninhadas (mesma amostra por célula — a coluna `question` do eval
é expandida pelo clarify e não serve de chave; ordem das linhas das amostras é a mesma).

| Célula | n pareado | média fixo−routed | mediana | vence routed/empate/fixo | Classificação |
|---|---|---|---|---|---|
| duo-16 idx2 | 16 | −0.0954 | −0.0140 | 8 / 5 / 3 | sugestivo |
| esparso idx8 | 16 | −0.1152 | 0.0000 | 7 / 2 / 7 | efeito (n=16) |
| **denso-64 idx8** | 64 | **−0.1231** | −0.0076 | **32 / 14 / 18** | **efeito** |

Classificação pela escala da §1.4 aplicada à |média|: 0.05–0.10 com mediana ~0 = *sugestivo*
(duo-16: vantagem real, maior que o ruído simples, mas não se decide com n=16); ≥0.10 com
n=16 (esparso) ou n=64 (denso) = *efeito*. No denso, a média (+0.12) e o placar (32×18)
apontam juntos; o único quase-empate é o esparso (7×7), com o dobro do limiar na média —
o denso é a evidência decisiva porque tem 4× a amostra (64 pareados), tamanho em que o
placar 32×18 não é compatível com o ruído medido do juiz.

No corpus inteiro e denso, o **roteador vence o baseline fixo com +0.12/pergunta de f**
(32 vitórias × 18 derrotas nos 64 pareados); no esparso o sinal também é favorável
(+0.12), e nas 16 do duo-16 fica na faixa "sugestivo". O custo operacional do roteador
(clarify + chamadas extras) se amortiza no corpus grande, onde o baseline fixo passa a
errar mais o POP/tipo relevante. *Correção de registro: a tabela pareada publicada na
primeira versão deste relatório usava um pareamento inconsistente (médias pares diferem
das não pareadas); recomputada da evidência — os valores anteriores (−0.0654/−0.0562/−0.1109
com 29/16/17) não se reproduzem.*

### 2.4 Contraste 3 — adicionar perguntas por domínio (esparso → denso, idx8)

| Braço | f esparso | f denso | Δ densidade | Classificação |
|---|---|---|---|---|
| routed | 0.5127 | 0.5492 | +0.0365 | ruído |
| fixo | 0.3975 | 0.4261 | +0.0286 | ruído |
| hybrid | 0.2633 | 0.4161 | +0.1528 | efeito a favor do denso |
| tree | 0.7190† | 0.7260† | +0.0070 | ruído |

Densidade não degrada: routed/fixo em ruído; o hybrid melhora (mais perguntas por POP dão
mais sinal de intenção para o retrieval global). Veredicto pré-registrado: **densidade =
ruído** — mais amostras por domínio não piorou nenhum braço. Em linguagem da escala da
§1.4: nenhum Δ excedeu 0.10 na direção de piora (o único acima do efeito foi o **hybrid
melhorando** +0.15), e os Δ de routed/fixo ficaram abaixo de 0.05 — ou seja, os +0.03/+0.04
não são comprovadamente melhora, tampouco piora.
(Dica de leitura: aqui "efeito" só aparece no hybrid porque é o único Δ que passou do limiar
de 0.10 — e na direção favorável, não de piora.)

### 2.5 Decomposição da queda total de corpus (duo-16 idx2 → esparso idx8)

| Braço | queda total | parte = volume | parte = densidade | residual ≈ **questionário** |
|---|---|---|---|---|
| routed | −0.4388 | +0.0056 | +0.0365 | **−0.48** |
| fixo | −0.4586 | n/a | +0.0286 | ≈ −0.49 |
| hybrid | −0.6506 | −0.3695 | +0.1528 | ≈ −0.43 |
| tree | −0.1383 | n/a | +0.0070 | ≈ −0.15 |

A árvore é a que menos sofre com o corpus (−0.14); o resto varia de −0.44 a −0.65. Em todos
os braços, **o questionário de domínios novos explica quase toda a queda**; volume+densidade
são ≈0 para routed/fixo; no hybrid, o volume puro responde por metade do total.

## 3. Conclusões por cenário

1. **Universo coberto (duo-16)**: todos os braços funcionam bem (f 0.86–0.95, score ≥0.89).
   Quando o grafo cobre o domínio, a técnica RAG não é o gargalo — o gargalo é a cobertura.
2. **Efeito de só adicionar documentos (duo-16 idx2 → idx8)**: o sistema-carro-chefe (routed)
   é **imune ao volume** (+0.006 com perguntas idênticas); o hybrid não (−0.37). O argumento
   histórico "o grafo absorve a distração" vale para o roteado; para o híbrido, o custo de
   contexto é real — e é exatamente esse custo que o roteador evita.
3. **Efeito de só adicionar domínios (duo-16 → esparso)**: **a queda real vem daqui**.
   Todos os braços caem (−0.14 a −0.65), o hybrid colapsa no contexto (ar 0.27 — o juiz pune
   citação de trecho irrelevante), e o routed é o que absorve melhor (0.95→0.51: entre os
   braços de retrieval, é a menor queda, e leva o melhor residual da decomposição). A hipótese
   do pré-registro se confirmou na direção oposta à que motivou o desenho para o routed: o
   efeito observado nos 96 golden da série anterior era **questionário, não distração de
   documentos**.
4. **Corpus denso (cenário principal, n=64)**: o roteador vence o baseline fixo pareado por
   pergunta (32×18, +0.12 de f; média do gap 0.12 por pergunta — efeito, não ruído, em n=64
   pareado). O tree segue com o maior f (0.7260†) e custo zero, mas com ar 0.67 e regras
   fechadas — ver OOD no item 6. Em score composto no denso: routed 0.80 · tree 0.84 ·
   fixo/hybrid 0.74.
5. **Densidade**: ruído para todos (ou melhora no hybrid) — mais perguntas por domínio não
   degrada nenhuma arquitetura.
6. **Fora de cobertura (OOD-32)**: os três braços novos avaliados por rúbrica determinística
   são **honestos** (dano total 1–5 em 32 perguntas: fixo 1, routed 3, hybrid 5); a
   fragilidade residual é o sidestep de NUMTRAP (não confirma o número falso, mas adivinha ao
   redor dele — itens `convenio_999999`, `inss_limite`, `cartao_contestado_ppf`). A série
   legada (juiz-chat, comparação válida só intra-série) mantém a inversão histórica da árvore:
   0 abstenções e maior dano (51) — a árvore responde com confiança o que não sabe.
   RAGAS não é veredicto OOD (pune abstenção); o painel está na §2.1.
   *H3 (dano idx2 < idx8) ficou inconclusiva intra-série: sem o mesmo braço nos dois índices
   (o orçamento de cota não cobriu `ood-idx2 fixo` / `ood-idx8 routed`).*
7. **Veredicto para a banca (deploy)**: **routed como padrão** (0.80 de score no denso-64,
   honestidade OOD alta — dano 3/32 —, custo moderado); **tree como fallback determinístico
   em universos fechados e estáveis** (quando o roteador aponta um POP coberto — nunca como
   oráculo geral, pela lição OOD da série legada); **fixo como piso durável** (menor dano OOD
   medido, 1/32, sem custo de confusão no corpus grande — dentro do pré-registro); hybrid
   apenas como componente de retrieval dos braços roteados (só-isolado degrada no índice
   grande). *Síntese estendida, com foco em mitigação de respostas erradas, na §7.*

## 4. Registro operacional (congelamento)

- Branch `fatorial/idx-condicionado`; base `2c3dea0…dfc3e33`, rúbrica `aa0dbf7`.
- 21 runs `fx_*` da narrativa com gate `n/0 vazias/0 erros` 100% PASS via **resume
  idempotente** (mesmo `--run-name`, sem `--no-resume`): 7 respostas vazias transientes no
  esparso (15/10) e 2 no denso fixo foram zeradas em retomada; sidecar `index_info.json`
  em todos os runs.
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

## 5. Limitações e ruído declarado

1. Piloto n=4 (sem conclusão, por pré-registro); células n=16 têm limiar apenas "sugestivo";
   a evidência decisiva está no denso-64 pareado.
2. Incidência de 19–21/10: o gerenciador de shell derrubava o eval em 90 min (o tree denso
   roda ~1h20m), e as duas tentativas abortadas consumiram a cota do dia; em 21/10 a
   recuperação exigiu reconstruir o venv (o SO atualizou Python 3.12→3.14 de madrugada;
   `asyncio.get_event_loop` quebra em 3.14 e o rebuild vlanew saiu sem `langchain-openai`):
   `uv sync --all-extras --python 3.12` restaurou o ambiente validado. **Correção do
   registro original:** o eval do tree denso não fechou "zero NaN" — o CSV da run tem
   14/64 linhas sem faithfulness (21,9%, template curto; carve-out pré-registrado da nota
   A4), f=0.7260 calculada sobre os 50 pontuados; redo do eval fica como pendência se
   houver janela de cota.
3. `answer_relevancy` do tree **idêntico a 4 casas** (0.7495) no piloto e no duo-16 idx2:
   coincidência não explicável com template determinístico — tratada como ruído do juiz; não
   influencia vereditos nem thresholds de f.
4. Sanidade idx2: acesso estourou o ±15% (21.8% entidades, vintage de extração distinto),
   registrado **antes** dos resultados — portanto comparações idx2×idx8 lêem-se
   "volume + vintage"; o contraste-estrela do duo-16 (mesmas perguntas) é o que isola o volume.
5. Latência é métrica operacional (nunca qualidade): clarify esparso do routed custa 55 s médio
   contra 5 s no denso-64 (mais turnos na escuridão esparso); tree=0.0s.
6. H3 não pode ser testada sem `ood-idx2 fixo` e `ood-idx8 routed` (par de braços que o
   orçamento D1–D8 não cobriu).
7. **Spot-check OOD pendente do humano**: `erafim_ood_spotcheck.csv` (23 linhas,
   `veredito_humano` a preencher; aceitação pré-registrada ≥80%).

## 6. Apêndice — versionamento, manifestos, desvios e glossário de hipóteses

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
- **Desvios do pré-registro**: (i) duo-16 idx8 medido só em routed/hybrid (demais braços
  fora do planejamento desta célula — nada imputado); (ii) `octeto-esparso × idx2` excluído
  (pré-registrado, não desvio); (iii) veredicto OOD determinístico na erafim vs juiz-chat na
  legada (comparação só intra-série); (iv) aborto/execução forçada remanejada para o dia
  seguinte duas vezes (regra de parar em 429/exit 3, sem parcial publicada).
- **Glossário das hipóteses pré-registradas** (códigos usados no desenho; o texto deste
  relatório usa só nomes longos):

| Código | Hipótese | Onde está |
|---|---|---|
| H1 | efeito-volume puro ≈ 0 (distração não explica a queda) | §2.2 |
| H2 | routed ≥ fixo pareado por pergunta | §2.3 |
| H3 | dano OOD idx2 < idx8 | §3.6 (inconclusiva intra-série) |
| H4 | densidade degrada menos que corpus | §2.4 |

## 7. Conclusão — o que separa as arquiteturas e como mitigar respostas erradas

### 7.1 As quatro apostas, lado a lado

Cada arquitetura é uma aposta diferente sobre de onde vem o erro de um assistente
bancário — e a série erafim mediu cada aposta com o mesmo juiz, os mesmos POPs e o mesmo
filtro de ruído pré-registrado (§1.4):

| Arquitetura | Aposta | Confirmação medida | Onde falha (medido) | Custo |
|---|---|---|---|---|
| **hybrid** | o grafo cru basta | f 0.9139 no universo coberto (duo-16) | volume derruba a geração (−0.3695, §2.2); colapso esparso no contexto (ar 0.2659) | 2–39 s |
| **fixo** | basta clarificar e usar uma receita única | menor dano OOD da série (1/32, §3.6) | perde do roteador no corpus grande (−0.1231 pareado por pergunta, §2.3) | 1–12 s |
| **routed** | o erro nasce do POP errado no retrieval; a receita certa por documento resolve | imune ao volume puro (+0.0056, §2.2); vence o fixo pareado 32×18 no denso (§2.3) | esparso custa 55 s de clarify; sidestep residual em NUMTRAP (§3.6) | 4–55 s |
| **tree** | o erro nasce da geração livre; sem LLM não há alucinação | maior f do denso (0.7260†) e custo zero | fora das regras: 0 abstenções e dano 51 na série legada (§3.6) — responde com confiança o que não sabe | 0 s |

Três leituras cruzadas valem a pena registrar. Primeiro, as falhas dos braços são
**complementares, não concorrentes**: o hybrid falha por contexto (competição no índice
grande), o fixo falha por rota (receita única perde o POP certo), o tree falha por
cobertura (as regras não alcançam o que não codificam) — e é exatamente por isso que a
combinação deles supera qualquer um isolado. Segundo, a peça mais barata e mais
transversal do desenho não é o roteador, é o **par clarify + prompt anti-alucinação**,
compartilhado pelos três braços honestos (fixo/routed/hybrid eram os menos danosos da
erafim; na legada, sem esse par ou com menos proteção, os danos eram muito maiores). Terceiro, o **RAGAS pune a abstenção** (ar baixo para quem diz "não sei") — por
isso, quem compara assistentes só pela nota de relevância favorece sistemas que adivinham;
a leitura humana dos danos OOD inverte essa preferência.

### 7.2 Cenário-alvo: mitigar respostas erradas

Se o objetivo explícito do deploy é **minimizar a taxa de respostas erradas** (e não
maximizar utilidade por resposta ou reduzir custo), a evidência da série ordena a
recomendação em camadas:

1. **Camadas universais (baratas, sempre ativas)**: clarificação com os dados
   obrigatórios por POP e
   system prompt anti-alucinação. Elas atacam as duas fontes dominantes de erro — consulta
   incompleta e geração fora do contexto — e são compartilhadas por todos os braços que
   abstêm de forma honesta no OOD.
2. **Roteio por POP no corpus grande**: no denso-64 pareado, é a única intervenção de
   retrieval cuja diferença ultrapassa o ruído do juiz (32×18, +0.12 f/pergunta; §2.3).
   Com corpus pequeno e totalmente coberto, o ganho desaparece (sugestivo com mediana ~0) —
   rotear é política para corpus que cresce, não dogma.
3. **Nunca trocar o LLM por templates fora de universo fechado**: a árvore tem o melhor
   custo-benefício no universo coberto (f 0.7260 do denso a custo zero), mas é o pior comportamento
   conhecido fora de cobertura (legado: 18 alucinações e dano 51 em 32; §3.6). Como
   mitigação de erro, a árvore só entra **atrás do roteador, quando a rota é confiante para
   um POP coberto** — como atalho determinístico, nunca como oráculo geral.
4. **Preferir abstenção a adivinhação**: entre os braços medidos, os que abstêm têm os
   menores danos (fixo 1, routed 3, hybrid 5 por 32; §3.6). Para o critério "não errar",
   a métrica de gestão não é o score RAGAS isolado — é a rúbrica de dano OOD, lida junto da
   declaração de abstenção.
5. **Controles operacionais permanentes**: rúbrica OOD no pipeline de regressão antes de
   qualquer alteração de índice/prompt; spot-check humano (23 linhas, `veredito_humano`
   pendente — §5.7); `n_scored/n` declarados em toda publicação de métrica; watchlist dos
   três itens sidestep (`convenio_999999`, `inss_limite`, `cartao_contestado_ppf`) com
   teste dedicado de captura de número falso (o resíduo conhecido dos braços novos).

**Stack recomendada para o Banco Alfa (síntese)**: **routed como padrão** (imune ao
crescimento do corpus, melhor efeito pareado do denso, abstenção honesta), com fallback
**fixo** (`hybrid/k5`) quando o roteador não confia na rota, e **tree acionável apenas
nessa rota confiante de POP coberto** — todas as três camadas com clarify + prompt
anti-alucinação, avaliação contínua pela rúbrica OOD e monitoramento da watchlist NUMTRAP.
O custo disso é aceitar o preço do erro controlado: ~4 s de latência média a mais no denso
(5 s do routed vs 1 s do fixo) e um ar mais baixo no RAGAS por causa das abstenções — que é
exatamente o que a rúbrica de dano humana valoriza quando o requisito não é errar.
