"""
ALTERAÇÕES NO main.py PARA WAKE WORD
Aplique estas mudanças no seu main.py atual.
São apenas 3 adições — o resto do arquivo fica igual.
"""

# ═══════════════════════════════════════════════════════════
# MUDANÇA 1 — No topo do arquivo, após "from commands import..."
# Adicione esta linha:
# ═══════════════════════════════════════════════════════════

import wake_word

# ═══════════════════════════════════════════════════════════
# MUDANÇA 2 — Nova rota, adicione junto com as outras rotas
# (ex: logo após @app.get("/status"))
# ═══════════════════════════════════════════════════════════

# Cole isto no main.py:
"""
@app.get("/wake")
def wake_status():
    \"\"\"
    Frontend chama este endpoint a cada 1s.
    Retorna {ativado: true} quando 'Luna' foi detectado.
    Consome a flag (próxima chamada retorna false até detectar de novo).
    \"\"\"
    return {"ativado": wake_word.consumir_ativacao()}
"""

# ═══════════════════════════════════════════════════════════
# MUDANÇA 3 — No bloco if __name__ == "__main__":
# Adicione wake_word.iniciar() ANTES do uvicorn.run(...)
# ═══════════════════════════════════════════════════════════

# O bloco final fica assim:
"""
if __name__ == "__main__":
    import uvicorn
    print("🌙 Luna v2 (Groq) online — http://127.0.0.1:8000")
    print(f"   Modelo:   {MODELO}  |  Whisper: whisper-large-v3-turbo")
    print(f"   API Key:  {'✅ configurada' if GROQ_API_KEY else '❌ não definida'}")
    print(f"   TTS:      {'✅ edge-tts → /audio' if TTS_ENABLED else '❌ indisponível'}")
    
    wake_word.iniciar()   # ← ADICIONE ESTA LINHA
    
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
"""
