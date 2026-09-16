# Sweep top_k — 5 piores casos de acesso (queries enriquecidas)

| top_k | hybrid (acesso×CDC, chars) | local (acesso×CDC, chars) |
|---|---|---|
| 5 | 0/5 (6×208, 27k) | 0/5 (3×50, 10k) |
| 10 | 0/5 (159×342, 62k) | **5/5** (125×67, 31k) |
| 20 | 0/5 (213×375, 76k) | 4/5 |
| 40 | 0/5 (244×401, 85k) | 2/5 |

Checagem CDC (k=10): hybrid 4/4, local 1/4.
Conclusão: top_k maior não corrige o viés em hybrid (só infla o contexto);
local/k=10 é ótimo para acesso mas inverte o viés. Daí o roteador por doc.
