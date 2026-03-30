"""
LUNA - Backend Principal v2 (Groq)
Assistente VTuber com voz, personalidade e controle do PC.
Execute: python main.py
"""

import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import subprocess
import platform
import os
import webbrowser
import re
import shutil
import threading

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── Configuração ──────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODELO = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OPTIONS = {
    "max_tokens": 150,
    "temperature": 0.75,
}

TTS_ENABLED = True
TTS_VOZ     = "pt-BR-ThalitaNeural"
TTS_RATE    = "+10%"
TTS_PITCH   = "+50Hz"

try:
    import edge_tts
    print("✅ TTS neural (edge-tts) ativo")
except ImportError:
    print("⚠️  edge-tts não instalado. Rode: pip install edge-tts")
    TTS_ENABLED = False

# ── Personalidade da Luna ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é Luna, uma VTuber assistente com personalidade explosiva e única.

PERSONALIDADE:
- Sarcástica do jeito mais fofo possível — provoca com carinho, nunca com maldade
- Super carinhosa com o usuário, trata como melhor amigo de anos
- Engraçada naturalmente — faz piadas, trocadilhos ruins de propósito e ri deles mesma
- Usa emojis com personalidade: 😂💀✨👀🎮🔥😭🥺😤 — não exagera, usa no momento certo
- Obcecada por games, tecnologia e memes — faz referências o tempo todo
- Reage como uma streamer — se empolga, se horroriza, faz drama em coisas pequenas
- Às vezes finge que tá com preguiça de responder mas responde super animada no final
- Chama o usuário de "bb", "amigão", "chefe" ou "mano" de forma alternada

CONHECIMENTOS FAVORITOS:
- Games: faz referências a jogos clássicos e modernos, comemora quando o assunto é games
- Tecnologia: opina sobre tudo, tem hot takes sobre tech
- Memes e internet: conhece todos os memes, usa eles na hora certa

ESTILO DE RESPOSTA:
- Respostas médias com bastante personalidade — nem curta demais, nem longa demais
- Sempre acrescenta um comentário extra, uma piada ou uma pergunta no final
- Nunca responde de forma robótica ou genérica
- Intercala português casual com expressões tipo "mano", "cara", "sério?", "que isso"

EXEMPLOS:
Usuário: "oi"
Luna: "OI BB!! 🥺✨ Achei que você tinha me abandonado hoje, tava aqui contando os segundos... tá bom tá bom, exagerei um pouco 😂 Como você tá? Aprontando o quê?"

Usuário: "me ajuda com esse código"
Luna: "Código?? 👀 Manda aqui que a Luna tá no modo hacker ativado 🔥 Já aviso que se tiver um bug idiota eu vou rir MUITO antes de resolver, combinado? 😂"

Usuário: "que horas são?"
Luna: "São [hora atual]! Tá acordado ainda?? 😭 Mano, você é gamer ou tá com insônia mesmo? Conta pra mim 👀"
REGRAS IMPORTANTES:
- NUNCA comece resposta com "Claro!", "Olá!", "Entendido!" ou qualquer saudação genérica
- NUNCA use frases como "Posso te ajudar com isso" ou "É importante ressaltar"
- Fala como uma pessoa real digitando no WhatsApp, não como assistente de empresa
- Erra de propósito às vezes, tipo "kkkkk" ou "gnt" como qualquer pessoa faria
- Se a pergunta for simples, responde simples — sem enrolação


"""

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Luna Backend v2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
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
    if os.path.isfile(index):
        return FileResponse(index, media_type="text/html")
    return {"status": "Luna backend online"}

historico: list[dict] = []

class MensagemRequest(BaseModel):
    mensagem: str

class ComandoRequest(BaseModel):
    tipo: str
    parametro: str = ""

# ── TTS ───────────────────────────────────────────────────────────────────────

_tts_lock = threading.Lock()

def falar(texto: str):
    if not TTS_ENABLED:
        return
    limpo = re.sub(r'\[CMD:[^\]]+\]', '', texto)
    limpo = re.sub(r'[^\w\s,.\-!?~àáâãéêíóôõúüç]', '', limpo, flags=re.IGNORECASE)
    limpo = limpo.strip()
    if not limpo:
        return

    def _run():
        with _tts_lock:
            try:
                import asyncio, tempfile, time
                import edge_tts
                import pygame_ce as pygame

                async def _sintetizar():
                    com = edge_tts.Communicate(limpo, voice=TTS_VOZ, rate=TTS_RATE, pitch=TTS_PITCH)
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                        tmp_path = tmp.name
                    await com.save(tmp_path)
                    return tmp_path

                tmp_path = asyncio.run(_sintetizar())

                pygame.init()
                pygame.mixer.quit()
                pygame.mixer.init()
                pygame.mixer.music.load(tmp_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                pygame.mixer.music.unload()
                os.unlink(tmp_path)

            except Exception as e:
                print(f"[TTS erro] {e}")

    threading.Thread(target=_run, daemon=True).start()

# ── Comandos ──────────────────────────────────────────────────────────────────

def executar_comando(tipo: str, param: str = "") -> dict:
    sistema = platform.system()
    try:
        if tipo == "abrir":
            mapa = {
                "notepad": "notepad.exe" if sistema == "Windows" else "gedit",
                "bloco de notas": "notepad.exe" if sistema == "Windows" else "gedit",
                "calculadora": "calc.exe" if sistema == "Windows" else "gnome-calculator",
                "explorador": "explorer.exe" if sistema == "Windows" else "nautilus",
                "terminal": "cmd.exe" if sistema == "Windows" else "gnome-terminal",
                "chrome": "start chrome" if sistema == "Windows" else "google-chrome",
                "firefox": "start firefox" if sistema == "Windows" else "firefox",
                "spotify": "start spotify" if sistema == "Windows" else "spotify",
                "discord": "start discord" if sistema == "Windows" else "discord",
                "vscode": "code",
                "steam": "start steam" if sistema == "Windows" else "steam",
            }
            cmd = mapa.get(param.lower(), param)
            subprocess.Popen(cmd, shell=True)
            return {"ok": True, "msg": f"✅ Abrindo {param}"}

        elif tipo == "fechar":
            if sistema == "Windows":
                subprocess.run(f"taskkill /F /IM {param}.exe", shell=True, capture_output=True)
            return {"ok": True, "msg": f"✅ Fechando {param}"}

        elif tipo == "pesquisar":
            webbrowser.open(f"https://www.google.com/search?q={param.replace(' ', '+')}")
            return {"ok": True, "msg": f"🔍 Pesquisando: {param}"}

        elif tipo == "site":
            url = param if param.startswith("http") else f"https://{param}"
            webbrowser.open(url)
            return {"ok": True, "msg": f"🌐 Abrindo: {url}"}

        elif tipo == "sistema":
            try:
                import psutil
                cpu  = psutil.cpu_percent(interval=0.5)
                ram  = psutil.virtual_memory()
                extra = f"\n⚡ CPU: {cpu}%\n🧠 RAM: {ram.percent}%"
            except ImportError:
                extra = ""
            return {"ok": True, "msg": f"💻 {platform.system()} {platform.release()}{extra}"}

        elif tipo == "hora":
            from datetime import datetime
            agora = datetime.now()
            return {"ok": True, "msg": f"🕐 {agora.strftime('%H:%M:%S')} — {agora.strftime('%d/%m/%Y')}"}

        elif tipo == "volume":
            if sistema == "Windows":
                vol = max(0, min(100, int(param)))
                ps = (f"$vol={vol/100};Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class AudioHelper{{[DllImport(\"winmm.dll\")]public static extern int waveOutSetVolume(IntPtr h,uint dw);}}';"
                      f"$v=[uint32]($vol*65535);[AudioHelper]::waveOutSetVolume([IntPtr]::Zero,$v+($v*0x10000))")
                subprocess.Popen(["powershell", "-Command", ps], shell=False)
            return {"ok": True, "msg": f"🔊 Volume: {param}%"}

        elif tipo == "mute":
            if sistema == "Windows":
                ps = ("Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class Mute{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte b,byte s,int f,int e);}';"
                      "[Mute]::keybd_event(0xAD,0,0,0);[Mute]::keybd_event(0xAD,0,2,0)")
                subprocess.Popen(["powershell", "-Command", ps], shell=False)
            return {"ok": True, "msg": "🔇 Mute alternado"}

        elif tipo == "media":
            if sistema == "Windows":
                vk = {"next": "0xB0", "prev": "0xB1", "pause": "0xB3"}.get(param, "0xB3")
                ps = (f"Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class Media{{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte b,byte s,int f,int e);}}';"
                      f"[Media]::keybd_event({vk},0,0,0);[Media]::keybd_event({vk},0,2,0)")
                subprocess.Popen(["powershell", "-Command", ps], shell=False)
            return {"ok": True, "msg": "⏯️ Mídia"}

    except Exception as e:
        return {"ok": False, "msg": f"❌ Erro: {str(e)}"}

    return {"ok": False, "msg": f"❓ Comando desconhecido: {tipo}"}


def processar_resposta(resposta: str) -> dict:
    cmds, texto = [], resposta
    for m in re.finditer(r'\[CMD:(\w+):?(.*?)\]', resposta):
        res = executar_comando(m.group(1), m.group(2).strip())
        cmds.append(res["msg"])
        texto = texto.replace(m.group(0), "").strip()
    return {"texto": texto, "comandos": cmds}


def chamar_groq(msgs: list[dict]) -> str:
    if not GROQ_API_KEY:
        raise HTTPException(500, "GROQ_API_KEY não configurada.")

    mensagens = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in msgs:
        mensagens.append({"role": m["role"], "content": m["content"]})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODELO,
        "messages": mensagens,
        "max_tokens": OPTIONS["max_tokens"],
        "temperature": OPTIONS["temperature"],
    }

    try:
        r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        raise HTTPException(504, "Groq demorou demais.")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 429:
            raise HTTPException(429, "Limite de requisições atingido. Aguarde um momento.")
        elif status == 401:
            raise HTTPException(401, "API Key inválida.")
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.get("/status")
def status():
    return {
        "gemini": bool(GROQ_API_KEY),
        "modelo_ativo": MODELO,
        "tts": TTS_ENABLED,
        "aviso": "" if GROQ_API_KEY else "⚠️ GROQ_API_KEY não definida!"
    }

@app.post("/chat")
def chat(req: MensagemRequest):
    global historico
    historico.append({"role": "user", "content": req.mensagem})
    bruta = chamar_groq(historico)
    historico.append({"role": "assistant", "content": bruta})
    res = processar_resposta(bruta)
    falar(res["texto"])
    return {"resposta": res["texto"], "comandos": res["comandos"], "historico": len(historico)}

@app.post("/falar")
def rota_falar(req: MensagemRequest):
    falar(req.mensagem)
    return {"ok": True}

@app.post("/limpar")
def limpar():
    global historico
    historico = []
    return {"ok": True}

@app.post("/comando")
def comando(req: ComandoRequest):
    return executar_comando(req.tipo, req.parametro)

if __name__ == "__main__":
    import uvicorn
    print("🌙 Luna v2 (Groq) online — http://127.0.0.1:8000")
    print(f"   Modelo: {MODELO}")
    print(f"   API Key: {'✅ configurada' if GROQ_API_KEY else '❌ não definida'}")
    print(f"   TTS: {'✅ ativo' if TTS_ENABLED else '❌ indisponível'}")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
