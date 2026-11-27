const token = promptToken();
const authHeaders = { "Content-Type": "application/json", "Authorization": `Bearer ${token}` };
const $ = (id) => document.getElementById(id);
const musicTaglines = [
  "Que suene la música",
  "Ritmo para trabajar",
  "Un buen tema cambia el día",
  "Dale play al día",
  "La oficina suena mejor",
  "Modo buena vibra",
  "Hoy se trabaja con ritmo",
  "Melodías entre reuniones",
];
let currentPlayerState = null;
let isSeeking = false;
const progressState = {
  position: 0,
  duration: null,
  updatedAt: Date.now(),
  isPlaying: false,
  trackKey: null,
};

$("deviceName").textContent =
  musicTaglines[Math.floor(Math.random() * musicTaglines.length)];

function promptToken() {
  let value = localStorage.getItem("cmg_access_token");
  if (!value) {
    value = window.prompt("Ingrese el token de acceso:");
    if (value) localStorage.setItem("cmg_access_token", value);
  }
  return value || "";
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove("show"), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...authHeaders, ...(options.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(body.detail || `Error ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

function setConnection(connected) {
  const status = $("connectionStatus");
  status.className = `status ${connected ? "connected" : "disconnected"}`;
  status.innerHTML = `<span></span> ${connected ? "Conectado" : "Desconectado"}`;
  ["previousButton", "playPauseButton", "nextButton", "volumeRange", "progressRange"].forEach((id) => {
    $(id).disabled = !connected;
  });
}

function formatClock(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "--:--";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function drawProgress(position) {
  const duration = progressState.duration;
  const ratio = duration ? Math.min(1, Math.max(0, position / duration)) : 0;
  $("progressRange").value = Math.round(ratio * 1000);
  $("currentTime").textContent = formatClock(position);
  $("durationTime").textContent = formatClock(duration);
  $("progressRange").setAttribute(
    "aria-valuetext",
    `${formatClock(position)} de ${formatClock(duration)}`,
  );
  const bars = $("waveform").children;
  const activeBars = Math.floor(ratio * bars.length);
  Array.from(bars).forEach((bar, index) => {
    bar.classList.toggle("active", index < activeBars);
  });
}

function updateProgress(state) {
  const track = state.current_track;
  const trackKey = track
    ? `${track.id}:${track.title}:${track.artists?.join(",") || ""}`
    : null;
  const trackChanged = Boolean(
    trackKey && progressState.trackKey && trackKey !== progressState.trackKey,
  );
  if (trackKey) progressState.trackKey = trackKey;
  if (trackChanged) isSeeking = false;
  progressState.position = trackChanged
    ? 0
    : Number.isFinite(state.position_seconds)
      ? state.position_seconds
      : 0;
  progressState.duration =
    Number.isFinite(state.duration_seconds) && state.duration_seconds > 0
      ? state.duration_seconds
      : null;
  progressState.updatedAt = Date.now();
  progressState.isPlaying = Boolean(state.is_playing);
  $("waveform").classList.toggle("playing", progressState.isPlaying);
  $("progressRange").disabled = !state.connected || !progressState.duration;
  if (!isSeeking) drawProgress(progressState.position);
}

function renderPlayer(state) {
  currentPlayerState = state;
  setConnection(state.connected);
  updateProgress(state);
  const track = state.current_track;
  $("trackTitle").textContent = track?.title || "Sin informacion";
  $("trackArtist").textContent = track?.artists?.join(", ") || "Estado no disponible";
  const cover = $("cover");
  cover.replaceChildren();
  if (track?.thumbnail_url) {
    const image = document.createElement("img");
    image.src = track.thumbnail_url;
    image.alt = `Caratula de ${track.title}`;
    cover.appendChild(image);
  } else {
    cover.textContent = "♪";
  }
  $("playPauseButton").textContent = state.is_playing ? "❚❚" : "▶";
  if (state.volume != null) $("volumeRange").value = state.volume;
}

async function refreshPlayer() {
  try { renderPlayer(await api("/api/player")); }
  catch (error) { toast(error.message); setConnection(false); }
}

async function command(path) {
  try { renderPlayer(await api(path, { method: "POST" })); }
  catch (error) { toast(error.message); }
}

function duration(seconds) {
  if (seconds == null) return "";
  const value = Math.round(seconds);
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

const waveform = $("waveform");
for (let index = 0; index < 64; index += 1) {
  const bar = document.createElement("span");
  const wave = Math.abs(Math.sin(index * 1.37) * 0.62 + Math.sin(index * 0.31) * 0.38);
  bar.style.height = `${4 + Math.round(wave * 18)}px`;
  bar.style.setProperty("--bar-index", index);
  waveform.appendChild(bar);
}

async function search() {
  const input = $("searchInput");
  try {
    const tracks = await api(`/api/search?q=${encodeURIComponent(input.value)}&limit=20`);
    const container = $("searchResults");
    container.innerHTML = "";
    if (!tracks.length) {
      container.innerHTML = "<p>No se encontraron resultados.</p>";
      return;
    }
    for (const track of tracks) {
      const row = document.createElement("div");
      row.className = "track-row";
      row.innerHTML = `
        ${track.thumbnail_url ? `<img src="${track.thumbnail_url}" alt="">` : `<div class="cover-mini"></div>`}
        <div><strong></strong><small></small></div>
        <div class="row-actions">
          <button data-action="play" title="Reproducir">▶</button>
          <button data-action="queue" title="Agregar">＋</button>
        </div>`;
      row.querySelector("strong").textContent = track.title;
      row.querySelector("small").textContent =
        `${track.artists?.join(", ") || "Artista desconocido"}${track.duration_seconds ? ` · ${duration(track.duration_seconds)}` : ""}`;
      row.querySelector('[data-action="play"]').onclick = () => addQueue(track, true);
      const queueButton = row.querySelector('[data-action="queue"]');
      queueButton.title = "Agregar a Lista para Siguiente";
      queueButton.onclick = () => addQueue(track, false);
      container.appendChild(row);
    }
  } catch (error) { toast(error.message); }
}

async function addQueue(track, playNow) {
  try {
    await api("/api/queue", {
      method: "POST",
      body: JSON.stringify({ track, play_now: playNow }),
    });
    toast(playNow ? "Reproduccion solicitada" : "Agregado a Lista para Siguiente");
  } catch (error) { toast(error.message); }
}

async function refreshQueue() {
  try {
    const items = await api("/api/queue");
    const container = $("queueList");
    container.innerHTML = "";
    if (!items.length) {
      container.innerHTML = "<p>No hay canciones en la lista.</p>";
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "track-row";
      row.innerHTML = `
        ${item.track.thumbnail_url ? `<img src="${item.track.thumbnail_url}" alt="">` : `<div></div>`}
        <div><strong></strong><small></small></div>
        <div class="row-actions"><button title="Quitar">×</button></div>`;
      row.querySelector("strong").textContent = item.track.title;
      row.querySelector("small").textContent = item.track.artists?.join(", ") || "Artista desconocido";
      row.querySelector("button").onclick = async () => {
        try { await api(`/api/queue/${item.queue_id}`, { method: "DELETE" }); }
        catch (error) { toast(error.message); }
      };
      container.appendChild(row);
    });
  } catch (error) { toast(error.message); }
}

$("searchForm").addEventListener("submit", (event) => { event.preventDefault(); search(); });
$("playPauseButton").addEventListener("click", async () => {
  const commandPath = currentPlayerState?.is_playing ? "/api/player/pause" : "/api/player/play";
  await command(commandPath);
});
$("nextButton").onclick = () => command("/api/player/next");
$("previousButton").onclick = () => command("/api/player/previous");
$("volumeRange").onchange = () => api("/api/player/volume", {
  method: "POST",
  body: JSON.stringify({ volume: Number($("volumeRange").value) }),
}).catch((error) => toast(error.message));
$("progressRange").addEventListener("input", () => {
  isSeeking = true;
  if (progressState.duration) {
    drawProgress((Number($("progressRange").value) / 1000) * progressState.duration);
  }
});
$("progressRange").addEventListener("change", async () => {
  const durationSeconds = progressState.duration;
  if (!durationSeconds) {
    isSeeking = false;
    return;
  }
  const positionSeconds = (Number($("progressRange").value) / 1000) * durationSeconds;
  try {
    const state = await api("/api/player/seek", {
      method: "POST",
      body: JSON.stringify({ position_seconds: positionSeconds }),
    });
    isSeeking = false;
    renderPlayer(state);
  } catch (error) {
    isSeeking = false;
    toast(error.message);
    await refreshPlayer();
  } finally {
    isSeeking = false;
  }
});
$("clearQueueButton").onclick = async () => {
  try { await api("/api/queue/clear", { method: "POST" }); }
  catch (error) { toast(error.message); }
};

$("settingsButton").addEventListener("click", async () => {
  try {
    const settings = await api("/api/settings");
    $("mainTabUrl").value = settings.main_tab_url;
    $("saveSettings").disabled = false;
    $("settingsDialog").showModal();
  } catch (error) {
    toast(error.message);
  }
});
$("cancelSettings").onclick = () => $("settingsDialog").close();
$("settingsForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const saveButton = $("saveSettings");
  saveButton.disabled = true;
  try {
    const result = await api("/api/settings/main-tab", {
      method: "PUT",
      body: JSON.stringify({ url: $("mainTabUrl").value }),
    });
    $("mainTabUrl").value = result.main_tab_url;
    $("settingsDialog").close();
    toast(
      result.applied
        ? "Enlace principal guardado y aplicado"
        : "Enlace guardado; reinicia Chrome para aplicar el cambio",
    );
  } catch (error) {
    toast(error.message);
  } finally {
    saveButton.disabled = false;
  }
});

const protocol = location.protocol === "https:" ? "wss:" : "ws:";
const socket = new WebSocket(`${protocol}//${location.host}/ws?token=${encodeURIComponent(token)}`);
socket.onmessage = (message) => {
  const event = JSON.parse(message.data);
  if (event.type === "player.state") renderPlayer(event.data);
  if (event.type === "queue.updated") refreshQueue();
};
socket.onclose = () => setTimeout(() => location.reload(), 3000);

setInterval(() => {
  if (isSeeking) return;
  let position = progressState.position;
  if (progressState.duration && progressState.isPlaying) {
    position += (Date.now() - progressState.updatedAt) / 1000;
  }
  if (progressState.duration) {
    position = Math.min(position, progressState.duration);
    drawProgress(position);
  }
}, 250);

refreshPlayer();
refreshQueue();
