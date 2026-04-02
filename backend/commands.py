"""
commands.py — Luna
Execução de comandos do sistema operacional.
Importado pelo main.py — não execute diretamente.
"""

import subprocess
import platform
import webbrowser
import os
import shutil
from pathlib import Path
from datetime import datetime

SISTEMA = platform.system()

# ── Pastas seguras para operações de arquivo ──────────────────────────────────
PASTAS_PERMITIDAS = [
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "luna_workspace",
]

def caminho_seguro(caminho_str: str) -> Path | None:
    """Retorna Path resolvido só se estiver dentro das pastas permitidas."""
    try:
        p = Path(os.path.expanduser(caminho_str)).resolve()
        for pasta in PASTAS_PERMITIDAS:
            try:
                p.relative_to(pasta.resolve())
                return p
            except ValueError:
                continue
        return None
    except Exception:
        return None

# ── Mapa de programas por OS ──────────────────────────────────────────────────
_ABRIR_WIN = {
    "notepad":                  "notepad.exe",
    "bloco de notas":           "notepad.exe",
    "calculadora":              "calc.exe",
    "explorador":               "explorer.exe",
    "gerenciador":              "explorer.exe",
    "terminal":                 "cmd.exe",
    "cmd":                      "cmd.exe",
    "powershell":               "powershell.exe",
    "chrome":                   "start chrome",
    "navegador":                "start chrome",
    "firefox":                  "start firefox",
    "spotify":                  "start spotify",
    "discord":                  "start discord",
    "vscode":                   "code",
    "word":                     "start winword",
    "excel":                    "start excel",
    "paint":                    "mspaint.exe",
    "gerenciador de tarefas":   "taskmgr.exe",
    "task manager":             "taskmgr.exe",
    "steam":                    "start steam",
    "obs":                      "start obs64",
    "whatsapp":                 "start whatsapp",
    "telegram":                 "start telegram",
}

_ABRIR_LINUX = {
    "notepad":                  "gedit",
    "bloco de notas":           "gedit",
    "calculadora":              "gnome-calculator",
    "explorador":               "nautilus",
    "gerenciador":              "nautilus",
    "terminal":                 "gnome-terminal",
    "cmd":                      "bash",
    "chrome":                   "google-chrome",
    "navegador":                "google-chrome",
    "firefox":                  "firefox",
    "spotify":                  "spotify",
    "discord":                  "discord",
    "vscode":                   "code",
    "word":                     "libreoffice --writer",
    "excel":                    "libreoffice --calc",
    "paint":                    "gimp",
    "gerenciador de tarefas":   "gnome-system-monitor",
    "task manager":             "gnome-system-monitor",
    "steam":                    "steam",
    "obs":                      "obs",
}

_ABRIR_MAC = {
    "notepad":                  "open -a TextEdit",
    "bloco de notas":           "open -a TextEdit",
    "calculadora":              "open -a Calculator",
    "explorador":               "open -a Finder",
    "gerenciador":              "open -a Finder",
    "terminal":                 "open -a Terminal",
    "cmd":                      "open -a Terminal",
    "chrome":                   "open -a 'Google Chrome'",
    "navegador":                "open -a 'Google Chrome'",
    "firefox":                  "open -a Firefox",
    "spotify":                  "open -a Spotify",
    "discord":                  "open -a Discord",
    "vscode":                   "open -a 'Visual Studio Code'",
    "word":                     "open -a 'Microsoft Word'",
    "excel":                    "open -a 'Microsoft Excel'",
    "paint":                    "open -a Preview",
    "gerenciador de tarefas":   "open -a 'Activity Monitor'",
    "task manager":             "open -a 'Activity Monitor'",
    "steam":                    "open -a Steam",
    "obs":                      "open -a OBS",
}

def _cmd_abrir(param: str) -> dict:
    nome = param.lower().strip()
    if SISTEMA == "Windows":
        cmd = _ABRIR_WIN.get(nome, nome)
    elif SISTEMA == "Darwin":
        cmd = _ABRIR_MAC.get(nome, f"open -a '{param}'")
    else:
        cmd = _ABRIR_LINUX.get(nome, nome)
    subprocess.Popen(cmd, shell=True)
    return {"ok": True, "msg": f"✅ Abrindo {param}"}

def _cmd_fechar(param: str) -> dict:
    nome = param.lower().strip()
    if SISTEMA == "Windows":
        subprocess.run(f"taskkill /F /IM {nome}.exe", shell=True, capture_output=True)
    elif SISTEMA == "Darwin":
        subprocess.run(f"osascript -e 'quit app \"{param}\"'", shell=True, capture_output=True)
    else:
        subprocess.run(f"pkill -f {nome}", shell=True, capture_output=True)
    return {"ok": True, "msg": f"✅ Fechando {param}"}

def _cmd_pesquisar(param: str) -> dict:
    url = f"https://www.google.com/search?q={param.replace(' ', '+')}"
    webbrowser.open(url)
    return {"ok": True, "msg": f"🔍 Pesquisando: {param}"}

def _cmd_site(param: str) -> dict:
    url = param if param.startswith("http") else f"https://{param}"
    webbrowser.open(url)
    return {"ok": True, "msg": f"🌐 Abrindo: {url}"}

def _cmd_listar(param: str) -> dict:
    pasta = Path(os.path.expanduser(param or "~"))
    if not pasta.exists():
        return {"ok": False, "msg": f"❌ Pasta não encontrada: {pasta}"}
    itens = list(pasta.iterdir())[:30]
    dirs  = [f"📁 {i.name}" for i in itens if i.is_dir()]
    files = [f"📄 {i.name}" for i in itens if i.is_file()]
    return {"ok": True, "msg": f"📂 {pasta}\n" + "\n".join(dirs + files)}

def _cmd_ler(param: str) -> dict:
    p = caminho_seguro(param)
    if not p:
        return {"ok": False, "msg": f"❌ Acesso negado: '{param}' fora das pastas permitidas."}
    if not p.is_file():
        return {"ok": False, "msg": f"❌ Arquivo não encontrado: {param}"}
    conteudo = p.read_text(encoding="utf-8", errors="ignore")[:2000]
    return {"ok": True, "msg": f"📄 {param}:\n\n{conteudo}"}

def _cmd_criar_arquivo(param: str) -> dict:
    partes = param.split("|", 1)
    p = caminho_seguro(partes[0].strip())
    if not p:
        return {"ok": False, "msg": "❌ Acesso negado: caminho fora das pastas permitidas."}
    conteudo = partes[1] if len(partes) > 1 else ""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(conteudo, encoding="utf-8")
    return {"ok": True, "msg": f"✅ Arquivo criado: {p}"}

def _cmd_criar_pasta(param: str) -> dict:
    p = caminho_seguro(param)
    if not p:
        return {"ok": False, "msg": "❌ Acesso negado: caminho fora das pastas permitidas."}
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "msg": f"✅ Pasta criada: {p}"}

def _cmd_deletar(param: str) -> dict:
    p = caminho_seguro(param)
    if not p:
        return {"ok": False, "msg": f"❌ Acesso negado: '{param}' fora das pastas permitidas.\nSó posso deletar dentro de: Documents, Desktop, Downloads ou luna_workspace."}
    if not p.exists():
        return {"ok": False, "msg": f"❌ Não encontrado: {param}"}
    if p.is_file():
        p.unlink()
    elif p.is_dir():
        shutil.rmtree(p)
    return {"ok": True, "msg": f"🗑️ Deletado: {p}"}

def _cmd_sistema() -> dict:
    info = f"💻 {platform.system()} {platform.release()}\n🖥️  {platform.node()}\n🐍 Python {platform.python_version()}"
    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=0.5)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        info += (
            f"\n⚡ CPU: {cpu}%"
            f"\n🧠 RAM: {ram.percent}% ({ram.used//1024**3}GB/{ram.total//1024**3}GB)"
            f"\n💾 Disco: {disk.percent}% usado"
        )
    except ImportError:
        info += "\n(instale psutil para mais detalhes)"
    return {"ok": True, "msg": info}

def _cmd_hora() -> dict:
    agora = datetime.now()
    return {"ok": True, "msg": f"🕐 {agora.strftime('%H:%M:%S')} — {agora.strftime('%d/%m/%Y')}"}

def _cmd_volume(param: str) -> dict:
    vol = max(0, min(100, int(param)))
    if SISTEMA == "Windows":
        ps = (
            f"$vol={vol/100};"
            f"Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
            f"public class AudioHelper{{[DllImport(\"winmm.dll\")]public static extern int waveOutSetVolume(IntPtr h,uint dw);}}';"
            f"$v=[uint32]($vol*65535);[AudioHelper]::waveOutSetVolume([IntPtr]::Zero,$v+($v*0x10000))"
        )
        subprocess.Popen(["powershell", "-Command", ps], shell=False)
    elif SISTEMA == "Darwin":
        subprocess.Popen(["osascript", "-e", f"set volume output volume {vol}"], shell=False)
    else:
        subprocess.Popen(["amixer", "set", "Master", f"{vol}%"], stdout=subprocess.DEVNULL)
    return {"ok": True, "msg": f"🔊 Volume: {vol}%"}

def _cmd_mute() -> dict:
    if SISTEMA == "Windows":
        ps = (
            "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
            "public class Mute{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte b,byte s,int f,int e);}';"
            "[Mute]::keybd_event(0xAD,0,0,0);[Mute]::keybd_event(0xAD,0,2,0)"
        )
        subprocess.Popen(["powershell", "-Command", ps], shell=False)
    elif SISTEMA == "Darwin":
        subprocess.Popen(["osascript", "-e", "set volume output muted not (output muted of (get volume settings))"], shell=False)
    else:
        subprocess.Popen(["amixer", "set", "Master", "toggle"], stdout=subprocess.DEVNULL)
    return {"ok": True, "msg": "🔇 Mute alternado"}

def _cmd_media(param: str) -> dict:
    if SISTEMA == "Windows":
        vk = {"next": "0xB0", "prev": "0xB1", "pause": "0xB3"}.get(param, "0xB3")
        ps = (
            f"Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;"
            f"public class Media{{[DllImport(\"user32.dll\")]public static extern void keybd_event(byte b,byte s,int f,int e);}}';"
            f"[Media]::keybd_event({vk},0,0,0);[Media]::keybd_event({vk},0,2,0)"
        )
        subprocess.Popen(["powershell", "-Command", ps], shell=False)
    elif SISTEMA == "Darwin":
        key_map = {"next": "next track", "prev": "previous track", "pause": "playpause"}
        key = key_map.get(param, "playpause")
        subprocess.Popen(["osascript", "-e", f'tell application "System Events" to key code 0'], shell=False)
    else:
        key_map = {"next": "Next", "prev": "Previous", "pause": "PlayPause"}
        key = key_map.get(param, "PlayPause")
        subprocess.Popen(["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
                          "/org/mpris/MediaPlayer2", f"org.mpris.MediaPlayer2.Player.{key}"],
                         stdout=subprocess.DEVNULL)
    labels = {"next": "⏭️ Próxima", "prev": "⏮️ Anterior", "pause": "⏯️ Play/Pause"}
    return {"ok": True, "msg": labels.get(param, "⏯️ Mídia")}

# ── Dispatcher principal ──────────────────────────────────────────────────────

def executar_comando(tipo: str, param: str = "") -> dict:
    """
    Ponto de entrada único. Recebe tipo e parâmetro,
    despacha para a função correta e retorna dict {ok, msg}.
    """
    try:
        match tipo:
            case "abrir":           return _cmd_abrir(param)
            case "fechar":          return _cmd_fechar(param)
            case "pesquisar":       return _cmd_pesquisar(param)
            case "site":            return _cmd_site(param)
            case "listar":          return _cmd_listar(param)
            case "ler":             return _cmd_ler(param)
            case "criar_arquivo":   return _cmd_criar_arquivo(param)
            case "criar_pasta":     return _cmd_criar_pasta(param)
            case "deletar":         return _cmd_deletar(param)
            case "sistema":         return _cmd_sistema()
            case "hora":            return _cmd_hora()
            case "volume":          return _cmd_volume(param)
            case "mute":            return _cmd_mute()
            case "media":           return _cmd_media(param)
            case _:
                return {"ok": False, "msg": f"❓ Comando desconhecido: {tipo}"}
    except Exception as e:
        return {"ok": False, "msg": f"❌ Erro ao executar '{tipo}': {str(e)}"}