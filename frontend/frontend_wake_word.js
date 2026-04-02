// ═══════════════════════════════════════════════════════════
// WAKE WORD — adicione este bloco no index.html
// Cole logo antes da linha: checkStatus(); setInterval(checkStatus, 15000);
// ═══════════════════════════════════════════════════════════

// ── Wake Word — polling do /wake a cada 1s ────────────────────────────────────
let _wakeAtivo = false;

function tocarSomAtivacao() {
  // Bip suave de ativação usando Web Audio API (sem arquivo externo)
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);

    osc.frequency.setValueAtTime(880, ctx.currentTime);          // Lá5
    osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.08);  // Dó#6
    gain.gain.setValueAtTime(0.18, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);

    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.25);
  } catch { /* silêncio se não suportar */ }
}

async function checkWake() {
  try {
    const res = await fetch(`${API}/wake`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) return;
    const { ativado } = await res.json();

    if (ativado && !_wakeAtivo && !busy) {
      _wakeAtivo = true;
      tocarSomAtivacao();

      // Mostra indicador visual na bolha
      showBubble('🎙️ ouvindo...');
      btnMic.classList.add('recording');

      // Grava o comando por até 5s ou até soltar
      await startRecordingWake();
      _wakeAtivo = false;
    }
  } catch { /* falha silenciosa */ }
}

async function startRecordingWake() {
  // Reutiliza a infraestrutura de gravação já existente
  const stream = await getMicStream();
  if (!stream) return;

  const mimeType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
    .find(m => MediaRecorder.isTypeSupported(m)) || '';

  return new Promise((resolve) => {
    const chunks = [];
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : {});

    rec.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };

    rec.onstop = async () => {
      btnMic.classList.remove('recording');
      btnMic.classList.add('processing');
      showThinking(true, 'transcrevendo');

      const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' });
      const ext  = (rec.mimeType || 'audio/webm').split(';')[0].split('/')[1] || 'webm';
      const fd   = new FormData();
      fd.append('audio', blob, `audio.${ext}`);

      try {
        const res = await fetch(`${API}/transcrever`, {
          method: 'POST', body: fd,
          signal: AbortSignal.timeout(15000),
        });
        showThinking(false);
        btnMic.classList.remove('processing');

        if (res.ok) {
          const { texto } = await res.json();
          if (texto) {
            msgInput.value = texto;
            showBubble(`🎤 "${texto}"`);
            setTimeout(() => sendText(), 200);
          } else {
            showBubble('Não entendi... fala de novo? 😅');
          }
        }
      } catch {
        showThinking(false);
        btnMic.classList.remove('processing');
        showBubble('Erro ao transcrever 😴');
      }
      resolve();
    };

    rec.start(100);

    // Para automaticamente após 5s
    setTimeout(() => {
      if (rec.state !== 'inactive') rec.stop();
    }, 5000);
  });
}

// Inicia o polling a cada 1 segundo
setInterval(checkWake, 1000);
