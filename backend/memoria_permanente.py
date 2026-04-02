# memoria_permanente.py
"""
Módulo de memória da Luna.
Interface mantida igual — main.py não precisa mudar as chamadas antigas.
Internamente, agora usa RAG (ChromaDB) além do JSON histórico.
"""

import json
import os
from datetime import datetime

CAMINHO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "historico_permanente.json"
)

# ── Palavras que indicam dia ruim ──────────────────────────────────────────────
_PALAVRAS_DIA_RUIM = [
    "triste", "cansado", "cansada", "mal", "péssimo", "péssima",
    "horrível", "chateado", "chateada", "deprimido", "deprimida",
    "ansioso", "ansiosa", "estressado", "estressada", "sozinho",
    "sozinha", "chorei", "choro", "difícil", "frustrado", "frustrada",
    "decepcionado", "decepcionada", "exausto", "exausta", "tô mal",
    "tô péssimo", "não tô bem", "tudo errado", "dia horrível",
]

# ── IAs rivais ─────────────────────────────────────────────────────────────────
_IAS_RIVAIS = [
    "chatgpt", "gpt", "openai", "gemini", "bard", "copilot",
    "claude", "anthropic", "mistral", "perplexity", "meta ai",
    "llama", "grok", "ani", "character ai", "character.ai",
    "replika", "pi ai", "inflection",
]

# ── Salvar / carregar (JSON histórico) ────────────────────────────────────────

def salvar(usuario: str, luna: str, humor: str = "neutro"):
    dados = carregar_tudo()
    dados.append({
        "timestamp": datetime.now().isoformat(),
        "data":      datetime.now().strftime("%d/%m/%Y"),
        "hora":      datetime.now().strftime("%H:%M"),
        "usuario":   usuario,
        "luna":      luna,
        "humor":     humor,
    })
    with open(CAMINHO, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def carregar_tudo() -> list:
    if not os.path.isfile(CAMINHO):
        return []
    try:
        with open(CAMINHO, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def buscar_recentes(n: int = 30) -> list:
    return carregar_tudo()[-n:]

def buscar_por_palavra(palavra: str) -> list:
    palavra = palavra.lower()
    return [
        m for m in carregar_tudo()
        if palavra in m.get("usuario", "").lower()
        or palavra in m.get("luna", "").lower()
    ]

def resumo_para_prompt(n: int = 10) -> str:
    """Últimas N trocas formatadas para o prompt."""
    recentes = buscar_recentes(n)
    if not recentes:
        return "Nenhuma conversa anterior."
    linhas = []
    for m in recentes:
        linhas.append(f"[{m['data']} {m['hora']}] Usuário: {m['usuario']}")
        linhas.append(f"[{m['data']} {m['hora']}] Luna: {m['luna']}")
    return "\n".join(linhas)

def total_conversas() -> int:
    return len(carregar_tudo())

# ── Detecção de contexto ───────────────────────────────────────────────────────

def detectar_humor(texto: str) -> str:
    t = texto.lower()
    if any(p in t for p in _PALAVRAS_DIA_RUIM):
        return "ruim"
    return "neutro"

def detectar_ia_rival(texto: str) -> str | None:
    t = texto.lower()
    for ia in _IAS_RIVAIS:
        if ia in t:
            return ia
    return None

# ── Dias ruins ─────────────────────────────────────────────────────────────────

def buscar_dias_ruins(max_resultados: int = 5) -> list:
    todos = carregar_tudo()
    ruins = [m for m in todos if m.get("humor") == "ruim"]
    return ruins[-max_resultados:]

def resumo_dias_ruins() -> str:
    dias = buscar_dias_ruins()
    if not dias:
        return "Nenhum dia difícil registrado ainda."
    linhas = []
    for m in dias:
        linhas.append(
            f"[{m['data']}] Usuário disse: \"{m['usuario']}\" → Luna respondeu: \"{m['luna']}\""
        )
    return "\n".join(linhas)

def teve_dia_ruim_recente(dias: int = 7) -> bool:
    from datetime import timedelta
    limite = datetime.now() - timedelta(days=dias)
    for m in carregar_tudo():
        if m.get("humor") != "ruim":
            continue
        try:
            ts = datetime.fromisoformat(m["timestamp"])
            if ts >= limite:
                return True
        except:
            pass
    return False