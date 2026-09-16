# 🔍 Probe de retrieval por modo

Cenários: 5 | modos: hybrid, local, global, naive | top_k=5

| Cenário | Esperado | Modo | Previsto | Acertou | acesso | cdc |
| --- | --- | --- | --- | --- | --- | --- |
| acesso_sequestro_senha8 | pop_acesso_pf.md | hybrid | pop_cdc_pf.md | ❌ | 7 | 242 |
| acesso_sequestro_senha8 | pop_acesso_pf.md | local | pop_cdc_pf.md | ❌ | 3 | 49 |
| acesso_sequestro_senha8 | pop_acesso_pf.md | global | pop_cdc_pf.md | ❌ | 7 | 240 |
| acesso_sequestro_senha8 | pop_acesso_pf.md | naive | pop_cdc_pf.md | ❌ | 188 | 306 |
| acesso_titular_solidario | pop_acesso_pf.md | hybrid | pop_cdc_pf.md | ❌ | 6 | 160 |
| acesso_titular_solidario | pop_acesso_pf.md | local | pop_cdc_pf.md | ❌ | 3 | 50 |
| acesso_titular_solidario | pop_acesso_pf.md | global | pop_cdc_pf.md | ❌ | 6 | 157 |
| acesso_titular_solidario | pop_acesso_pf.md | naive | pop_cdc_pf.md | ❌ | 188 | 306 |
| acesso_portador_adicional | pop_acesso_pf.md | hybrid | pop_cdc_pf.md | ❌ | 7 | 242 |
| acesso_portador_adicional | pop_acesso_pf.md | local | pop_cdc_pf.md | ❌ | 3 | 49 |
| acesso_portador_adicional | pop_acesso_pf.md | global | pop_cdc_pf.md | ❌ | 7 | 240 |
| acesso_portador_adicional | pop_acesso_pf.md | naive | pop_cdc_pf.md | ❌ | 188 | 306 |
| acesso_sms_nao_cadastrada | pop_acesso_pf.md | hybrid | pop_cdc_pf.md | ❌ | 6 | 236 |
| acesso_sms_nao_cadastrada | pop_acesso_pf.md | local | pop_cdc_pf.md | ❌ | 3 | 50 |
| acesso_sms_nao_cadastrada | pop_acesso_pf.md | global | pop_cdc_pf.md | ❌ | 6 | 233 |
| acesso_sms_nao_cadastrada | pop_acesso_pf.md | naive | pop_cdc_pf.md | ❌ | 188 | 306 |
| acesso_site_biometria_7dias | pop_acesso_pf.md | hybrid | pop_cdc_pf.md | ❌ | 6 | 161 |
| acesso_site_biometria_7dias | pop_acesso_pf.md | local | pop_cdc_pf.md | ❌ | 3 | 50 |
| acesso_site_biometria_7dias | pop_acesso_pf.md | global | pop_cdc_pf.md | ❌ | 6 | 158 |
| acesso_site_biometria_7dias | pop_acesso_pf.md | naive | pop_cdc_pf.md | ❌ | 188 | 306 |

**Acerto global: 0/20**
- hybrid: 0/5
- local: 0/5
- global: 0/5
- naive: 0/5