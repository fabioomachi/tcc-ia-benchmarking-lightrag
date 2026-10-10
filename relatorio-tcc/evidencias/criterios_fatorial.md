# Pré-registro — desenho fatorial com índice condicionado

Documento versionado **antes** das runs (10/10/2026). Qualquer desvio deve ser
registrado aqui com data e motivo — nunca decidido após ver os números.

## Desenho

Células `<perguntas>-<índice>`: `piloto-duo2-idx2` (2×2, n=4),
`duo-denso-idx2` (2×8, n=16), `duo-denso-idx8` (mesmas 16, n=16),
`octeto-esparso-idx8` (8×2, n=16), `octeto-denso-idx8` (8×8, n=64),
`ood-idx2`/`ood-idx8` (32 OOD fixas). Braços: routed, fixo, hybrid, direct,
tree (OOD-idx8 sem fixo = lacuna registrada; OOD inclui fixo nas duas).
Amostragem: seed 42, estratificada por `tipo`, IDs publicados
(`evidencias/amostra_fatorial.json`, a gerar no D1).

## Contrastes primários (conclusivos se dentro do orçamento de ruído)

1. `duo-denso-idx2 × duo-denso-idx8`: efeito-volume puro (mesmas perguntas).
2. Routed × fixo pareado por pergunta, por célula.
3. Dano OOD `idx2 × idx8` (rúbrica A/B/C).
4. Densidade: `piloto×duo(idx2)`, `esparso×denso(idx8)`.
5. `duo-denso-idx2 × octeto-esparso-idx8`: efeito-corpus total.

Exploratório (sem conclusão): resto, trajetórias por POP/tipo, latências.

## Gatilhos numéricos

- **Aborto de célula**: >15% dos jobs do eval com retry exaurido por 429/NaN
  → refazer a célula em outro dia; nunca publicar parcial como final.
- **Sanidade idx2**: divergência de entidades por doc ≤±15% vs idx8.
  Resultado D1 real: acesso 21,8% (ESTOUROU), CDC 9,6% (OK). Decisão
  registrada: contraste A×A publicado como "volume + vintage de extração".
- **Ruído do juiz**: deltas <0,05 em células n≤16 não são achados.
- **Piloto n=4**: sem conclusão; só valida o pipeline.
- **NaN**: médias sempre sobre pontuadas com `n_scored/n` declarado.

## Congelamento D1–D8

Nenhum `index`, `src`, `.env`, reindex ou `uv sync`. Registrar: commit hash,
SHA dos manifests idx2/idx8, seed, janela de datas, paradas por 429.

## Exclusões deliberadas

- `octeto-esparso × idx2` (documento ausente ≠ volume; custo sem valor).
- RAGAS como veredito OOD (pune abstenção); veredito = rúbrica + spot-check.
