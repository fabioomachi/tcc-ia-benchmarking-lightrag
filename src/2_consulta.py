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

LOG_FILE = LOGS_DIR / "benchmark_execution.log"

logger = logging.getLogger("RAG_BENCHMARK")
logger.setLevel(logging.INFO)

# Handler de Arquivo: Escreve JSONL puro para parsing automatizado (Pandas, RAGAS, etc.)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(file_handler)

# Handler de Terminal: Formato legível para acompanhamento em tempo real
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)


def log_structured_event(event_type: str, payload: dict):
    """Helper central para padronizar todos os eventos em JSON no log."""
    log_entry = {
        "timestamp": time.time(),
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "data": payload
    }
    logger.info(json.dumps(log_entry, ensure_ascii=False))


def async_time_tracker(func):
    """Decorator para medir latência da orquestração do RAG."""
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
# Integração Desacoplada (Isola o AsyncOpenAI client contra erros de deepcopy)
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
    
    if history_messages:
        messages.extend(history_messages)
    if GLOBAL_HISTORY:
        messages.extend(GLOBAL_HISTORY.messages)
        
    messages.append({"role": "user", "content": prompt})
    
    # AUDITORIA DE PROMPT: Grava o contexto/prompt completo que o LightRAG montou para o LLM
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
    """Consome o streaming, imprime na tela e mede a latência do primeiro token (TTFT)."""
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


async def process_batch_file(rag: LightRAG, batch_path: str, params: QueryParam):
    """Processa lote de perguntas e gera log estruturado para benchmarking."""
    path = Path(batch_path)
    if not path.exists():
        log_structured_event("execution_error", {"message": f"Arquivo batch não encontrado: {batch_path}"})
        return

    output_path = path.parent / f"results_{path.stem}_{params.mode}.jsonl"
    log_structured_event("batch_start", {"input_file": str(path), "output_file": str(output_path)})

    with open(path, 'r', encoding='utf-8') as f_in, open(output_path, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            query = line.strip()
            if line.startswith('{'):
                try:
                    data = json.loads(line)
                    query = data.get('query', '')
                except json.JSONDecodeError:
                    pass
            
            if not query: continue
            
            start_time = time.perf_counter()
            try:
                response = await execute_rag_query(rag, query, param=params)
                latency = time.perf_counter() - start_time
                
                result_record = {
                    "query": query,
                    "response": response,
                    "mode": params.mode,
                    "latency_seconds": round(latency, 4)
                }
                f_out.write(json.dumps(result_record, ensure_ascii=False) + "\n")
                
                log_structured_event("batch_interaction_record", result_record)
            except Exception as e:
                log_structured_event("execution_error", {"query": query, "error": str(e)})


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
        "history_turns": args.history_turns
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
    
    params = QueryParam(mode=args.mode, top_k=args.top_k, stream=not args.batch)

    if args.batch:
        await process_batch_file(rag, args.batch, params)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Módulo de Consulta Avançada LightRAG")
    parser.add_argument("--mode", type=str, default="hybrid", choices=["naive", "local", "global", "hybrid"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--llm-model", type=str, default="qwen2.5:3b")
    parser.add_argument("--embed-model", type=str, default="all-minilm")
    parser.add_argument("--embed-dim", type=int, default=384)
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434/v1/")
    parser.add_argument("--batch", type=str, default=None)
    parser.add_argument("--history-turns", type=int, default=3, help="Número de turnos mantidos na memória (Sliding Window)")
    parser.add_argument("--cache-threshold", type=float, default=0.92, help="Limiar de similaridade para cache semântico (0 a 1)")

    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nSessão encerrada com segurança.")