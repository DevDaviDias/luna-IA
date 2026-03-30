"""
run_standalone.py
Inicia o backend e abre o Chrome com microfone liberado.
Execute: python run_standalone.py
"""
import subprocess, sys, time, os, platform

def main():
    python  = sys.executable
    backend = os.path.join(os.path.dirname(__file__), "backend", "main.py")

    print("🌙 Iniciando Luna v15...")
    proc = subprocess.Popen([python, backend])
    time.sleep(2.5)

    url = "http://127.0.0.1:8000"
    print(f"✅ Abrindo: {url}")
    print("   (microfone liberado automaticamente)\n")
    print("[Ctrl+C para encerrar]\n")

    sistema = platform.system()

    if sistema == "Windows":
        # Abre Chrome com flag que libera microfone em localhost
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        chrome = next((p for p in chrome_paths if os.path.exists(p)), None)

        if chrome:
            subprocess.Popen([
                chrome,
                "--allow-insecure-localhost",
                "--unsafely-treat-insecure-origin-as-secure=http://127.0.0.1:8000",
                "--use-fake-ui-for-media-stream",   # auto-aprova microfone
                "--app=" + url,                      # abre sem barra de endereço
                "--window-size=400,750",
            ])
        else:
            # Fallback: abre navegador padrão
            import webbrowser
            webbrowser.open(url)
            print("⚠️  Chrome não encontrado. Se o mic não funcionar, abra manualmente no Chrome.")

    elif sistema == "Darwin":  # Mac
        subprocess.Popen(["open", "-a", "Google Chrome", url])
    else:  # Linux
        subprocess.Popen(["google-chrome", "--use-fake-ui-for-media-stream", url])

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Encerrando Luna...")
        proc.terminate()

if __name__ == "__main__":
    main()
