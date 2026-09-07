import asyncio
import argparse
import json
import logging
import time
import sys
import functools
import numpy as np
from pathlib import Path
from openai import AsyncOpenAI
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

# -----------------------------------------------------------------------------
# Setup de Diretórios e Logging Estruturado (JSONL)
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
WORKING_DIR = BASE_DIR / "lightrag_ollama_db"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Caminho padrão ajustado para a estrutura solicitada
DEFAULT_BATCH_DIR = BASE_DIR / "entradas" / "perguntas"

LOG_FILE = LOGS_DIR / "benchmark_execution.log"

logger = logging.getLogger("RAG_BENCHMARK")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)


def log_structured_event(event_type: str, payload: dict):
    log_entry = {
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "data": payload
    }
    logger.info(json.dumps(log_entry, ensure_ascii=False))


def async_time_tracker(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        params = kwargs.get('param')
        search_mode = params.mode if params else "unknown"
        
        try:
            result = await func(*args, **kwargs)
            status = "success"
        except Exception as e:
            result = None
            status = f"error: {type(e).__name__}"
            raise
        finally:
            latency = time.perf_counter() - start_time
            log_structured_event("rag_orchestration", {
                "function": func.__name__,
                "search_mode": search_mode,
                "latency_seconds": round(latency, 4),
                "status": status
            })
        return result
    return wrapper


# -----------------------------------------------------------------------------
# Controladores de Sessão: Cache Semântico e Histórico (Sliding Window)
# -----------------------------------------------------------------------------
class SemanticCache:
    def __init__(self, threshold=0.92):
        self.threshold = threshold
        self.cache = []

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

    def get(self, query_emb: np.ndarray):
        for item in self.cache:
            similarity = self._cosine_similarity(query_emb, item['embedding'])
            if similarity >= self.threshold:
                return item['response'], similarity
        return None, 0.0

    def add(self, query_emb: np.ndarray, response: str):
        self.cache.append({'embedding': query_emb, 'response': response})


class SlidingWindowHistory:
    def __init__(self, max_turns=3):
        self.max_turns = max_turns
        self.messages = []

    def add_turn(self, user_msg: str, asst_msg: str):
        self.messages.append({"role": "user", "content": user_msg})
        self.messages.append({"role": "assistant", "content": asst_msg})
        if len(self.messages) > self.max_turns * 2:
            self.messages = self.messages[-self.max_turns * 2:]


# -----------------------------------------------------------------------------
# Integração Desacoplada
# -----------------------------------------------------------------------------
GLOBAL_CLIENT = None
GLOBAL_HISTORY = None
GLOBAL_ARGS = None


async def custom_llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    language_constraint = (
        "DIRETRIZ ABSOLUTA: Você deve responder SEMPRE e EXCLUSIVAMENTE em Português do Brasil (pt-BR). "
        "Independentemente do idioma dos documentos de contexto ou do prompt original."
    )
    final_sys_prompt = f"{system_prompt}\n\n{language_constraint}" if system_prompt else language_constraint

    messages = [{"role": "system", "content": final_sys_prompt}]
    
    # if history_messages:
    #     messages.extend(history_messages)
    # if GLOBAL_HISTORY:
    #     messages.extend(GLOBAL_HISTORY.messages)
    if history_messages:
        messages.extend(history_messages)


    messages.append({"role": "user", "content": prompt})
    
    log_structured_event("llm_input_prompt", {
        "system_prompt": final_sys_prompt,
        "raw_prompt_payload": prompt,
        "history_messages": GLOBAL_HISTORY.messages if GLOBAL_HISTORY else []
    })

    valid_kwargs = {k: v for k, v in kwargs.items() if k in ["temperature", "max_tokens", "top_p"]}
    stream = kwargs.get("stream", False)
    
    response = await GLOBAL_CLIENT.chat.completions.create(
        model=GLOBAL_ARGS.llm_model, 
        messages=messages, 
        stream=stream,
        **valid_kwargs
    )
    
    if stream:
        async def stream_generator():
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        return stream_generator()
    else:
        return response.choices[0].message.content


async def custom_embedding_func(texts: list[str]) -> np.ndarray:
    response = await GLOBAL_CLIENT.embeddings.create(model=GLOBAL_ARGS.embed_model, input=texts)
    return np.array([res.embedding for res in response.data])


async def async_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


@async_time_tracker
async def execute_rag_query(rag: LightRAG, query: str, param: QueryParam):
    return await rag.aquery(query, param=param)


async def consume_stream(response_gen) -> tuple[str, float]:
    start_time = time.perf_counter()
    first_token = True
    full_response = ""
    ttft = 0.0
    
    print("\n--- Resposta Gerada ---")
    async for chunk in response_gen:
        if first_token:
            ttft = time.perf_counter() - start_time
            first_token = False
            
        sys.stdout.write(chunk)
        sys.stdout.flush()
        full_response += chunk
        
    print("\n" + "-" * 40 + "\n")
    return full_response, ttft


async def process_batch_dir(rag: LightRAG, batch_path: Path, params: QueryParam, concurrency_limit: int = 10):
    if not batch_path.exists():
        log_structured_event("execution_error", {"message": f"Diretório de lote não encontrado: {batch_path}"})
        print(f"⚠️ Diretório de lote não encontrado em: {batch_path}")
        return

    query_files = list(batch_path.glob("*.txt")) + list(batch_path.glob("*.json"))
    if not query_files:
        print(f"⚠️ Nenhum arquivo .txt ou .json encontrado em {batch_path}")
        return

    output_path = BASE_DIR / "logs" / f"results_batch_{batch_path.parent.name}_{batch_path.name}_{params.mode}.jsonl"
    log_structured_event("batch_start", {"input_dir": str(batch_path), "output_file": str(output_path), "concurrency": concurrency_limit})

    queries = []
    for qfile in query_files:
        with open(qfile, 'r', encoding='utf-8') as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                if line_str.startswith('{'):
                    try:
                        data = json.loads(line_str)
                        q = data.get('question', '')
                        if q: queries.append(q)
                    except json.JSONDecodeError:
                        pass
                else:
                    queries.append(line_str)

    total_queries = len(queries)
    log_structured_event("batch_total_loaded", {"total_queries": total_queries})
    print(f"\n🚀 Iniciando processamento em lote de {total_queries} perguntas da pasta {batch_path} (Concorrência: {concurrency_limit})...\n")

    semaphore = asyncio.Semaphore(concurrency_limit)
    completed_counter = 0

    async def worker(query_idx: int, query_text: str):
        nonlocal completed_counter
        async with semaphore:
            start_time = time.perf_counter()
            try:
                local_param = QueryParam(mode=params.mode, top_k=params.top_k, stream=False)
                response = await execute_rag_query(rag, query_text, param=local_param)
                latency = time.perf_counter() - start_time
                
                result_record = {
                    "index": query_idx,
                    "query": query_text,
                    "response": response,
                    "mode": params.mode,
                    "latency_seconds": round(latency, 4),
                    "status": "success"
                }
                
                log_structured_event("batch_interaction_record", result_record)
                return result_record
            except Exception as e:
                latency = time.perf_counter() - start_time
                error_record = {
                    "index": query_idx,
                    "query": query_text,
                    "response": None,
                    "mode": params.mode,
                    "latency_seconds": round(latency, 4),
                    "status": f"error: {type(e).__name__}",
                    "error_message": str(e)
                }
                log_structured_event("execution_error", error_record)
                return error_record

    tasks = [worker(i, q) for i, q in enumerate(queries)]
    
    with open(output_path, 'w', encoding='utf-8') as f_out:
        for coro in asyncio.as_completed(tasks):
            res = await coro
            f_out.write(json.dumps(res, ensure_ascii=False) + "\n")
            completed_counter += 1
            if completed_counter % 25 == 0 or completed_counter == total_queries:
                print(f"📊 Progresso: {completed_counter}/{total_queries} perguntas processadas...")

    log_structured_event("batch_complete", {"total_processed": completed_counter, "output_file": str(output_path)})
    print(f"\n✅ Lote concluído. Resultados salvos em: {output_path}\n")


# -----------------------------------------------------------------------------
# Loop Principal
# -----------------------------------------------------------------------------
async def main(args):
    if not WORKING_DIR.exists():
        raise FileNotFoundError(f"Banco de grafos ausente em {WORKING_DIR}.")

    global GLOBAL_CLIENT, GLOBAL_HISTORY, GLOBAL_ARGS
    GLOBAL_ARGS = args
    GLOBAL_CLIENT = AsyncOpenAI(base_url=args.ollama_url, api_key="ollama_local", max_retries=3)
    GLOBAL_HISTORY = SlidingWindowHistory(max_turns=args.history_turns)
    
    semantic_cache = SemanticCache(threshold=args.cache_threshold)

    log_structured_event("session_start", {
        "llm_model": args.llm_model,
        "embed_model": args.embed_model,
        "mode": args.mode,
        "top_k": args.top_k,
        "cache_threshold": args.cache_threshold,
        "history_turns": args.history_turns,
        "batch_mode": args.batch
    })

    rag = LightRAG(
        working_dir=str(WORKING_DIR),
        llm_model_func=custom_llm_func,
        embedding_func=EmbeddingFunc(
            embedding_dim=args.embed_dim, 
            max_token_size=8192, 
            func=custom_embedding_func
        )
    )
    await rag.initialize_storages()    
   
    params = QueryParam(mode=args.mode, top_k=args.top_k)

    if args.batch:
        batch_target = Path(args.batch) if args.batch != "entradas/perguntas" else DEFAULT_BATCH_DIR
        await process_batch_dir(rag, batch_target, params, concurrency_limit=args.concurrency)
        return

    print(f"\n✅ Motor Operacional. Logs gravados em: {LOG_FILE}\n")
    
    while True:
        try:
            query = await async_input("Digite sua pergunta (ou 'sair' para encerrar): \n> ")
            if query.lower() in ['sair', 'exit', 'quit']:
                log_structured_event("session_end", {"reason": "user_exit"})
                break
            if not query.strip():
                continue

            query_start_time = time.perf_counter()

            # 1. Verificação no Cache Semântico
            query_embs = await custom_embedding_func([query])
            query_emb = query_embs[0]
            
            cached_response, similarity = semantic_cache.get(query_emb)
            if cached_response:
                total_latency = time.perf_counter() - query_start_time
                print("\n--- Resposta Gerada (via Semantic Cache) ---")
                print(cached_response)
                print("-" * 40 + "\n")
                
                log_structured_event("interaction_record", {
                    "user_query": query,
                    "final_response": cached_response,
                    "source": "semantic_cache",
                    "similarity_score": round(similarity, 4),
                    "execution_metrics": {
                        "total_latency_seconds": round(total_latency, 4)
                    }
                })
                GLOBAL_HISTORY.add_turn(query, cached_response)
                continue

            # 2. Execução via RAG
            rag_start_time = time.perf_counter()
            response = await execute_rag_query(rag, query, param=params)
            rag_latency = time.perf_counter() - rag_start_time
            
            ttft = 0.0
            if hasattr(response, '__aiter__'):
                final_text, ttft = await consume_stream(response)
            else:
                final_text = response
                print("\n--- Resposta Gerada ---")
                print(final_text)
                print("-" * 40 + "\n")

            total_latency = time.perf_counter() - query_start_time

            # 3. Log Completo para Avaliação de Qualidade
            log_structured_event("interaction_record", {
                "user_query": query,
                "final_response": final_text,
                "source": "lightrag_engine",
                "execution_metrics": {
                    "total_latency_seconds": round(total_latency, 4),
                    "rag_retrieval_latency_seconds": round(rag_latency, 4),
                    "ttft_seconds": round(ttft, 4)
                },
                "parameters": {
                    "search_mode": args.mode,
                    "top_k": args.top_k,
                    "model": args.llm_model
                }
            })

            semantic_cache.add(query_emb, final_text)
            GLOBAL_HISTORY.add_turn(query, final_text)
            
        except Exception as e:
            log_structured_event("execution_error", {
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
            print(f"⚠️ Falha no processamento: {e}")
    await rag.finalize_storages()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo de Consulta Avançada LightRAG")
    parser.add_argument("--mode", type=str, default="hybrid", choices=["naive", "local", "global", "hybrid"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--llm-model", type=str, default="qwen2.5:3b")
    parser.add_argument("--embed-model", type=str, default="all-minilm")
    parser.add_argument("--embed-dim", type=int, default=384)
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434/v1/")
    
    # Flag --batch agora é um argumento opcional (nargs="?") que assume "entradas/perguntas" por padrão se acionado sem valor
    parser.add_argument("--batch", nargs="?", const="entradas/perguntas", default=None, help="Executa o lote de arquivos da pasta entradas/perguntas de forma concorrente")
    
    parser.add_argument("--concurrency", type=int, default=10, help="Número máximo de requisições concorrentes para o lote")
    parser.add_argument("--history-turns", type=int, default=3, help="Número de turnos mantidos na memória (Sliding Window)")
    parser.add_argument("--cache-threshold", type=float, default=0.92, help="Limiar de similaridade para cache semântico (0 a 1)")

    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nSessão encerrada com segurança.")