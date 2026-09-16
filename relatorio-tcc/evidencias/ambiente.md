# Ambiente e reprodução

- Branch `hypothesis/teste-inicial`, commit `9bbe766`
- Modelos (.env): index `gemini-3.5-flash-lite`, chat `gemini-3.1-flash-lite`,
  juiz `gemini-3.5-flash-lite`, embeddings `gemini-embedding-001`/768
- Índice LightRAG: 2 docs, 12 chunks, 55 + 94 entidades (14/09)
- Comandos:
  - `uv run ragbench run-clarify --run-name X --mode hybrid --max-clarify-turns 3 --no-resume`
  - `uv run ragbench run-direct --input completa|incompleta --run-name Y --no-resume`
  - `uv run ragbench eval --run-id <id>`
  - `uv run ragbench probe-retrieval --run-name Z --top-k 10`
- Cota: eval de `exp_direct_incompleta` pendente (free-tier 500 req/dia esgotada em 16/09).
