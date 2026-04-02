"""
wake_word.py — Luna
Fica ouvindo o microfone em loop.
Quando detecta "luna" no áudio, sinaliza para o backend via flag global.

Rodado automaticamente pelo main.py em thread separada.
NÃO execute diretamente.
"""

import io
import os
import time
import threading
import tempfile
import requests
import numpy as np

# ── Configuração ──────────────────────────────────────────────────────────────

GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
WHISPER_URL   = "https://api.groq.com/openai/v1/audio/transcriptions"

CHUNK_SEGUNDOS   = 2.5    # duração de cada "escuta" em segundos
SAMPLE_RATE      = 16000  # Hz — padrão Whisper
SILENCIO_THRESH  = 0.008  # RMS mínimo pra considerar que tem fala (evita mandar silêncio)
PALAVRA_ATIVACAO = "luna" # palavra que aciona (lowercase)

# Flag global — True quando "Luna" foi detectado e está aguardando comando
_ativado        = False
_ativado_lock   = threading.Lock()
_rodando        = False

def esta_ativado() -> bool:
    with _ativado_lock:
        return _ativado

def consumir_ativacao() -> bool:
    """Retorna True e reseta a flag. Usado pelo /wake endpoint."""
    global _ativado
    with _ativado_lock:
        if _ativado:
            _ativado = False
            return True
        return False

def _tem_voz(audio_bytes: bytes) -> bool:
    """Checa se o áudio tem energia suficiente pra valer mandar pro Whisper."""
    try:
        arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(arr ** 2)))
        return rms > SILENCIO_THRESH
    except Exception:
        return True  # se não deu pra checar, manda assim mesmo

def _transcrever(audio_bytes: bytes, mime: str = "audio/wav") -> str:
    """Manda o áudio pro Whisper e retorna a transcrição em lowercase."""
    if not GROQ_API_KEY:
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as f:
            r = requests.post(
                WHISPER_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": "whisper-large-v3-turbo", "language": "pt", "response_format": "json"},
                timeout=10,
            )
        os.unlink(tmp_path)
        r.raise_for_status()
        return r.json().get("text", "").lower().strip()
    except Exception as e:
        print(f"[Wake] erro Whisper: {e}")
        return ""

def _gravar_chunk() -> bytes | None:
    """Grava CHUNK_SEGUNDOS de áudio e retorna bytes WAV."""
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wav

        amostras = int(SAMPLE_RATE * CHUNK_SEGUNDOS)
        audio = sd.rec(amostras, samplerate=SAMPLE_RATE, channels=1, dtype='int16', blocking=True)

        buf = io.BytesIO()
        wav.write(buf, SAMPLE_RATE, audio)
        return buf.getvalue()

    except Exception as e:
        print(f"[Wake] erro ao gravar: {e}")
        time.sleep(1)
        return None

def _loop():
    """Loop principal — fica escutando e checando a palavra de ativação."""
    global _ativado, _rodando

    print("[Wake] 🎙️ Ouvindo... diga 'Luna' para ativar.")

    while _rodando:
        audio = _gravar_chunk()
        if not audio:
            continue

        # Pula silêncio pra economizar chamadas à API
        if not _tem_voz(audio):
            continue

        texto = _transcrever(audio)
        if not texto:
            continue

        print(f"[Wake] ouviu: '{texto}'")

        if PALAVRA_ATIVACAO in texto:
            with _ativado_lock:
                _ativado = True
            print("[Wake] ✅ 'Luna' detectado! Aguardando comando...")

def iniciar():
    """Inicia o loop de wake word em thread daemon."""
    global _rodando

    # Verifica dependências
    try:
        import sounddevice  # noqa
        import scipy        # noqa
    except ImportError:
        print("[Wake] ⚠️  Dependências faltando. Rode:")
        print("       pip install sounddevice scipy numpy")
        print("[Wake] Wake word DESATIVADO.")
        return

    if not GROQ_API_KEY:
        print("[Wake] ⚠️  GROQ_API_KEY não definida — wake word desativado.")
        return

    _rodando = True
    t = threading.Thread(target=_loop, daemon=True, name="wake-word")
    t.start()

def parar():
    global _rodando
    _rodando = False
