# PROMPT — regenerar o relatório comparativo (série erafim, do zero)

Propósito: um agente novo consegue reproduzir `relatorio-tcc/relatorio-comparativo-final.md`
**lendo apenas `runs/`** — sem editar `src/`, sem re-rodar pipelines, sem usar a rede.

## Pré-condições

- Branch `fatorial/idx-condicionado`; índices **congelados** em `lightrag_2pops_db/` (idx2)
  e `lightrag_ollama_db/` (idx8); runs `fx_*` em `runs/` com gates de n/0-vazias/0-erros e
  sidecars `index_info.json`. Qualquer divergência dessas condições → abortar antes
  do passo 1 e reportar.
- Regras de cota: 1 eval-64/dia no balde do juiz; **nunca publicar parcial**; evals
  **um comando por chamada**; timeout >= 90 min; parar em 429/exit 3.

## Passos

1. **Amostragem**: `python3 relatorio-tcc/evidencias/amostra_fatorial.py` (seed 42,
   determinística) — valida 64 IDs únicos, aninhamento piloto ⊂ duo-16 ⊂ denso-64 e
   esparso ⊂ denso; gera sidecars em `/tmp` (células, targets e goldens convertidos).
   OOD-32 = `data/ood_scenarios.json` (32 cenários, ordem canônica).
2. **Runs** (idempotentes, mesmos parâmetros usados nos runs existentes (resumidos em `relatorio-tcc/evidencias/erafim_resumo_ragas.csv`).
   Cada run já tem gate e sidecar; **retomar com o mesmo `--run-name`, sem `--no-resume`**).
   Convenção de nome: `fx_<celula>_<braco>`; `STORAGE_DIR=lightrag_2pops_db` só para braços
   retrieval idx2; `CONCURRENCY_LIMIT=1` no `run-direct`. **Estado: série fechada** — os 25
   runs `fx_*` têm eval (a última célula, `fx_denso_idx8_tree`, em 21/10, com 14/64 NaN de
   faithfulness de template curto — carve-out pré-registrado com †, `n_scored_f=50/64` no
   resumo); redo opcional do eval do tree pende janela de cota (1/dia).
3. **Evals** (1/dia): `ragbench eval --run-id <run>`; híbrido sempre com
   `--golden /tmp/cel_<celula>_golden.json`; checar `n` e NaN após cada chamada;
   referência de NaN = `n_scored/n` declarado (nunca imputar).
4. **Rúbrica OOD** (`evidencias/erafim_ood_rubrica.csv` + `_notas.md`): extração por match
   de `pergunta_completa` (2 nuances de clarify: resolver por prefixo da base),
   triagem determinística conforme regras da `erafim_ood_notas.md`; dump em `/tmp/rub_raw.json`.
5. **Tabela canônica**: gerar `evidencias/erafim_resumo_ragas.csv` conforme o script da
   evidência (médias das 4 métricas por run + `score_composto` + `latencia_media_s`).
6. **Contrastes** (regras `tcc-serie-antiga:relatorio-tcc/evidencias/criterios_fatorial.md`):
   efeito se |Δf| ≥ 0.10 (n ≥ 16); sugestivo 0.05–0.10; ruído < 0.05 (ou n=4). Deltas
   pareados routed×fixo por pergunta (join pela coluna `question` do eval).
7. **Relatório final**: escrever `relatorio-comparativo-final.md` com a estrutura
   §1–§9 (resumo executivo com vereditos H1–H4; desenho; registro operacional com 429s;
   matriz por célula; contrastes; OOD; respostas; limitações; apêndice com commits,
   manifestos e desvios). Escrever apenas com números verificados em `runs/`; as duas
   células PENDENTE-EVAL ficam sinalizadas com "**PENDENTE-EVAL**" até completar —
   nunca publicar a matriz sem eles.

## Não fazer

- Não rodar `index`, `uv sync`, trocar `.env`, trocar prompts, mexer em `src/`.
- Não publicar tabela sem reconferir os CSVs de `runs/<id>/`.
- Não comparar a rúbrica erafim com a legada como se fossem o mesmo juiz
  (determinística vs chat-assistida: comparar intra-série sempre).
- Antes de commitar `docs(tcc): …`, ler o diff completo e regenerar
  `erafim_resumo_ragas.csv` uma vez para conferir números (deltas incl. pareados).
