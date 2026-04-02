# memoria_rag.py
"""
Sistema de memória semântica (RAG) para a Luna.
Substitui a busca por palavra-chave do memoria_permanente por busca vetorial.

Dependência: pip install chromadb
"""

import os
import uuid
import json
import requests
from datetime import datetime

# ── Caminhos ───────────────────────────────────────────────────────────────────

_ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CHROMA_DIR = os.path.join(_ROOT, "memories", "chroma.db")
_INIT_JSON  = os.path.join(_ROOT, "memories", "memoryinit.json")
_BL_PATH    = os.path.join(_ROOT, "blacklist.txt")

os.makedirs(os.path.join(_ROOT, "memories"), exist_ok=True)

# ── ChromaDB ───────────────────────────────────────────────────────────────────

import chromadb
from chromadb.config import Settings

_client     = chromadb.PersistentClient(
    path=_CHROMA_DIR,
    settings=Settings(anonymized_telemetry=False)
)
_collection = _client.get_or_create_collection(name="luna_memories")

# Importa memórias iniciais se banco estiver vazio
if _collection.count() == 0 and os.path.isfile(_INIT_JSON):
    try:
        with open(_INIT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        for mem in data.get("memories", []):
            _collection.upsert(
                ids=[mem["id"]],
                documents=[mem["document"]],
                metadatas=[mem.get("metadata", {"type": "long-term"})]
            )
        print(f"[RAG] Importadas {_collection.count()} memórias iniciais.")
    except Exception as e:
        print(f"[RAG] Erro ao importar memórias iniciais: {e}")
else:
    print(f"[RAG] {_collection.count()} memórias carregadas.")

# ── Blacklist ──────────────────────────────────────────────────────────────────

def _carregar_blacklist() -> list[str]:
    if not os.path.isfile(_BL_PATH):
        # Cria arquivo padrão vazio com instruções
        with open(_BL_PATH, "w", encoding="utf-8") as f:
            f.write("# Uma palavra/frase por linha. A Luna não vai falar nada que contenha estes termos.\n")
        return []
    with open(_BL_PATH, "r", encoding="utf-8") as f:
        return [
            linha.strip().lower()
            for linha in f
            if linha.strip() and not linha.startswith("#")
        ]

def is_safe(texto: str) -> bool:
    """Retorna False se o texto contiver alguma palavra da blacklist."""
    t = texto.lower()
    for palavra in _carregar_blacklist():
        if palavra in t:
            print(f"[Blacklist] Bloqueado: contém '{palavra}'")
            return False
    return True

def sanitizar(texto: str, fallback: str = "...") -> str:
    """Retorna o texto original se seguro, ou o fallback."""
    return texto if is_safe(texto) else fallback

# ── Adicionar / buscar memórias ────────────────────────────────────────────────

def adicionar_memoria(documento: str, tipo: str = "short-term") -> str:
    """
    Salva uma memória no banco vetorial.
    Retorna o ID gerado.
    """
    mem_id = str(uuid.uuid4())
    _collection.upsert(
        ids=[mem_id],
        documents=[documento],
        metadatas=[{"type": tipo, "data": datetime.now().strftime("%d/%m/%Y")}]
    )
    return mem_id

def buscar_memorias(query: str, n: int = 5) -> list[str]:
    """
    Busca as N memórias mais relevantes por similaridade semântica.
    Retorna lista de strings (documentos).
    """
    if _collection.count() == 0:
        return []
    try:
        resultado = _collection.query(
            query_texts=[query],
            n_results=min(n, _collection.count())
        )
        return resultado["documents"][0] if resultado["documents"] else []
    except Exception as e:
        print(f"[RAG] Erro na busca: {e}")
        return []

def memorias_para_prompt(query: str, n: int = 5) -> str:
    """
    Formata as memórias relevantes para injetar no system prompt.
    """
    mems = buscar_memorias(query, n)
    if not mems:
        return "Nenhuma memória relevante encontrada."
    linhas = [f"- {m}" for m in mems]
    return "\n".join(linhas)

# ── Auto-geração de memórias (reflection) ─────────────────────────────────────

# Prompt usado para pedir ao Groq que extraia memórias importantes
_REFLECTION_PROMPT = """Analise o trecho de conversa abaixo e extraia de 2 a 4 fatos importantes sobre o usuário ou sobre o que foi discutido.
Cada fato deve ser uma frase curta e objetiva, no formato de pergunta e resposta separados por " | ".
Exemplo: "O que o usuário gosta? | Gosta de jogos de RPG e tem um gato chamado Bola."

Responda APENAS com os fatos, um por linha, sem numeração, sem cabeçalho.

CONVERSA:
{conversa}
"""

_msgs_desde_reflection = 0
_REFLECTION_INTERVALO  = 20   # gera memórias a cada N mensagens


def tentar_reflection(historico: list[dict], groq_url: str, groq_key: str, modelo: str):
    """
    Chamado a cada mensagem nova. Quando acumular N mensagens,
    pede ao LLM para extrair memórias e salva no ChromaDB.
    """
    global _msgs_desde_reflection
    _msgs_desde_reflection += 1

    if _msgs_desde_reflection < _REFLECTION_INTERVALO:
        return

    _msgs_desde_reflection = 0
    msgs_recentes = historico[-_REFLECTION_INTERVALO:]

    # Monta texto da conversa
    linhas = []
    for m in msgs_recentes:
        papel = "Usuário" if m["role"] == "user" else "Luna"
        linhas.append(f"{papel}: {m['content']}")
    conversa = "\n".join(linhas)

    try:
        r = requests.post(
            groq_url,
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": modelo,
                "messages": [
                    {"role": "user", "content": _REFLECTION_PROMPT.format(conversa=conversa)}
                ],
                "max_tokens": 300,
                "temperature": 0.3,
            },
            timeout=20,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()

        novos = 0
        for linha in raw.splitlines():
            linha = linha.strip()
            if "|" in linha and len(linha) > 5:
                adicionar_memoria(linha, tipo="short-term")
                novos += 1

        if novos:
            print(f"[RAG] {novos} memória(s) gerada(s) por reflection. Total: {_collection.count()}")

    except Exception as e:
        print(f"[RAG] Erro no reflection: {e}")


# ── Utilitários ────────────────────────────────────────────────────────────────

def total_memorias() -> int:
    return _collection.count()

def listar_memorias(query: str = "") -> list[dict]:
    """Para debug/admin — lista todas ou filtra por query."""
    if query:
        res = _collection.query(query_texts=[query], n_results=min(30, _collection.count()))
        return [
            {"id": res["ids"][0][i], "documento": res["documents"][0][i], "distancia": res["distances"][0][i]}
            for i in range(len(res["ids"][0]))
        ]
    res = _collection.get()
    return [
        {"id": res["ids"][i], "documento": res["documents"][i], "metadata": res["metadatas"][i]}
        for i in range(len(res["ids"]))
    ]

def deletar_memoria(mem_id: str):
    _collection.delete(ids=[mem_id])

def limpar_short_term():
    """Remove apenas memórias de curto prazo (geradas por reflection)."""
    short = _collection.get(where={"type": "short-term"})
    if short["ids"]:
        _collection.delete(ids=short["ids"])
        print(f"[RAG] {len(short['ids'])} memórias short-term removidas.")