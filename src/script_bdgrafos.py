import networkx as nx
import matplotlib.pyplot as plt
from pathlib import Path
import os

# 1. Configuração do Caminho do Arquivo de Grafo
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == "src" else Path(__file__).resolve().parent
GRAPH_FILE = BASE_DIR / "lightrag_ollama_db" / "graph_chunk_entity_relation.graphml"

def inspecionar_grafo():
    if not GRAPH_FILE.exists():
        print(f"Erro: Arquivo de grafo não encontrado em {GRAPH_FILE}")
        print("Certifique-se de que a indexação (1_indexacao.py) foi concluída com sucesso.")
        return

    print("Carregando Grafo de Conhecimento...\n")
    
    # 2. Carregar o Grafo (Formato GraphML)
    G = nx.read_graphml(str(GRAPH_FILE))

    print(f"📊 ESTATÍSTICAS DO GRAFO:")
    print(f"- Total de Entidades (Nós): {G.number_of_nodes()}")
    print(f"- Total de Relações (Arestas): {G.number_of_edges()}\n")

    # 3. Listar Entidades Extraídas (Nós)
    print("🏢 ENTIDADES BANCÁRIAS IDENTIFICADAS (Amostra de 15):")
    for idx, (node, data) in enumerate(list(G.nodes(data=True))):
        if idx >= 15: break
        # O LightRAG salva o tipo da entidade (se houver) ou a descrição
        tipo = data.get('entity_type', 'DESCONHECIDO')
        print(f" - [{tipo}] {node}")

    print("\n🔗 REGRAS E DEPENDÊNCIAS EXTRAÍDAS (Amostra de 10):")
    for idx, (source, target, data) in enumerate(list(G.edges(data=True))):
        if idx >= 10: break
        # O LightRAG costuma colocar a relação no campo 'description' ou 'weight'
        relacao = data.get('description', 'relaciona-se com')
        print(f" - {source} --> {target} \n   (Motivo: {relacao[:100]}...)\n")

    # 4. Plotagem Visual Básica (Opcional, abre uma janela)
    print("Gerando visualização gráfica... (Feche a janela para encerrar o script)")
    
    plt.figure(figsize=(12, 8))
    
    # Layout focado em espalhar os nós para melhor leitura
    pos = nx.spring_layout(G, k=0.5, iterations=50)
    
    # Desenhar os nós e os rótulos
    nx.draw_networkx_nodes(G, pos, node_size=300, node_color='lightblue', alpha=0.8)
    nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')
    
    # Desenhar as arestas
    nx.draw_networkx_edges(G, pos, alpha=0.5, edge_color='gray')
    
    plt.title("Visualização do Grafo de Conhecimento Bancário (LightRAG)", size=15)
    plt.axis('off')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    inspecionar_grafo()