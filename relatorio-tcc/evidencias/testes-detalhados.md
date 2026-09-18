# Anexo — o que cada teste verifica, em detalhe (158 testes)

> Como ler: cada item segue o formato **Cenário → Ação → Esperado →
> Diferença** (no que ele difere dos vizinhos). Para rodar tudo:
> `uv run pytest tests/ --no-cov -q` (esperado: **158 passed**).
> `arquivo:função` localiza cada caso no código.

## test_tree.py — árvore de decisão (32 casos)

A tabela `test_ramos` alimenta a árvore com uma pergunta e exige o ramo
exato. Cada linha existe para travar **uma armadilha real de implementação**
(encontradas ao codificar os POPs); a coluna “Armadilha” diz qual:

| Pergunta de entrada | Ramo exigido | Regra do POP | Armadilha que o caso trava |
|---|---|---|---|
| senha 6 dígitos bloqueio 'U' pelo site sem Alfa | `ACESSO_U_SITE_AGENCIA` | U só altera; site veda U/8 sem Alfa; biometria >7d (§3.1.2, §3.1.4) | Combinar 3 condições (código+canal+Alfa) num ramo só |
| senha bloqueio 'U' (geral) | `ACESSO_U_GERAL` | U nunca desbloqueia (§3.1.4, §3.2.4) | Cair no ramo de desbloqueio comum |
| senha 8 dígitos bloqueio '8' | `ACESSO_8_ALTERACAO` | Sem senha atual → Alteração (§3.2.2, §3.2.4) | Confundir '8' com 'U' (regras diferentes) |
| sequestro, bloquear senha-8 | `ACESSO_SEQUESTRO_X98` | Emergência → X98/800050; Conta de Acesso intacta (§4.2.2) | Bloquear a credencial errada (são 2 distintas) |
| marido bloqueou, titular solidário | `ACESSO_SOLIDARIO` | Senhas compartilhadas; trava todos (Nota c) | Tratar como conta individual |
| deficiente visual e código | `ACESSO_DEFICIENTE_CODIGO` | Dispensa com registro; conjunta só o titular (§5.a) | Estender a dispensa à conta toda |
| exterior com bloqueio U | `ACESSO_EXTERIOR_U` | E-mail MCI não vale p/ U; só Tóquio; procurador (§7) | Aceitar declaração por e-mail para fraude |
| cartão adicional sem senha | `ACESSO_ADICIONAL` | Adicional não correntista → agência (§8) | Mandar para App/SMS |
| senha por SMS não cadastrada | `ACESSO_SMS_ALTERACAO` | SMS só p/ alteração (§6) | Enviar 1ª senha por SMS |
| chip trocado não funciona | `ACESSO_CHIP_TAA` | Atualizar chip na TAA (§3.1.2) | Diagnosticar como senha errada |
| código 'Q' no celular | `ACESSO_CODIGO_Q` | Pendente de TAA + biometria >7d (§2.2) | Tratar 'Q' como bloqueio comum |
| App Alfa com senha do cartão | `ACESSO_CONTA_VS_SENHA8` | Credenciais distintas; identificar via X69 (§4.2.1–4.2.2) | Resetar a senha do app errado |
| bloqueio U, SAC resolve? | `ACESSO_SAC_ALCADA_U` | Rotinas 50130/50131/50112 (§3.1.2, §3.2.2) | Exigia código entre aspas; pergunta curta “U” caía no genérico |
| cancelar CDC 2881 convênio 700001 | `CDC_CANCEL_2881_DOC` | Restrito ao DOC 800020 + margem (§4) | Atendente cancelar direto |
| cancelar 2881 convênio 700017 | `CDC_CANCEL_2881_C17` | Restrito à Superintendência III 800030 (§4) | Tratar todo 2881 como DOC |
| boleto + débito duplicados | `CDC_DUPLICIDADE_BOLETO` | Estorna boleto 1º; supervisor em CDC 13.23 (§2) | Ordem inversa deixa operação em atraso |
| consignado INSS descontado 2× | `CDC_CONSIG_DEVOLUCAO` | D+2, exceto INSS 5º dia e MPDG 1º (§2) | Prazo único para todos |
| amortização linear no consignado | `CDC_LINEAR_VEDADO` | Linear vedado; preferir decrescente (§5.1) | Ramo era engolido pelo de consignação (ordem) |
| operação em perdas | `CDC_PERDAS` | Não informar prejuízo; CDC 13-34 + supervisor (§5.2) | Revelar o prejuízo ao cliente |
| ANC vencida sem limite | `CDC_ANC_SEM_LIMITE` | Agência com docs <90 dias; 50105 (§3) | “Cancelar” casava “anc” por substring e caía aqui — regex com fronteira |
| empréstimo de correspondente, fraude | `CDC_FRAUDE_CORRESPONDENTE` | Ocorrência 50113/14/15, unidade 800010 (§7.2) | Mesmo bug do substring acima |
| cancelar Limite Especial usando | `CDC_LIMITE_CANCELAMENTO` | Cobrir saldo antes; Ouvidoria direto (§8.1) | Cancelar com limite em uso |
| CDC 13º no aniversário | `CDC_13_ANIVERSARIO` | Cobrança+vencimento no mês de aniversário (§2) | Regra geral do 13º |
| antecipação IRPF e FGTS | `CDC_IRPF_FGTS` | IRPF: restituição ou vencimento; FGTS: repasse (§2) | Tratar os dois iguais |
| repactuação com Op pendente | `CDC_REPACTUACAO` | Pendente exclui; confirmada só liquida (§4.4) | Mesmo bug do substring “anc” |
| débito sem autorização pós-01/03/21 | `CDC_AUTORIZACAO_2021` | Exige autorização (CMN 4.790); 50104 | Dispatch não reconhecia “débito/autorização” — keywords adicionadas |

Demais casos do arquivo (diferenças entre si):

- `test_site_biometria_ok_vs_pendente` — **mesma pergunta, dois biometrias**:
  com 10 dias a árvore **responde** (liberado); sem dias ela **pergunta**
  (não chuta). É o teste da fronteira responder-vs-perguntar.
- `test_fallback_para_fora_dos_pops` — pergunta fora do domínio (“previsão do
  tempo”): esperado é o fallback honesto ou um pedido de dado, **nunca** uma
  regra inventada. Difere dos 26 acima porque testa o que a árvore faz quando
  *nada* casa.
- `test_detect_doc_por_slots` — prova que **slots vencem keywords**: com
  `codigo_bloqueio=U` preenchido, qualquer texto vai para o POP de acesso;
  sem slots, “cdc/boleto” vai para CDC e “oi” não vai para lugar nenhum.
  Difere do `test_ramos` porque testa só o *roteamento*, sem percorrer ramos.
- `test_engine_protocolo` — ciclo de vida completo do motor com fakes:
  nome de telemetria versionado, `aquery` retorna string com o conteúdo,
  embeddings têm forma `(2, 3)`, `ainsert`/`finalize` não quebram. Difere dos
  demais porque não testa regra nenhuma — testa o **contrato** que o
  `run-tree` espera do motor.
- `test_run_tree_gera_artefatos_com_tree_engine` — fim a fim com cenário
  mínimo: checkpoint + `tree_manifest.json` + `golden.json` criados, record
  com `mode=tree`/`source=tree_engine` e ramo `ACESSO…`. É o teste que garante
  que o `eval` vai conseguir julgar a run da árvore depois.
- `test_run_tree_help` — o comando existe e se descreve no CLI.

## test_clarifier.py — extração de slots e loop (10 casos)

- `test_extract_bloqueio_u` — **caso canônico**: `bloqueio 'U'` (com aspas) →
  `codigo_bloqueio=U`. Base para todos os outros.
- `test_extract_nao_captura_letra_de_bloqueio_pelo` — **regressão de bug
  real**: “bloqueio **p**elo site” capturava `P` como código (regex casava a
  letra seguinte). Agora: nenhum código + `canal=site`. Difere do anterior
  porque testa o que **não** deve casar.
- `test_extract_sem_alfa_e_biometria` — **múltiplos slots de uma vez**: “sem
  Alfa, biometria há 5 dias, pelo site” → `alfa=não` + `biometria=5` +
  `canal=site`. Prova extração composta, não só unitária.
- `test_extract_tipo_cliente` — “sou correntista” vs “não sou correntista”:
  a negação inverte o valor (não é só presença de keyword).
- `test_missing_e_next_question` — com `codigo` preenchido, o faltante passa
  a ser `alfa_code` e há pergunta formulada; sem faltantes, pergunta é `None`
  (critério de parada do loop).
- `test_should_ask_more` — tabela-verdade da parada: com pendência e turnos
  → continua; sem pendência **ou** turnos esgotados → para.
- `test_merge_e_enriched_query` — mescla sem mutar originais + query
  enriquecida carrega `slot=valor` (é o que o grafo recebe); sem slots,
  retorna o original intacto.
- `test_collect_slots_interactive_simulado` — diálogo simulado com respostas
  curtas (“U”, “não”, “5 dias”): 3 turnos, `codigo=U`, `biometria=5`. Prova
  que **resposta de 1 letra** é interpretada via `expected_slot` — difere dos
  testes de extração isolada porque exercita o loop com contexto.
- `test_collect_respeita_max_turns` — respostas vagas (“resposta vaga sem
  slots”) consomem turnos sem preencher nada e param em 2: o loop não trava
  nem estoura o teto.
- `test_clarify_settings_default` — config hermética (sem `.env`): padrão
  `max_turns=3`.

## test_router.py — roteador só-grafo (13 casos)

- `test_normalize_tira_acento_e_caixa` — base de tudo: “Agência” ≡ “agencia”
  (sem isso nenhum overlap funcionaria).
- `test_score_docs_pondera_tokens_exclusivos` — token exclusivo do doc vale
  1.0, compartilhado 0.25: genéricos (“conta”, “agência”) não decidem a rota.
  Difere do teste seguinte por não usar slots.
- `test_score_docs_expansao_de_slots` — valor cru `U` jamais casaria com
  entidade, então o slot injeta termos (“senha de 6 dígitos…”): com expansão,
  score de acesso > 0. É a ponte slot→vocabulário do índice.
- `test_route_margin` — margem = melhor menos segundo (0.0 com <2 docs).
- `test_route_by_graph_confiante_e_estrategia` — overlap claro → doc + modo
  certo (acesso→`local/k10`) + `confident=True`. O caminho feliz completo.
- `test_route_by_graph_sem_overlap_cai_em_fallback` — texto sem overlap
  (“xyz”) → `doc=None` + estratégia padrão: **roteador que não sabe, não
  atrapalha** (sem regressão vs comportamento antigo).
- `test_route_by_graph_sem_indice` — sem arquivos de índice → mesmo fallback
  (robustez a ambiente incompleto). Difere do anterior: lá o índice existe
  mas nada casa; aqui nem índice há.
- `test_next_discriminative_slot_prioriza_acesso` — entre `canal` e `codigo`,
  pergunta `codigo` primeiro (ordem que separa os docs, não ordem alfabética).
- `test_load_entity_index_mapeia_docs` / `test_load_entity_index_sem_arquivos` —
  lê os 2 JSONs reais do índice e mapeia hash→POP (via `DOCUMENTO_ORIGEM`);
  sem arquivos → `{}` (diferença: I/O válido vs ausente).
- `test_guided_para_cedo_quando_margem_estabiliza` — **a inteligência**:
  para antes do teto quando a margem estabiliza (menos turnos que o fixo).
  Difere do `test_collect_*` do clarifier porque a parada é por confiança do
  grafo, não por contagem.
- `test_guided_sem_indice_preenche_como_classica` — sem índice, preenche os 2
  slots como o loop antigo (compatibilidade garantida).
- `test_routing_settings_default` — `enabled`, `margin_min=0.05`, `k10/k5`.

## test_run_clarify.py — batch com clarificação (5 casos)

- `test_simulate_preenche_slots_e_respeita_max` — com teto 1, 1 turno e query
  enriquecida contém o slot; com teto 5, ≥2 turnos (teto é respeitado, não
  decorativo).
- `test_simulate_sem_valor_para` — sem valores simulados: 0 turnos, query
  intacta, dict vazio (o “usuário simulado” não inventa respostas).
- `test_simulate_pula_slots_sem_valor` — **regressão real**: cenário CDC sem
  `codigo_bloqueio` travava em 0 turnos; agora pula e preenche os 2 úteis.
  Difere do anterior: lá *nada* há para preencher; aqui há, mas fora de ordem.
- `test_run_clarify_gera_mesmos_artefatos_do_run` — com fake engine:
  checkpoint+CSV+MD+manifest+`golden.json`; manifest registra turnos e a
  query contém o slot. É o contrato que permite ao `eval` julgar depois.
- `test_run_clarify_help` — comando registrado no CLI.

## test_direct.py — baseline LLM puro (6 casos)

- `test_usa_modelo_do_chat` — usa o **mesmo** modelo do chat: o experimento
  isola só o retrieval (diferença vs árvore, que não usa modelo algum).
- `test_aquery_sem_contexto_recuperado` — o prompt enviado ao LLM contém a
  pergunta e instrução geral, **sem chunks/contexto**; “chunk” não aparece.
  É o teste que certifica “LLM puro de verdade”.
- `test_lifecycle_noop_e_ainsert_avisa` — sem storages: initialize/finalize
  vazios, `ainsert` avisa e ignora (diferença vs LightRAG, que indexa).
- `test_system_prompt_ptbr` — prompt exige pt-BR.
- `test_run_direct_gera_artefatos_com_baseline_engine` — records com
  `mode=direct` + `source=baseline_engine` e `golden.json` com a pergunta
  usada (completa, não a incompleta — o que o juiz vai comparar).
- `test_run_direct_rejeita_input_invalido` — `--input` fora de
  completa/incompleta sai com erro 1 (validação de CLI, não de IA).

## test_cli.py — comandos fim a fim com fakes (14 casos)

- `test_health_ok` vs `test_health_failure` — **par espelhado**: transporte no
  ar → saída 0 com “operacionais”; caído → saída 1 com “Falha no index”.
- `test_index_seeds_and_inserts` — sem POPs, semeia os 2 padrão e insere com
  marcador `DOCUMENTO_ORIGEM` (prova a origem rastreável).
- `test_generate_dataset` — gera 1 pergunta e registra (arquivo, qtd).
- `test_run_benchmark_end_to_end` — `run` com 2 perguntas gera checkpoint+CSV
  +MD e as cópias em `resultados/` (o contrato completo de artefatos).
- `test_run_no_queries` — pasta vazia → mensagem amigável, sem traceback
  (diferença vs acima: caminho vazio, não caminho feliz).
- `test_eval_run_id` vs `test_eval_no_checkpoint` — par espelhado do eval:
  com checkpoint gera CSV+MD (+cópia); sem checkpoint → erro 1 com “Nenhum
  checkpoint”.
- `test_build_run_id`, `test_resolve_eval_db_path`,
  `test_resolve_eval_db_path_missing_dir` — nomes de run (`None` → timestamp
  +modo) e resolução do checkpoint (explícito > por run-id > mais recente;
  dir inexistente levanta `FileNotFoundError`).
- `test_apply_chat_model_override_copies` — override retorna **cópia**; o
  global segue intacto (sem esse teste, um experimento contaminaria outro).
- `test_discover_and_seed_pops`, `test_run_and_eval_helpers_importable` —
  utilitários presentes e importáveis (fumaça contra refator que esquece
  export).

## test_runner_checkpoint.py — lote com checkpoint (5 casos)

- `test_str_response_success_and_checkpoint_saved` vs
  `test_stream_response_is_consumed` — **resposta direta vs stream**: ambas
  viram records `success` salvos (o runner consome geradores assíncronos).
- `test_empty_response_marks_error_and_still_checkpoints` — resposta vazia é
  erro **mas** o checkpoint persiste (o lote sobrevive a respostas ruins).
- `test_engine_exception_marks_error_and_checkpoints` — exceção vira record
  de erro com a mensagem (foi assim que os 429s ficaram registrados nos
  checkpoints `_35`, permitindo o resume depois).
- `test_resume_skips_completed_queries` — `--resume` pula índice concluído
  (base do reprocessamento após queda de cota).

## test_ragas_prepare.py + test_ragas_report.py — avaliação (12 casos)

- `test_normalize_and_is_gemini` + `test_select_relevancy_metric_by_transport` —
  detecção de modelo Gemini e `strictness=1` só para ele (o endpoint rejeita
  múltiplos candidatos com 400; demais modelos usam o padrão).
- `test_load_golden_map_missing_and_invalid` vs
  `test_load_golden_map_normalizes_keys` — golden ausente/corrompido → `{}` sem
  quebrar (diferença: tolerância) vs chaves normalizadas casando com queries
  enriquecidas (diferença: casamento).
- `test_prepare_dataset_joins_golden_and_context` — junta resposta + ground
  truth + **texto do documento-fonte** (é daqui que vem a ressalva: contexto
  do RAGAS = arquivo, não chunks recuperados).
- `test_prepare_dataset_empty_raises` — zero records válidos →
  `EvaluationError` explícito (foi o que barrou o eval do `_35` com 21 erros
  em vez de gerar relatório vazio silencioso).
- `test_run_evaluation_uses_injected_fn` / `test_run_evaluation_wraps_error` —
  RAGAS injetável (testes sem rede/gasto) e erro embrulhado em
  `EvaluationError` (fronteira de erro limpa).
- `test_ragas_report_means_and_groups`,
  `test_ragas_report_without_question_type`,
  `test_ragas_report_all_nan_metric_skips_worst`, `test_ragas_report_empty_df` —
  médias + recorte por tipo; sem coluna de tipo não quebra; métrica toda-NaN
  pula o “pior caso” em vez de eleger lixo; DataFrame vazio gera relatório
  “sem dados” (cada um cobre uma forma distinta de o juiz falhar
  parcialmente).

## test_lightrag_engine.py — adaptador do grafo (9 casos)

- `test_build_entity_prompt_appends_once` — ontologia bancária injetada **1×**
  mesmo chamando 2× (idempotência; sem isso o prompt duplicaria a cada engine).
- `test_build_llm_messages_order_and_constraint` — ordem system(pt-BR) →
  histórico → pergunta (ordem errada degradaria o modelo).
- `test_invalid_role_raises_without_network` — role inválido falha rápido, sem
  tocar rede (fail-fast).
- `test_role_aware_model_and_inject_prompts` + `test_injected_clients_are_kept` —
  index usa um modelo, chat outro; clientes injetados (fakes) são preservados
  (base da testabilidade).
- `test_custom_llm_func_delegates_role_model`,
  `test_initialize_uses_factory_and_role_timeouts` — transporte único, modelo
  por role; inicialização via factory com timeouts por role.
- `test_aquery_requires_initialize`, `test_aquery_maps_mode_and_top_k`,
  `test_ainsert_and_finalize` — sem initialize é erro; modo/top_k/stream
  chegam ao `QueryParam` (antes eram silenciosamente ignorados — regressão
  histórica); ciclo de insert/finalize.

## test_ollama_retry.py + test_ollama_rest.py — transporte resiliente (18 casos)

- `test_rate_limit_delay_within_bounds` vs
  `test_rate_limit_delay_respects_small_ceiling` — backoff com jitter dentro
  do teto normal vs teto pequeno (duas parametrizações do mesmo cálculo).
- `test_completion_success_first_try` — caminho feliz sem retry (baseline de
  comparação dos seguintes).
- `test_completion_rate_limit_then_success` — 429 seguido de sucesso: retry
  com backoff recupera (foi esse mecanismo que segurou os picos de cota nas
  runs — ver `logs/`, “Tentativa 2/6…”).
- `test_completion_rate_limit_exhausted` — 429 até o fim → erro tipado
  `OllamaConnectionError` (diferença vs anterior: quando **desistir**).
- `test_completion_generic_error_wraps` — erro não-429 também vira erro
  tipado (fronteira de erro única para o runner).
- `test_completion_stream_yields_chunks` — streaming entrega chunks (base do
  `chat` interativo).
- `test_check_health_ok` / `test_check_health_non_200_is_false` /
  `test_check_health_exception_is_false` — saúde nos 3 estados (ok / HTTP
  ruim / exceção).
- `test_chat_non_stream_returns_content_and_injects_num_ctx`,
  `test_chat_stream_concatenates_and_ignores_invalid_line`,
  `test_get_embeddings_returns_array`,
  `test_get_embeddings_empty_returns_zeros` — fallback Ollama local: conteúdo
  + `num_ctx`, stream tolerante a linha inválida, embeddings com forma certa,
  lista vazia → zeros (não exceção).
- `test_api_urls_strip_v1_suffix`, `test_build_chat_payload_injects_num_ctx_and_model_fallback`,
  `test_build_chat_payload_explicit_overrides` — URLs sem `/v1` duplicado,
  `num_ctx`/modelo padrão injetados, overrides explícitos vencem padrões.

## test_config.py, test_models.py, test_storage.py, test_cache.py, test_logging.py (18 casos)

- `test_default_config` — hermético (ignora `.env`, limpa variáveis): padrões
  de URL, modelos e limites (contrato de configuração).
- `test_custom_ollama_settings` — override via construtor funciona.
- `test_get_settings_cached_singleton` vs `test_get_settings_reset_rebuilds` —
  par espelhado: mesma instância sempre **vs** reset reconstrói (isolamento
  entre testes).
- `test_get_settings_resolves_absolute_paths` — paths relativos viram
  absolutos (sem isso, trocar de cwd quebra tudo).
- `test_settings_attr_delegates_to_getter` / `test_unknown_attr_raises` —
  `config.settings` delega ao getter; atributo inexistente levanta
  `AttributeError` (não `None` silencioso).
- `test_golden_question_validation`, `test_query_execution_record_defaults` —
  Pydantic valida schemas e preenche defaults (contratos de dados).
- `test_sqlite_storage_checkpoint_and_resume`, `test_jsonl_storage` — salvar,
  listar concluídos e carregar, nos 2 backends (base física do `--resume`).
- `test_semantic_cache_hit_and_miss` — similaridade acima do limiar
  reaproveita; abaixo, passa adiante (o atalho que explica latências de ~2s
  em runs com cache).
- `test_sliding_window_history` — janela mantém só os últimos N turnos
  (limite de contexto da conversa).
- `test_setup_logging_cria_arquivo`, `test_setup_logging_idempotente`,
  `test_setup_logging_per_run`, `test_cli_cria_log_global`,
  `test_logs_dir_resolvido_para_base_dir` — log central criado 1× (chamadas
  repetidas não duplicam handlers), um arquivo por run, dir resolvido contra
  `base_dir`.

## test_question_parser.py + test_reporters_guards.py (16 casos)

- `test_strip_fences_plain_unchanged` vs `test_strip_fences_json_and_uppercase` —
  texto puro passa intacto **vs** cercas de código/JSON/maiúsculas são
  removidas (o LLM gera Markdown; o parser precisa tolerar).
- `test_parse_valid_questions_typed` — JSON válido vira objetos tipados.
- `test_parse_fenced_and_prefixed_json_via_fallback` — JSON com prefixo usa
  rota de fallback (diferença: formato fora do padrão, não erro).
- `test_parse_unknown_type_becomes_unmapped_and_non_dict_skipped` — tipo
  desconhecido → `UNMAPPED`, item não-dict é pulado (tolerância sem perder o
  lote).
- `test_parse_garbage_returns_empty` — lixo total → lista vazia (não exceção).
- `test_build_user_prompt_contains_doc_and_count` — prompt carrega doc +
  quantidade pedida.
- `test_generate_for_doc_delegates_to_parse` vs
  `test_generate_for_doc_llm_error_returns_empty` — sucesso delega ao parser
  **vs** erro do LLM retorna vazio (fronteiras opostas do gerador).
- `test_generate_dataset_writes_json_and_filters_empty`,
  `test_generate_dataset_empty_dir`, `test_generate_dataset_respects_concurrency` —
  escreve JSON filtrando vazios; dir vazio não quebra; concorrência limitada.
- `test_ragas_report_means_and_groups` (+3 variações, ver seção RAGAS acima).
- `test_empty_records_writes_fallback_and_creates_parents`,
  `test_enum_status_and_source_counted`, `test_missing_status_column_defaults_to_total`,
  `test_missing_ttft_column_does_not_raise` — relatório executivo defensivo:
  vazio gera fallback (criando pastas), enums contam como fonte/status,
  colunas ausentes usam defaults em vez de exceção.
