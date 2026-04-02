# 🌙 Luna — VTuber Assistente de Desktop

> Assistente VTuber local com modelo 3D animado, voz neural em PT-BR, chat por texto ou microfone e controle do PC — rodando com a API do **Groq** (gratuita e ultra-rápida).

---

<img width="1920" height="1032" alt="image" src="https://github.com/user-attachments/assets/64e5ca4d-d0f9-4832-a6ed-e1eb944c08cf" />

## ✨ Funcionalidades

- 🎭 **Modelo 3D VRM animado** — respiração, piscar natural, rastreamento de olhar pelo mouse e expressões emocionais
- 🗣️ **Voz neural PT-BR** — via edge-tts (Microsoft), 100% gratuita
- 🎤 **Entrada por microfone** — segure o botão e fale
- 💬 **Memória de conversa** — lembra o contexto das últimas mensagens
- 🖥️ **Controle do PC** — abre/fecha programas, ajusta volume, pesquisa na web, gerencia arquivos
- ⚡ **Groq API** — respostas extremamente rápidas com modelos open-source

---

## 🚀 Início Rápido

### 1. Pré-requisitos

- Python 3.10 ou superior → [python.org/downloads](https://python.org/downloads)
- Google Chrome (para microfone funcionar corretamente)
- Conta Groq gratuita → [console.groq.com](https://console.groq.com)

### 2. Instalar dependências

```bash
pip install -r backend/requirements.txt
```

### 3. Adicionar o modelo 3D

Coloque seu arquivo VRM em:
```
assets/luna.vrm
```

> O modelo não está incluso no repositório por questões de licença.  
> Você pode baixar modelos gratuitos em [hub.vroid.com](https://hub.vroid.com) ou [booth.pm](https://booth.pm).

### 4. Rodar

**Windows (PowerShell):**
```powershell
$env:GROQ_API_KEY="sua_chave_aqui"; python run_standalone.py
```

**Linux / Mac:**
```bash
export GROQ_API_KEY=sua_chave_aqui && python run_standalone.py
```

O Chrome abrirá automaticamente com a Luna. Se não abrir, acesse: **http://127.0.0.1:8000**

---

## 🔑 Como obter a chave Groq (gratuita)

1. Acesse [console.groq.com](https://console.groq.com) e crie uma conta
2. Vá em **API Keys → Create API Key**
3. Copie a chave (começa com `gsk_...`)
4. Use no comando de execução conforme mostrado acima

> A chave **nunca deve ser salva em arquivo** nem commitada no repositório.

---

## 🖥️ Comandos que a Luna entende

| Você fala / digita           | O que acontece                  |
|------------------------------|---------------------------------|
| "Abre o bloco de notas"      | Abre o Notepad                  |
| "Pesquisa receita de bolo"   | Abre Google com a busca         |
| "Que horas são?"             | Mostra hora e data              |
| "Informações do sistema"     | CPU, RAM e disco                |
| "Abre o Discord"             | Abre o Discord                  |
| "Volume 70"                  | Ajusta volume do sistema        |
| "Lista os arquivos"          | Lista a pasta home              |
| "Cria um arquivo teste.txt"  | Cria arquivo em Documents       |

---

## 📁 Pastas seguras para arquivos

Por segurança, a Luna só cria ou deleta arquivos dentro de:

- `~/Documents`
- `~/Desktop`
- `~/Downloads`
- `~/luna_workspace`

---

## 📂 Estrutura do Projeto

```
luna/
├── backend/
│   ├── main.py               ← Backend FastAPI + Groq + TTS
│   └── requirements.txt      ← Dependências Python
├── frontend/
│   └── index.html            ← Interface VTuber (Three.js + VRM)
├── assets/
│   └── luna.vrm              ← Modelo 3D (não incluso, veja acima)
├── run_standalone.py         ← Script de inicialização
└── README.md
```

---

## 🛠️ Solução de Problemas

**"Backend offline" na interface**
→ Rode `python backend/main.py` direto no terminal para ver o erro exato

**Modelo 3D não carrega**
→ Confirme que `assets/luna.vrm` existe  
→ Abra o console do navegador (F12) para ver o erro  
→ O chat de texto funciona mesmo sem o modelo 3D

**Voz não funciona**
```bash
pip install edge-tts pygame

# Linux — pode precisar de:
sudo apt install libespeak1
```

**Microfone não funciona**
→ Use sempre o `run_standalone.py` — ele abre o Chrome com permissão automática  
→ Se abrir manualmente, clique no 🔒 na barra de endereços e permita o microfone

**Resposta lenta**
→ Verifique sua conexão — Groq é uma API online  
→ No plano gratuito há limite de requisições por minuto

---

## 📄 Licença

MIT — sinta-se livre para usar, modificar e distribuir.

> O modelo VRM (`luna.vrm`) tem licença própria do criador original e **não está incluso** neste repositório.
