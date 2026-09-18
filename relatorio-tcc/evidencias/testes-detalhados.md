# Anexo — o que cada teste verifica (158 testes, linha a linha)

> Gerado a partir do código em `tests/unit/`. Para rodar tudo:
> `uv run pytest tests/ --no-cov -q` (esperado: **158 passed**).
> Cada item abaixo diz **o que** o teste verifica e **por que** isso importa
> para o experimento. Nomes de arquivo:função permitem localizar cada caso.

## test_tree.py — árvore de decisão (32 casos)

Cada linha da tabela `test_ramos` alimenta a árvore com uma pergunta e exige
o ramo exato (regra do POP) — é assim que se prova que as ~40 regras foram
codificadas certo, sem LLM no caminho:

| Pergunta de entrada | Ramo exigido | Regra do POP que ele codifica |
|---|---|---|
| senha 6 dígitos bloqueio 'U' pelo site sem Alfa | `ACESSO_U_SITE_AGENCIA` | U só altera; site veda U/8 sem Alfa; biometria >7d (§3.1.2, §3.1.4) |
| senha bloqueio 'U' (geral) | `ACESSO_U_GERAL` | U nunca desbloqueia (§3.1.4, §3.2.4) |
| senha 8 dígitos bloqueio '8' | `ACESSO_8_ALTERACAO` | Sem senha atual → Alteração, não Desbloqueio (§3.2.2, §3.2.4) |
| sequestro, bloquear senha-8 | `ACESSO_SEQUESTRO_X98` | Emergência → SISRET X98 rota 800050; Conta de Acesso intacta (§4.2.2) |
| marido bloqueou, titular solidário | `ACESSO_SOLIDARIO` | Senhas compartilhadas; bloqueio de um trava todos (Nota c) |
| deficiente visual e código de acesso | `ACESSO_DEFICIENTE_CODIGO` | Dispensa com registro; conjunta só o titular (§5.a) |
| exterior com bloqueio U | `ACESSO_EXTERIOR_U` | E-mail MCI não vale p/ U; só Tóquio; procurador (§7) |
| cartão adicional sem senha | `ACESSO_ADICIONAL` | Adicional não correntista → agência (§8) |
| senha por SMS não cadastrada | `ACESSO_SMS_ALTERACAO` | SMS só p/ alteração, nunca 1ª senha (§6) |
| chip trocado não funciona | `ACESSO_CHIP_TAA` | Atualizar chip na TAA (§3.1.2) |
| código 'Q' no celular | `ACESSO_CODIGO_Q` | Pendente de TAA + biometria >7d (§2.2) |
| App Alfa com senha do cartão | `ACESSO_CONTA_VS_SENHA8` | Credenciais distintas; identificar via X69 (§4.2.1–4.2.2) |
| bloqueio U, SAC resolve? | `ACESSO_SAC_ALCADA_U` | Rotinas 50130/50131/50112 (§3.1.2, §3.2.2) |
| cancelar CDC 2881 convênio 700001 | `CDC_CANCEL_2881_DOC` | Restrito ao DOC 800020 + margem p/ reaverbação (§4) |
| cancelar 2881 convênio 700017 | `CDC_CANCEL_2881_C17` | Restrito à Superintendência III 800030 (§4) |
| boleto + débito duplicados | `CDC_DUPLICIDADE_BOLETO` | Estorna boleto 1º, supervisor em CDC 13.23 (§2) |
| consignado INSS descontado 2× | `CDC_CONSIG_DEVOLUCAO` | D+2, exceto INSS 5º dia útil e MPDG 1º (§2) |
| amortização linear no consignado | `CDC_LINEAR_VEDADO` | Linear vedado; preferir decrescente (§5.1) |
| operação em perdas | `CDC_PERDAS` | Não informar prejuízo; CDC 13-34 + supervisor (§5.2) |
| ANC vencida sem limite | `CDC_ANC_SEM_LIMITE` | Agência com docs <90 dias; rotina 50105 (§3) |
| empréstimo de correspondente, fraude | `CDC_FRAUDE_CORRESPONDENTE` | Ocorrência 50113/50114/50115, unidade 800010 (§7.2) |
| cancelar Limite Especial usando | `CDC_LIMITE_CANCELAMENTO` | Cobrir saldo antes; Ouvidoria direto (§8.1) |
| CDC 13º no aniversário | `CDC_13_ANIVERSARIO` | Cobrança+vencimento no mês de aniversário (§2) |
| antecipação IRPF e FGTS | `CDC_IRPF_FGTS` | IRPF: restituição ou vencimento; FGTS: repasse (§2) |
| repactuação com Op pendente | `CDC_REPACTUACAO` | Pendente exclui; confirmada só liquida (§4.4) |
| débito sem autorização pós-01/03/21 | `CDC_AUTORIZACAO_2021` | Exige autorização (CMN 4.790); rotina 50104 |

Outros testes do arquivo: `test_site_biometria_ok_vs_pendente` (biometria com
10 dias libera o site, sem dias pede o dado — decide entre responder e
perguntar); `test_fallback_para_fora_dos_pops` (fora do domínio → fallback
honesto, nunca chute); `test_detect_doc_por_slots` (slots decidem o POP antes
das keywords); `test_engine_protocolo` (mesmo contrato dos outros motores:
modelo, query, embeddings, insert/finalize); `test_run_tree_gera_artefatos…`
(`run-tree` gera checkpoint+manifest+golden com `mode=tree`/`source=tree_engine`);
`test_run_tree_help` (CLI registra o comando).

## test_clarifier.py — extração de slots e loop (10 casos)

- `test_extract_bloqueio_u`: `bloqueio 'U'` → `codigo_bloqueio=U`.
- `test_extract_nao_captura_letra_de_bloqueio_pelo`: regressão do bug real —
  “bloqueio **p**elo site” capturava `P` como código; agora não captura nada.
- `test_extract_sem_alfa_e_biometria`: “sem Alfa, biometria há 5 dias, pelo
  site” → 3 slots corretos de uma vez.
- `test_extract_tipo_cliente`: “sou correntista” vs “não sou correntista”.
- `test_missing_e_next_question`: lista o que falta e formula a próxima pergunta.
- `test_should_ask_more`: para quando acabam slots ou turnos.
- `test_merge_e_enriched_query`: monta a query enriquecida (`slot=valor`) que
  vai ao grafo.
- `test_collect_slots_interactive_simulado`: diálogo simulado (“U”, “não”,
  “5 dias”) preenche 3 turnos corretamente, inclusive resposta curta “U”.
- `test_collect_respeita_max_turns`: respostas vagas não estouram o limite.
- `test_clarify_settings_default`: padrão `max_turns=3` na config.

## test_router.py — roteador só-grafo (13 casos)

- `test_normalize_tira_acento_e_caixa`: “Agência” casa com “agencia”.
- `test_score_docs_pondera_tokens_exclusivos`: token só de um doc vale 1.0,
  compartilhado 0.25 (genéricos não decidem a rota).
- `test_score_docs_expansao_de_slots`: valor cru `U` vira termos de entidade
  (“senha de 6 dígitos…”) antes do overlap.
- `test_route_margin`: margem = melhor menos segundo melhor.
- `test_route_by_graph_confiante_e_estrategia`: overlap claro → doc + modo
  certo (acesso→local/k10) + confiante.
- `test_route_by_graph_sem_overlap_cai_em_fallback` /
  `test_route_by_graph_sem_indice`: sem evidência → estratégia padrão (sem
  regressão).
- `test_next_discriminative_slot_prioriza_acesso`: pergunta o slot que mais
  separa os docs primeiro.
- `test_load_entity_index_mapeia_docs` / `test_load_entity_index_sem_arquivos`:
  lê o índice real do disco (ou retorna vazio com dignidade).
- `test_guided_para_cedo_quando_margem_estabiliza`: para antes do limite
  quando o grafo “se decide” (a inteligência do loop).
- `test_guided_sem_indice_preenche_como_classica`: sem índice, comporta-se
  como o loop fixo antigo.
- `test_routing_settings_default`: `enabled`, `margin_min=0.05`, `k10/k5`.

## test_run_clarify.py — batch com clarificação (5 casos)

- `test_simulate_preenche_slots_e_respeita_max`: preenche e obedece o teto.
- `test_simulate_sem_valor_para`: sem valores simulados, 0 turnos (não inventa).
- `test_simulate_pula_slots_sem_valor`: regressão real — cenário CDC sem
  `codigo_bloqueio` travava em 0 turnos; agora pula e preenche os 2 úteis.
- `test_run_clarify_gera_mesmos_artefatos_do_run`: checkpoint+CSV+MD+manifest
  com fake engine (prova o contrato de artefatos do `eval`).
- `test_run_clarify_help`: comando registrado no CLI.

## test_direct.py — baseline LLM puro (6 casos)

- `test_usa_modelo_do_chat`: usa o mesmo modelo do chat (isola só o retrieval).
- `test_aquery_sem_contexto_recuperado`: prompt não contém chunks/contexto;
  resposta vem só do modelo.
- `test_lifecycle_noop_e_ainsert_avisa`: sem storages (initialize/finalize
  vazios, insert avisado e ignorado).
- `test_system_prompt_ptbr`: prompt em pt-BR.
- `test_run_direct_gera_artefatos_com_baseline_engine`: records com
  `mode=direct` + `source=baseline_engine` e `golden.json` próprio.
- `test_run_direct_rejeita_input_invalido`: `--input` só aceita
  completa/incompleta.

## test_cli.py — comandos fim a fim com fakes (14 casos)

- `test_health_ok` / `test_health_failure`: ambiente operacional vs em falha
  (códigos de saída 0/1).
- `test_index_seeds_and_inserts`: semeia os 2 POPs padrão e insere com marcador
  de origem.
- `test_generate_dataset`: gera 1 pergunta e registra saída.
- `test_run_benchmark_end_to_end`: `run` gera checkpoint+CSV+MD e cópias em
  `resultados/`.
- `test_run_no_queries`: pasta vazia → mensagem, sem erro.
- `test_eval_run_id` / `test_eval_no_checkpoint`: avalia checkpoint existente;
  sem checkpoint → erro 1.
- `test_build_run_id`, `test_resolve_eval_db_path*`: nomes de run e resolução
  do checkpoint (inclusive “mais recente”).
- `test_apply_chat_model_override_copies`: override de modelo não muta o global.
- `test_discover_and_seed_pops`, `test_run_and_eval_helpers_importable`:
  utilitários presentes e importáveis.

## test_runner_checkpoint.py — lote com checkpoint (5 casos)

- `test_str_response_success_and_checkpoint_saved`,
  `test_stream_response_is_consumed`: respostas diretas e em stream viram
  records `success` salvos.
- `test_empty_response_marks_error_and_still_checkpoints`: resposta vazia é
  erro, mas checkpoint persiste (não perde o lote).
- `test_engine_exception_marks_error_and_checkpoints`: exceção vira record de
  erro com mensagem (foi assim que os 429s ficaram registrados nos _35).
- `test_resume_skips_completed_queries`: `--resume` pula o já concluído.

## test_ragas_prepare.py + test_ragas_report.py — avaliação (12 casos)

- `test_normalize_and_is_gemini`, `test_select_relevancy_metric_by_transport`:
  Gemini usa `strictness=1` (endpoint rejeita múltiplos candidatos).
- `test_load_golden_map_*`: golden ausente/corrompido não quebra; chaves
  normalizadas casam com queries enriquecidas.
- `test_prepare_dataset_joins_golden_and_context`: junta resposta + ground
  truth + texto do documento-fonte; `test_prepare_dataset_empty_raises`: sem
  records válidos, erro explícito (foi o que barrou o eval do _35 com 21 erros).
- `test_run_evaluation_uses_injected_fn` / `test_run_evaluation_wraps_error`:
  RAGAS injetável (testes sem rede) e erro embrulhado em `EvaluationError`.
- `test_ragas_report_*`: médias, agrupamento por tipo, NaN conta só nas
  colunas de métrica, DataFrame vazio não quebra o relatório.

## test_lightrag_engine.py — adaptador do grafo (9 casos)

- `test_build_entity_prompt_appends_once`: ontologia bancária injetada 1×
  (idempotente).
- `test_build_llm_messages_order_and_constraint`: system em pt-BR + histórico
  + pergunta, nessa ordem.
- `test_invalid_role_raises_without_network`, `test_role_aware_model_and_inject_prompts`,
  `test_injected_clients_are_kept`: roles index/chat, modelo por role, DI.
- `test_custom_llm_func_delegates_role_model`,
  `test_initialize_uses_factory_and_role_timeouts`,
  `test_aquery_requires_initialize`, `test_aquery_maps_mode_and_top_k`,
  `test_ainsert_and_finalize`: ciclo de vida e repasse de modo/top_k/stream.

## test_ollama_retry.py + test_ollama_rest.py — transporte resiliente (18 casos)

- `test_rate_limit_delay_*`: backoff com jitter dentro dos tetos.
- `test_completion_success_first_try`, `test_completion_rate_limit_then_success`,
  `test_completion_rate_limit_exhausted`, `test_completion_generic_error_wraps`,
  `test_completion_stream_yields_chunks`: sucesso, retry após 429, esgotamento
  → `OllamaConnectionError`, streaming por chunks (foi esse retry que segurou
  os picos de cota durante as runs).
- `test_check_health_*`, `test_chat_*`, `test_get_embeddings_*`,
  `test_api_urls_strip_v1_suffix`, `test_build_chat_payload_*`: saúde, fallback
  Ollama local, embeddings e montagem de payload.

## test_config.py, test_models.py, test_storage.py, test_cache.py, test_logging.py (18 casos)

- Config: padrões, override, singleton lazy + reset, paths absolutos, atributo
  desconhecido levanta `AttributeError`.
- Modelos: validação Pydantic (`GoldenQuestion`, defaults de
  `QueryExecutionRecord`).
- Storage: SQLite salva/retoma/carrega; JSONL idem (base do `--resume`).
- Cache: hit/miss por similaridade de cosseno; histórico de janela deslizante.
- Logging: arquivo central, idempotência, um log por run.

## test_question_parser.py + test_reporters_guards.py (16 casos)

- Parser do gerador adversarial: remove cercas de código, JSON com prefixo,
  tipos desconhecidos → `UNMAPPED`, lixo → vazio, concorrência respeitada.
- Repórteres defensivos: CSV/MD mesmo com records vazios, enums como objeto,
  colunas ausentes (`status`, `ttft`) sem exceção, NaN só nas métricas.
