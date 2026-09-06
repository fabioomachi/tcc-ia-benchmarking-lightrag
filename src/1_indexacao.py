import shutil
import asyncio
import numpy as np
from pathlib import Path
from openai import AsyncOpenAI
from lightrag import LightRAG
from lightrag.utils import EmbeddingFunc
from lightrag.prompt import PROMPTS

BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
WORKING_DIR = BASE_DIR / "lightrag_ollama_db"

print("[1/4] Higienizando ambiente de experimentação...")
if WORKING_DIR.exists():
    shutil.rmtree(WORKING_DIR)
WORKING_DIR.mkdir(parents=True, exist_ok=True)
INPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# TUNING: Injetando a Ontologia Bancária na Chave Correta
# ---------------------------------------------------------
PROMPTS["entity_extraction_system_prompt"] += (
    "\n\nCRITICAL DOMAIN INSTRUCTION (BANKING COMPLIANCE):\n"
    "You are a banking compliance auditor. Focus exhaustively on extracting entities and relationships "
    "that represent business rules, regulatory constraints, and operational systems.\n"
    "Use strict entity types such as: REGRA_BACEN, PROCEDIMENTO, SISTEMA, CONDICAO, EXCECAO, ATOR, DOCUMENTO, PRAZO.\n"
    "Ignore generic words. Focus heavily on dependencies (e.g., 'requires', 'blocks', 'authorizes')."
)

client = AsyncOpenAI(base_url="http://localhost:11434/v1/", api_key="ollama_local")

async def custom_llm_func(prompt, system_prompt=None, history_messages=[], **kwargs):
    messages = []
    if system_prompt: messages.append({"role": "system", "content": system_prompt})
    if history_messages: messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})
    
    valid_kwargs = {k: v for k, v in kwargs.items() if k in ["temperature", "max_tokens", "top_p"]}
    valid_kwargs["temperature"] = 0.0 
    
    response = await client.chat.completions.create(model="qwen2.5:3b", messages=messages, **valid_kwargs)
    return response.choices[0].message.content

async def custom_embedding_func(texts: list[str]) -> np.ndarray:
    response = await client.embeddings.create(model="all-minilm", input=texts)
    return np.array([res.embedding for res in response.data])

async def main():
    print("[2/4] Inicializando Motor LightRAG (Perfil: Alta Fidelidade de Extração)...")
    rag = LightRAG(
        working_dir=str(WORKING_DIR),
        llm_model_func=custom_llm_func,
        embedding_func=EmbeddingFunc(embedding_dim=384, max_token_size=8192, func=custom_embedding_func),
        chunk_token_size=512,
        chunk_overlap_token_size=128
    )
    await rag.initialize_storages()

    print("[3/4] Preparando Corpus Documental (Varredura de Arquivos)...")
    arquivos_txt = list(INPUT_DIR.glob("*.txt"))
    
    # Se a pasta estiver vazia, gera POPs sintéticos para garantir o funcionamento do experimento
    if not arquivos_txt:
        print(" -> Pasta input vazia. Gerando POPs sintéticos de teste...")
        
        pop_pix = INPUT_DIR / "pop_cancelamento_pix.txt"
        pop_pix.write_text(
            "PROCEDIMENTO OPERACIONAL PADRÃO - POP-014: Cancelamento de PIX por Suspeita de Fraude.\n"
            "1. O operador deve validar a identidade do cliente via biometria facial no sistema BioCheck.\n"
            "2. Caso haja contestação por golpe do falso leilão, o bloqueio cautelar deve ser acionado no sistema MED (Mecanismo Especial de Devolução) do BACEN em até 30 minutos corridos após a denúncia.\n"
            "3. EXCEÇÃO: É estritamente proibido o estorno manual sem a autorização prévia, registrada em ticket, da mesa de compliance antifraude.\n"
            "4. Falhas na aplicação do bloqueio cautelar no prazo regulatório geram passivo ao banco de acordo com a resolução BCB nº 103.",
            encoding="utf-8"
        )
        
        pop_cartao = INPUT_DIR / "pop_bloqueio_cartao.txt"
        pop_cartao.write_text(
            "PROCEDIMENTO OPERACIONAL PADRÃO - POP-015: Bloqueio de Cartão de Crédito por Suspeita de Fraude.\n"
            "1. O operador deve verificar o padrão de compras no sistema de monitoramento transacional.\n"
            "2. Em caso de transações internacionais atípicas consecutivas, acionar o bloqueio preventivo do cartão.\n"
            "3. CONDICAO: O bloqueio preventivo exige a comunicação imediata ao cliente via SMS e e-mail cadastrado, conforme determina a norma do BACEN sobre transparência.\n"
            "4. O desbloqueio só pode ser realizado após contato ativo do cliente validado pelo sistema BioCheck.",
            encoding="utf-8"
        )
        
        # Atualiza a lista após a criação
        arquivos_txt = list(INPUT_DIR.glob("*.txt"))

    print(f"\n[4/4] Executando Extração de Grafos (Encontrados {len(arquivos_txt)} documentos)...")
    for arquivo in arquivos_txt:
        print(f" -> Indexando: {arquivo.name} ...")
        conteudo = arquivo.read_text(encoding="utf-8")
        await rag.ainsert(conteudo)
        
    print("\n✅ Treinamento/Indexação em Lote concluído com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())