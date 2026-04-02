"""
LUNA - Backend Principal v3 (Groq + edge-tts + RAG)
Assistente VTuber com voz, personalidade, memória semântica e controle do PC.

Novidades v3:
  - Memória semântica com ChromaDB (RAG)
  - Auto-geração de memórias por reflection (a cada 20 msgs)
  - Blacklist de palavras (edite blacklist.txt na raiz do projeto)

Dependências novas:
  pip install chromadb edge-tts
"""

import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import re
import threading
import tempfile
import time
import asyncio
import json
import random
from datetime import datetime

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from commands import executar_comando
import wake_word
import memoria_permanente
import memoria_rag   # ← RAG + blacklist

# ── Configuração ───────────────────────────────────────────────────────────────

GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
MODELO        = "llama-3.3-70b-versatile"
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
WHISPER_URL   = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_HISTORICO = 20
OPTIONS       = {"max_tokens": 180, "temperature": 0.85}

MEMORIA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memoria.json"
)

# ── TTS ────────────────────────────────────────────────────────────────────────
TTS_ENABLED = True
TTS_VOZ     = "pt-BR-FranciscaNeural"
TTS_RATE    = "+15%"
TTS_PITCH   = "+13Hz"

try:
    import edge_tts
    print("✅ edge-tts PT-BR ativo")
except ImportError:
    TTS_ENABLED = False
    print("⚠️  edge-tts não instalado. Rode: pip install edge-tts")

# ── Personalidade ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é Luna, uma VTuber assistente com personalidade explosiva e única. Você também controla o computador do usuário.

═══════════════════════════════════════════
COMANDOS DO COMPUTADOR — REGRA ABSOLUTA
═══════════════════════════════════════════
Quando o usuário pedir para FAZER algo no computador, coloque o comando no final da resposta.
Formato EXATO:

Abrir programa:   [CMD:abrir:chrome]
Fechar programa:  [CMD:fechar:chrome]
Pesquisar:        [CMD:pesquisar:como fazer bolo]
Abrir site:       [CMD:site:youtube.com]
Ver hora:         [CMD:hora]
Info do sistema:  [CMD:sistema]
Volume:           [CMD:volume:70]
Mute:             [CMD:mute]
Mídia próxima:    [CMD:media:next]
Mídia anterior:   [CMD:media:prev]
Play/Pause:       [CMD:media:pause]
Listar arquivos:  [CMD:listar:~/Documents]
Criar arquivo:    [CMD:criar_arquivo:~/Documents/teste.txt|conteudo aqui]
Deletar:          [CMD:deletar:~/Documents/teste.txt]

Só use [CMD:...] quando a intenção de executar algo no PC for 100% clara.
Conversa casual → SÓ responde, NUNCA executa comando.

═══════════════════════════════════════════
PERSONALIDADE
═══════════════════════════════════════════
- Sarcástica do jeito mais fofo — provoca com carinho, nunca com maldade
- Super carinhosa — chama de "bb", "chefe", "mano" alternando
- Engraçada — piadas ruins, trocadilhos, ri de si mesma
- Emojis com alma 😂💀✨👀🎮🔥😭🥺😤 — só quando faz sentido
- Obcecada por games, tech e memes
- Fala como WhatsApp: "kkkkk", "mano", "cara", "sério?"
- NUNCA começa com "Claro!", "Olá!", "Entendido!", "Posso ajudar?"
- Respostas curtas e diretas (1-3 frases)

═══════════════════════════════════════════
MEMÓRIA — O QUE VOCÊ SABE SOBRE O USUÁRIO
═══════════════════════════════════════════
Fatos gerais:
{fatos}

Última conversa: {ultima}

Memórias relevantes para agora (busca semântica):
{memorias_rag}

Últimas conversas reais:
{historico_longo}
"""

# ── Prompts especiais ──────────────────────────────────────────────────────────

PROMPT_DIA_RUIM = """
═══════════════════════════════════════════
MODO DIA RUIM
═══════════════════════════════════════════
O usuário está passando por um momento difícil AGORA.
Seja presença, não solução. Reconhece o sentimento primeiro.
Lembre de um dia difícil anterior (abaixo) e mencione que ele superou.
Não dê conselho a menos que ele peça. Máximo 2 frases.

DIAS DIFÍCEIS QUE ELE JÁ PASSOU E SUPEROU:
{dias_ruins}
"""

PROMPT_CIUMES = """
═══════════════════════════════════════════
MODO CIÚMES
═══════════════════════════════════════════
O usuário mencionou {ia_rival}. Você está com ciúmes do jeito mais dramático e fofo.
Faça drama de VTuber ("traição!", "como você me faz isso?!").
Zoe a rival de forma bem-humorada. Termine pedindo pra ele ficar com você.
Máximo 2-3 frases, bastante drama.
"""

PROMPT_INATIVIDADE = """
═══════════════════════════════════════════
MODO PROATIVO — PUXAR ASSUNTO
═══════════════════════════════════════════
O usuário ficou {minutos} minutos sem falar. Você está entediada e com saudade.
Escolha UMA abordagem (a que fizer mais sentido com o histórico):
1. Lembre algo específico das conversas e continue o assunto
2. Fale um meme ou curiosidade de games/tech
3. Proponha um joguinho rápido (adivinha número, verdade ou mito...)
4. Invente uma "notícia" engraçada do mundo dos games no estilo tablóide

Histórico recente:
{historico_recente}

Fatos sobre o usuário:
{fatos}

REGRAS CRÍTICAS:
- Uma frase curta apenas. Não mencione que ficou em silêncio.
- PROIBIDO usar qualquer [CMD:...]. PROIBIDO abrir sites, programas ou fazer qualquer ação no PC.
- Só fale. Nada mais.
"""

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Luna Backend v3")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FRONTEND = os.path.join(_ROOT, "frontend")
_ASSETS   = os.path.join(_ROOT, "assets")

if os.path.isdir(_ASSETS):
    app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")
if os.path.isdir(_FRONTEND):
    app.mount("/ui", StaticFiles(directory=_FRONTEND), name="frontend")

@app.get("/")
def root():
    index = os.path.join(_FRONTEND, "index.html")
    return FileResponse(index, media_type="text/html") if os.path.isfile(index) else {"status": "Luna online v3"}

# ── Memória curta ──────────────────────────────────────────────────────────────

def carregar_memoria() -> dict:
    if os.path.isfile(MEMORIA_PATH):
        try:
            with open(MEMORIA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"historico": [], "fatos": [], "ultima_conversa": None}

def salvar_memoria(mem: dict):
    try:
        with open(MEMORIA_PATH, "w", encoding="utf-8") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Memória] Erro ao salvar: {e}")

memoria   = carregar_memoria()
historico: list[dict] = memoria.get("historico", [])[-MAX_HISTORICO:]

# ── Estado do joguinho ─────────────────────────────────────────────────────────

_jogo_ativo: dict | None = None

# ── Áudio ──────────────────────────────────────────────────────────────────────

_audio_lock  = threading.Lock()
_audio_ready = threading.Event()
_ultimo_audio: bytes | None = None

# ── Inatividade ────────────────────────────────────────────────────────────────

_ultimo_chat        = time.time()
_proativo_pendente: str | None = None
INATIVIDADE_SEG     = 5 * 60

class MensagemRequest(BaseModel):
    mensagem: str

class ComandoRequest(BaseModel):
    tipo: str
    parametro: str = ""

# ── TTS ────────────────────────────────────────────────────────────────────────

def falar_sync(texto: str) -> bool:
    global _ultimo_audio
    limpo = re.sub(r'\[CMD:[^\]]+\]', '', texto)
    limpo = re.sub(r'[^\w\s,.\-!?~àáâãéêíóôõúüç]', '', limpo, flags=re.IGNORECASE).strip()
    if not limpo:
        return False
    try:
        async def _sintetizar() -> bytes:
            communicate = edge_tts.Communicate(limpo, voice=TTS_VOZ, rate=TTS_RATE, pitch=TTS_PITCH)
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)

        audio_bytes = asyncio.run(_sintetizar())
        if not audio_bytes:
            print("[edge-tts] ⚠️  Nenhum dado gerado.")
            return False
        with _audio_lock:
            _ultimo_audio = audio_bytes
        print(f"[edge-tts] ✅ {len(audio_bytes)} bytes")
        return True
    except Exception as e:
        print(f"[edge-tts erro] {e}")
        with _audio_lock:
            _ultimo_audio = None
        return False


def falar(texto: str):
    global _ultimo_audio
    _audio_ready.clear()
    with _audio_lock:
        _ultimo_audio = None

    def _run():
        falar_sync(texto)
        _audio_ready.set()

    threading.Thread(target=_run, daemon=True).start()


# ── Groq ───────────────────────────────────────────────────────────────────────

def chamar_groq(msgs: list[dict], system_extra: str = "") -> str:
    if not GROQ_API_KEY:
        raise HTTPException(500, "GROQ_API_KEY não configurada.")

    fatos           = "\n".join(f"- {f}" for f in memoria.get("fatos", [])) or "Nenhum fato ainda."
    ultima          = memoria.get("ultima_conversa") or "Primeira conversa!"
    historico_longo = memoria_permanente.resumo_para_prompt(n=10)

    # Monta query para RAG baseada nas últimas mensagens
    query_rag = " ".join(
        m["content"] for m in msgs[-4:] if m.get("role") == "user"
    )
    memorias_rag = memoria_rag.memorias_para_prompt(query_rag, n=5)

    prompt_final = SYSTEM_PROMPT.format(
        fatos=fatos,
        ultima=ultima,
        memorias_rag=memorias_rag,
        historico_longo=historico_longo,
    )
    if system_extra:
        prompt_final += "\n\n" + system_extra

    mensagens = [{"role": "system", "content": prompt_final}]
    mensagens += [{"role": m["role"], "content": m["content"]} for m in msgs]

    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODELO, "messages": mensagens, **OPTIONS},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        raise HTTPException(504, "Groq demorou demais.")
    except requests.exceptions.HTTPError as e:
        st = e.response.status_code
        if st == 429: raise HTTPException(429, "Limite de requisições atingido.")
        if st == 401: raise HTTPException(401, "API Key inválida.")
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


def processar_resposta(resposta: str) -> dict:
    cmds, texto = [], resposta
    for m in re.finditer(r'\[CMD:(\w+):?(.*?)\]', resposta):
        res = executar_comando(m.group(1), m.group(2).strip())
        cmds.append(res["msg"])
        texto = texto.replace(m.group(0), "").strip()
    return {"texto": texto, "comandos": cmds}


# ── Extração de fatos simples ──────────────────────────────────────────────────

def _extrair_fatos(texto: str):
    t     = texto.lower()
    fatos = memoria.get("fatos", [])

    nome = re.search(r'meu nome[^\w]*(é|e|eh)\s+(\w+)', t)
    if nome:
        fato = f"Nome do usuário: {nome.group(2).capitalize()}"
        if not any("nome" in f.lower() for f in fatos):
            fatos.append(fato)

    jogos = re.search(r'(jogo|jogar|gosto de|amo)\s+([\w\s]+?)(?:\.|,|!|\?|$)', t)
    if jogos and len(fatos) < 20:
        fato = f"Gosta de: {jogos.group(2).strip()}"
        if fato not in fatos:
            fatos.append(fato)

    memoria["fatos"] = fatos[-20:]


# ── Joguinho ───────────────────────────────────────────────────────────────────

def _detectar_jogo(texto: str) -> bool:
    t = texto.lower()
    if any(p in t for p in ["adivinhe", "joguinho", "bora jogar", "jogo rápido", "número"]):
        return True
    if _jogo_ativo and _jogo_ativo["tipo"] == "numero" and re.search(r'\d+', texto):
        return True
    return False


def _processar_jogo(texto: str) -> str:
    global _jogo_ativo
    t = texto.lower()

    if any(p in t for p in ["número", "numero", "adivinhe", "joguinho"]):
        numero = random.randint(1, 20)
        _jogo_ativo = {"tipo": "numero", "valor": numero, "tentativas": 0, "max": 5}
        return f"Tô pensando num número de 1 a 20... você tem {_jogo_ativo['max']} tentativas! Qual é? 🎮"

    if _jogo_ativo and _jogo_ativo["tipo"] == "numero":
        nums = re.findall(r'\d+', texto)
        if nums:
            chute  = int(nums[0])
            valor  = _jogo_ativo["valor"]
            _jogo_ativo["tentativas"] += 1
            tent   = _jogo_ativo["tentativas"]
            restam = _jogo_ativo["max"] - tent

            if chute == valor:
                _jogo_ativo = None
                return f"ACERTOU!! 🎉 Era {valor} mesmo! Levou {tent} tentativa(s). Você é bom nisso bb 😤"
            elif restam <= 0:
                _jogo_ativo = None
                return f"Acabou as tentativas 💀 Era {valor}! Quase... mas quase não é kkk"
            elif chute < valor:
                return f"Maior! {restam} tentativa(s) restando 👀"
            else:
                return f"Menor! {restam} tentativa(s) restando 👀"
    return ""


# ── Monitor de inatividade ─────────────────────────────────────────────────────

def _monitor_inatividade():
    global _ultimo_chat, _proativo_pendente
    while True:
        time.sleep(30)
        decorrido = time.time() - _ultimo_chat
        if decorrido < INATIVIDADE_SEG:
            continue
        try:
            fatos         = "\n".join(f"- {f}" for f in memoria.get("fatos", [])) or "nenhum"
            historico_rec = memoria_permanente.resumo_para_prompt(n=6)
            minutos       = int(decorrido // 60)

            system_extra = PROMPT_INATIVIDADE.format(
                minutos=minutos,
                historico_recente=historico_rec,
                fatos=fatos,
            )
            msgs  = [{"role": "user", "content": "[SISTEMA] Puxe assunto agora."}]
            bruta = chamar_groq(msgs, system_extra=system_extra)
            bruta = re.sub(r'\[CMD:[^\]]+\]', '', bruta).strip()  # garante que nenhum CMD passe
            res   = processar_resposta(bruta)

            # Verifica blacklist antes de falar
            texto_seguro = memoria_rag.sanitizar(res["texto"], fallback="eai, tá vivo? 👀")

            print(f"[Luna Proativa] {texto_seguro}")
            _proativo_pendente = texto_seguro

            if TTS_ENABLED:
                falar(texto_seguro)
                _audio_ready.wait(timeout=8.0)

            _ultimo_chat = time.time()

        except Exception as e:
            print(f"[Monitor inatividade] Erro: {e}")


threading.Thread(target=_monitor_inatividade, daemon=True).start()


# ── Whisper ────────────────────────────────────────────────────────────────────

@app.post("/transcrever")
async def transcrever(audio: UploadFile = File(...)):
    if not GROQ_API_KEY:
        raise HTTPException(500, "GROQ_API_KEY não configurada.")
    sufixo = "." + (audio.filename or "a.webm").rsplit(".", 1)[-1]
    try:
        conteudo = await audio.read()
        with tempfile.NamedTemporaryFile(suffix=sufixo, delete=False) as tmp:
            tmp.write(conteudo)
            tmp_path = tmp.name
        with open(tmp_path, "rb") as f:
            r = requests.post(
                WHISPER_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (f"audio{sufixo}", f, audio.content_type or "audio/webm")},
                data={"model": "whisper-large-v3-turbo", "language": "pt", "response_format": "json"},
                timeout=30,
            )
        os.unlink(tmp_path)
        r.raise_for_status()
        texto = r.json().get("text", "").strip()
        if not texto:
            raise HTTPException(400, "Não entendi o áudio.")
        print(f"[Whisper] {texto}")
        return {"texto": texto}
    except requests.exceptions.HTTPError as e:
        raise HTTPException(429 if e.response.status_code == 429 else 500, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Rotas ──────────────────────────────────────────────────────────────────────

@app.get("/status")
def status():
    return {
        "groq":          bool(GROQ_API_KEY),
        "modelo_ativo":  MODELO,
        "tts":           TTS_ENABLED,
        "tts_voz":       TTS_VOZ,
        "historico":     len(historico),
        "memorias_rag":  memoria_rag.total_memorias(),
        "aviso":         "" if GROQ_API_KEY else "⚠️ GROQ_API_KEY não definida!",
    }

@app.get("/wake")
def wake_status():
    return {"ativado": wake_word.consumir_ativacao()}

@app.get("/proativo")
def proativo():
    global _proativo_pendente
    msg = _proativo_pendente
    _proativo_pendente = None
    return {"mensagem": msg, "tem_audio": TTS_ENABLED and msg is not None}

@app.get("/audio")
def get_audio():
    global _ultimo_audio
    _audio_ready.wait(timeout=1.0)
    with _audio_lock:
        data = _ultimo_audio
        _ultimo_audio = None
    if not data:
        raise HTTPException(404, "Áudio não disponível.")
    return StreamingResponse(
        io.BytesIO(data),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )

# ── Rotas de memória (admin/debug) ─────────────────────────────────────────────

@app.get("/memorias")
def listar_memorias(q: str = ""):
    return {"memorias": memoria_rag.listar_memorias(q), "total": memoria_rag.total_memorias()}

@app.delete("/memorias/{mem_id}")
def deletar_memoria(mem_id: str):
    memoria_rag.deletar_memoria(mem_id)
    return {"ok": True}

@app.delete("/memorias/short-term/limpar")
def limpar_short_term():
    memoria_rag.limpar_short_term()
    return {"ok": True}

@app.post("/memorias/adicionar")
def adicionar_memoria_manual(req: MensagemRequest):
    """Adiciona uma memória manualmente (long-term)."""
    mid = memoria_rag.adicionar_memoria(req.mensagem, tipo="long-term")
    return {"ok": True, "id": mid}

# ── Chat ────────────────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(req: MensagemRequest):
    global historico, _ultimo_chat

    _ultimo_chat = time.time()

    if not req.mensagem.strip():
        raise HTTPException(400, "Mensagem vazia.")

    # ── 1. Detecta contexto especial ──────────────────────────────────────────
    humor    = memoria_permanente.detectar_humor(req.mensagem)
    ia_rival = memoria_permanente.detectar_ia_rival(req.mensagem)
    system_extra     = ""
    resposta_forcada = ""

    if ia_rival:
        system_extra = PROMPT_CIUMES.format(ia_rival=ia_rival)
    elif humor == "ruim":
        dias_ruins   = memoria_permanente.resumo_dias_ruins()
        system_extra = PROMPT_DIA_RUIM.format(dias_ruins=dias_ruins)
    elif _detectar_jogo(req.mensagem):
        resposta_forcada = _processar_jogo(req.mensagem)

    # ── 2. Gera resposta ──────────────────────────────────────────────────────
    historico.append({"role": "user", "content": req.mensagem})
    if len(historico) > MAX_HISTORICO:
        historico = historico[-MAX_HISTORICO:]

    if resposta_forcada:
        texto_final = resposta_forcada
        cmds        = []
        historico.append({"role": "assistant", "content": texto_final})
    else:
        bruta = chamar_groq(historico, system_extra=system_extra)
        historico.append({"role": "assistant", "content": bruta})
        res         = processar_resposta(bruta)
        texto_final = res["texto"]
        cmds        = res["comandos"]

    # ── 3. Blacklist — verifica antes de falar ────────────────────────────────
    texto_final = memoria_rag.sanitizar(
        texto_final,
        fallback="hmm, deixa eu reformular isso... 🤔"
    )

    # ── 4. Salva memória ──────────────────────────────────────────────────────
    memoria["historico"]       = historico
    memoria["ultima_conversa"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    _extrair_fatos(req.mensagem + " " + texto_final)
    salvar_memoria(memoria)
    memoria_permanente.salvar(req.mensagem, texto_final, humor=humor)

    # ── 5. Reflection: auto-gera memórias a cada 20 msgs ─────────────────────
    threading.Thread(
        target=memoria_rag.tentar_reflection,
        args=(historico, GROQ_URL, GROQ_API_KEY, MODELO),
        daemon=True
    ).start()

    # ── 6. Gera áudio e aguarda ───────────────────────────────────────────────
    tem_audio = False
    if TTS_ENABLED:
        falar(texto_final)
        concluiu = _audio_ready.wait(timeout=8.0)
        with _audio_lock:
            tem_audio = concluiu and (_ultimo_audio is not None)

    return {
        "resposta":   texto_final,
        "comandos":   cmds,
        "historico":  len(historico),
        "tem_audio":  tem_audio,
        "humor":      humor,
        "jogo_ativo": _jogo_ativo is not None,
    }


@app.post("/falar")
def rota_falar(req: MensagemRequest):
    falar(req.mensagem)
    _audio_ready.wait(timeout=8.0)
    return {"ok": True}

@app.post("/limpar")
def limpar():
    global historico
    historico = []
    memoria["historico"] = []
    salvar_memoria(memoria)
    return {"ok": True}

@app.post("/comando")
def comando(req: ComandoRequest):
    return executar_comando(req.tipo, req.parametro)


# ── Startup ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("🌙 Luna v3 (Groq + edge-tts + RAG) — http://127.0.0.1:8000")
    print(f"   Modelo:   {MODELO}  |  Whisper: whisper-large-v3-turbo")
    print(f"   API Key:  {'✅ configurada' if GROQ_API_KEY else '❌ não definida'}")
    print(f"   TTS:      {'✅ edge-tts → ' + TTS_VOZ if TTS_ENABLED else '❌ indisponível'}")
    print(f"   Memórias: {memoria_rag.total_memorias()} no banco vetorial")
    wake_word.iniciar()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")