# Pré-registro — desenho fatorial com índice condicionado

Documento versionado **antes** das runs (10/10/2026). Qualquer desvio deve ser
registrado aqui com data e motivo — nunca decidido após ver os números.

## Desenho

Células `<perguntas>-<índice>`: `piloto-duo2-idx2` (2×2, n=4),
`duo-denso-idx2` (2×8, n=16), `duo-denso-idx8` (mesmas 16, n=16),
`octeto-esparso-idx8` (8×2, n=16), `octeto-denso-idx8` (8×8, n=64),
`ood-idx2`/`ood-idx8` (32 OOD fixas). Hipóteses: routed, fixo, hybrid, direct,
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

## Plano de medição por atividade (o que se mede, contra o que, critério)

Legenda de decisão por contraste: **efeito** (|Δ|≥0,10 em faithfulness com
n≥16), **sugestivo** (0,05–0,10 ou n=16 com NaN), **ruído** (<0,05 ou n=4),
**inconclusivo** (gatilho de aborto disparado).

### A1. Amostragem
- **Medir**: distribuição `tipo`×POP por célula vs fonte (96); lista de IDs.
- **Comparar**: proporções da célula contra as do golden96 (desvio ocular;
  n pequeno demais para qui-quadrado).
- **Critério**: publica-se `evidencias/amostra_fatorial.json`; qualquer
  re-amostragem após ver resultados invalida a célula.

### A2. Build idx2 + sanidade
- **Medir**: nº de entidades por doc (idx2 vs idx8), SHA dos POPs, hash do manifest.
- **Comparar**: divergência % por doc contra tolerância ±15%.
- **Critério**: dentro → segue; fora → 1 rebuild; persistindo → contraste A×A
  publicado como "volume + vintage de extração" (foi o ocorrido: 21,8%/9,6%).

### A3. Runs (por run)
- **Medir**: n do checkpoint == n da célula; taxa de sucesso; respostas vazias;
  latência média; turnos de clarify (média); `rota==source` (routed).
- **Comparar**: nada ainda (sem conclusão por run isolada).
- **Critério**: **0 respostas vazias** (resume até zerar); manifest n == célula
  (merge em resume); latência só operacional, nunca qualidade.

### A4. Evals (por run)
- **Medir**: 4 métricas RAGAS + `n_scored/n` + contagem de NaN por métrica.
- **Comparar**: nada ainda.
- **Critério**: >15% de jobs com retry exaurido por 429/NaN → **aborta a
  célula** (refazer outro dia); NaN de template curto (árvore) conta à parte
  com †, não como falha.

### A5. Rúbrica OOD (por braço×índice)
- **Medir**: contagens A/B1/B2/B3/C + dano total + dano por tipo OOD.
- **Comparar**: `ood-idx2 × ood-idx8` por braço (corpus menor alucina menos?).
- **Critério**: spot-check ≥80% de concordância confirma a rúbrica; abaixo,
  revisar regex/rúbrica **antes** de publicar (nunca após ver totais).

### A6. Comparações finais (relatório comparativo)
| Contraste | Medida | Decisão esperada se H verdadeira |
|---|---|---|
| `duo-denso-idx2 × duo-denso-idx8` | Δ faithfulness por braço (mesmas 16) | Efeito = distração pura do volume |
| routed × fixo pareado por pergunta/célula | Δ médio + fração de perguntas com Δ>0 | Efeito em toda célula = hipótese confirmada |
| `duo-denso-idx2 × octeto-esparso-idx8` | Δ por braço (n=16 ambos) | Efeito-corpus total (distração + questionário) |
| densidade (`piloto×duo`, `esparso×denso`) | Δ por braço | Efeito menor que o de corpus (H4) |
| dano OOD idx2 × idx8 | Δ dano por braço | idx2 < idx8 (H3) |

### A7. Gráficos (o que cada um prova)
- **Interação corpus×densidade** (faithfulness por hipótese): linhas não
  paralelas = o corpus afeta hipóteses de forma diferente (achado) vs
  paralelas = degradação uniforme.
- **Painel `duo-denso-idx2×idx8`**: barras pareadas por braço = efeito-volume puro.
- **Dano OOD por índice**: idx2 < idx8 sustenta H3.
- **Deltas pareados routed×fixo**: histograma por pergunta mostra se o ganho é
  generalizado ou puxado por poucas perguntas.
