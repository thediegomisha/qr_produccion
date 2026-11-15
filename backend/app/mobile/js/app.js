/* ============================================================
   QR Lector · PWA
   Paridad funcional con la APK Android:
   login, conteo de cajas, lotes, historial, reportes,
   consultas y vigilancia (entrada/salida).
   ============================================================ */

import { api, session, ApiError, refreshSession } from "./api.js";
import * as db from "./db.js";
import { Scanner, ScannerError, parseQrPayload, extractDni } from "./scanner.js";

/* ------------------------------- Iconos ------------------------------- */
const S = 'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const icons = {
  back: `<svg viewBox="0 0 24 24" ${S}><path d="M15 18l-6-6 6-6"/></svg>`,
  more: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="12" cy="19" r="1.8"/></svg>`,
  scan: `<svg viewBox="0 0 24 24" ${S}><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/><path d="M4 12h16"/></svg>`,
  boxes: `<svg viewBox="0 0 24 24" ${S}><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/></svg>`,
  search: `<svg viewBox="0 0 24 24" ${S}><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>`,
  chart: `<svg viewBox="0 0 24 24" ${S}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>`,
  history: `<svg viewBox="0 0 24 24" ${S}><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></svg>`,
  logout: `<svg viewBox="0 0 24 24" ${S}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></svg>`,
  torch: `<svg viewBox="0 0 24 24" ${S}><path d="M9 2h6l-1 6h-4L9 2zM8 8h8v3l-2 3v8h-4v-8l-2-3V8z"/></svg>`,
  send: `<svg viewBox="0 0 24 24" ${S}><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>`,
  clean: `<svg viewBox="0 0 24 24" ${S}><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/><path d="M10 11v5M14 11v5"/></svg>`,
  box: `<svg viewBox="0 0 24 24" ${S}><path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" ${S}><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2v11z"/><circle cx="12" cy="13" r="4"/></svg>`,
  warning: `<svg viewBox="0 0 24 24" ${S}><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>`,
  install: `<svg viewBox="0 0 24 24" ${S}><path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/></svg>`,
  empty: `<svg viewBox="0 0 24 24" ${S}><path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/></svg>`,
  refresh: `<svg viewBox="0 0 24 24" ${S}><path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6"/></svg>`,
};

/* ------------------------------- Estado ------------------------------- */
const app = document.getElementById("app");
const modalRoot = document.getElementById("modal-root");
const toastEl = document.getElementById("toast");

const FEATURES = {
  ROOT: ["CONTEO", "HISTORIAL", "REPORTES", "INGRESO", "CONSULTAS", "LOTE_SET", "LOTE_CLOSE", "LOTE_OPEN"],
  GERENCIA: ["CONTEO", "HISTORIAL", "REPORTES", "INGRESO", "CONSULTAS", "LOTE_SET", "LOTE_CLOSE", "LOTE_OPEN"],
  SUPERVISOR: ["CONTEO", "HISTORIAL", "REPORTES", "LOTE_SET", "LOTE_CLOSE"],
  OPERADOR: ["CONTEO", "HISTORIAL", "LOTE_SET", "REPORTES"],
  VIGILANCIA: ["INGRESO", "CONSULTAS", "REPORTES"],
};

const state = {
  lote: null,
  scanner: null,
  cameraDevice: null,
  cleanup: null,
  vigMode: "ENTRADA",
  vigItems: [],
  vigSeen: new Set(),
};

/* ------------------------------- Helpers ------------------------------ */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function uuid() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function go(route) {
  const next = `#/${route}`;
  if (location.hash === next) render();
  else location.hash = next;
}

function can(feature) {
  return (FEATURES[session.role()] || []).includes(feature);
}

function todayLima() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
}

function fmtDate(value) {
  if (!value) return "—";
  const date = typeof value === "number" ? new Date(value) : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("es-PE", {
    timeZone: "America/Lima", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

function fullName(person) {
  return [person?.nombres, person?.apellido_paterno, person?.apellido_materno]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join(" ");
}

/* ------------------------------- Toast -------------------------------- */
let toastTimer = null;
function toast(message, kind = "", action = null, ms = 2800) {
  clearTimeout(toastTimer);
  toastEl.className = `toast ${kind}`;
  toastEl.innerHTML = `<span>${esc(message)}</span>`;
  if (action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = action.label;
    button.addEventListener("click", () => { toastEl.hidden = true; action.onClick(); });
    toastEl.appendChild(button);
  }
  toastEl.hidden = false;
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, ms);
}

/* ------------------------------- Sonido ------------------------------- */
let audioCtx = null;
function beep(ok = true) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = ok ? "sine" : "square";
    osc.frequency.value = ok ? 880 : 220;
    gain.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(ok ? 0.16 : 0.1, audioCtx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + (ok ? 0.11 : 0.18));
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + (ok ? 0.12 : 0.2));
  } catch { /* audio no disponible */ }
  try { navigator.vibrate?.(ok ? 80 : [60, 50, 60]); } catch { /* sin vibración */ }
}

/* ------------------------------- Sheet -------------------------------- */
function openSheet({ title, body, onMount }) {
  const backdrop = document.createElement("div");
  backdrop.className = "sheet-backdrop";
  backdrop.innerHTML = `
    <div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <div class="grabber"></div>
      <div class="sheet-head">
        <h2>${esc(title)}</h2>
        <button class="icon-btn" data-close aria-label="Cerrar">✕</button>
      </div>
      <div class="sheet-body">${body}</div>
    </div>`;
  modalRoot.appendChild(backdrop);
  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (event) => { if (event.key === "Escape") close(); };
  document.addEventListener("keydown", onKey);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop || event.target.closest("[data-close]")) close();
  });
  if (onMount) onMount(backdrop.querySelector(".sheet-body"), close);
  return { close, body: backdrop.querySelector(".sheet-body") };
}

function confirmDialog(title, message, confirmLabel = "Aceptar", danger = false) {
  return new Promise((resolve) => {
    const sheet = openSheet({
      title,
      body: `
        <p class="muted small">${esc(message)}</p>
        <div class="btn-row mt-14">
          <button class="btn ghost" data-no>Cancelar</button>
          <button class="btn ${danger ? "danger" : "primary"}" data-yes>${esc(confirmLabel)}</button>
        </div>`,
      onMount(body, close) {
        body.querySelector("[data-no]").addEventListener("click", () => { close(); resolve(false); });
        body.querySelector("[data-yes]").addEventListener("click", () => { close(); resolve(true); });
      },
    });
    const backdrop = sheet.body.closest(".sheet-backdrop");
    backdrop.addEventListener("click", (event) => {
      // Solo cuenta el clic sobre el fondo, no sobre la tarjeta.
      if (event.target === backdrop) resolve(false);
    });
  });
}

/* ------------------------------- Lote --------------------------------- */
function loadLote() {
  try { state.lote = JSON.parse(localStorage.getItem("qr.lote") || "null"); }
  catch { state.lote = null; }
}
function saveLote(lote) {
  state.lote = lote;
  try {
    if (lote) localStorage.setItem("qr.lote", JSON.stringify(lote));
    else localStorage.removeItem("qr.lote");
  } catch { /* modo privado */ }
  updateLoteLabels();
}
function loteReady() {
  return Boolean(state.lote?.codigo) && String(state.lote?.estado || "").toUpperCase() !== "CERRADO";
}
function loteText() {
  if (!state.lote?.codigo) return "Sin lote seleccionado";
  return `Lote ${state.lote.codigo} · ${state.lote.estado || "ABIERTO"}`;
}
function updateLoteLabels() {
  document.querySelectorAll("[data-lote-label]").forEach((el) => { el.textContent = loteText(); });
  document.querySelectorAll("[data-lote-chip]").forEach((el) => {
    const ready = loteReady();
    el.className = `chip ${ready ? "ok" : "warn"}`;
    el.innerHTML = `<span class="dot"></span>${esc(state.lote?.codigo || "Sin lote")}${state.lote?.codigo ? ` · ${esc(state.lote.estado || "ABIERTO")}` : ""}`;
  });
}

/* ------------------------------- Sesión local ------------------------- */
function currentSession() {
  let value = "";
  try { value = localStorage.getItem("qr.session") || ""; } catch { /* modo privado */ }
  if (!value) {
    value = uuid();
    try { localStorage.setItem("qr.session", value); } catch { /* modo privado */ }
  }
  return value;
}
function newSession() {
  const value = uuid();
  try { localStorage.setItem("qr.session", value); } catch { /* modo privado */ }
  return value;
}
function deviceId() {
  let value = "";
  try { value = localStorage.getItem("qr.device") || ""; } catch { /* modo privado */ }
  if (!value) {
    value = `pwa-${uuid()}`;
    try { localStorage.setItem("qr.device", value); } catch { /* modo privado */ }
  }
  return value;
}

function handleAuthError(err) {
  if (err instanceof ApiError && err.status === 401) {
    session.clear();
    go("login");
    return true;
  }
  return false;
}

/* ------------------------------- Login -------------------------------- */
function renderLogin() {
  app.innerHTML = `
    <div class="login-wrap">
      <div class="brand">
        <div class="logo">${icons.scan}</div>
        <h1>QR Lector</h1>
        <p>Producción · conteo de cajas y vigilancia</p>
      </div>
      <div class="card login-card">
        <form id="loginForm" novalidate>
          <div id="loginError" class="form-error" hidden></div>
          <div class="field">
            <label for="usuario">Usuario</label>
            <input class="input" id="usuario" name="usuario" autocomplete="username"
                   autocapitalize="none" spellcheck="false" placeholder="Tu usuario" required>
          </div>
          <div class="field">
            <label for="password">Contraseña</label>
            <input class="input" id="password" name="password" type="password"
                   autocomplete="current-password" placeholder="Tu contraseña" required>
          </div>
          <button class="btn primary block" id="loginBtn" type="submit">Iniciar sesión</button>
        </form>
      </div>
      <div class="login-note">
        <strong>Sesión recordada.</strong> La app renueva el acceso automáticamente, así que
        puedes cerrar Safari o dejarla inactiva sin volver a escribir la contraseña.
      </div>
    </div>`;

  const form = document.getElementById("loginForm");
  const errorBox = document.getElementById("loginError");
  const button = document.getElementById("loginBtn");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const usuario = form.usuario.value.trim();
    const password = form.password.value;
    errorBox.hidden = true;
    if (!usuario || !password) {
      errorBox.textContent = "Completa usuario y contraseña.";
      errorBox.hidden = false;
      return;
    }
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span> Ingresando…`;
    try {
      const data = await api.login(usuario, password);
      if (!data?.access_token) throw new Error("Respuesta de login inválida");
      session.save(data);
      newSession();
      saveLote(null);
      toast(`Bienvenido, ${data.usuario || usuario}`, "ok");
      go("menu");
    } catch (err) {
      errorBox.textContent = err?.message || "No se pudo iniciar sesión.";
      errorBox.hidden = false;
      button.disabled = false;
      button.textContent = "Iniciar sesión";
    }
  });
}

/* ------------------------------- Menú --------------------------------- */
function renderMenu() {
  const user = session.user() || "Usuario";
  const name = session.name();
  const role = session.role() || "SIN ROL";
  const initial = (name || user).slice(0, 1).toUpperCase();

  const tiles = [];
  if (can("INGRESO")) {
    tiles.push(tile("blue", "vigilancia", icons.camera, "Ingreso / Vigilancia", "Escanea gafetes y registra entradas y salidas."));
  }
  if (can("CONTEO")) {
    tiles.push(tile("", "conteo", icons.boxes, "Conteo de cajas", "Escanea etiquetas QR y envía el lote."));
  }
  if (can("CONSULTAS")) {
    tiles.push(tile("violet", "consultas", icons.search, "Consultas", "Busca una persona por DNI."));
  }
  if (can("REPORTES")) {
    tiles.push(tile("", "reportes", icons.chart, "Reportes", "Totales por DNI, empacador y seleccionador."));
  }
  if (can("HISTORIAL")) {
    tiles.push(tile("blue", "historial", icons.history, "Historial", "Pendientes, enviados y duplicados."));
  }

  app.innerHTML = `
    <header class="topbar">
      <div class="title">
        <h1>QR Lector</h1>
        <small>Producción</small>
      </div>
      <button class="icon-btn" id="btnLogout" aria-label="Cerrar sesión">${icons.logout}</button>
    </header>
    <main class="content">
      <div class="hero">
        <div class="avatar">${esc(initial)}</div>
        <div class="who">
          <h1>${esc(name || user)}</h1>
          <p>${name ? `@${esc(user)} · ` : ""}${esc(role)}</p>
        </div>
      </div>

      <div class="lote-bar">
        <div style="min-width:0">
          <div class="muted" style="font-size:.68rem;text-transform:uppercase;letter-spacing:.08em">Lote activo</div>
          <div class="lote-name" data-lote-label>${esc(loteText())}</div>
        </div>
        ${can("LOTE_SET") ? `<button class="btn small" id="btnLote">${icons.box} Cambiar</button>` : ""}
      </div>

      <div class="tile-grid">${tiles.length ? tiles.join("") : `<div class="card muted small">Tu usuario no tiene funciones asignadas. Consulta con el administrador.</div>`}</div>

      ${installHint()}

      <p class="muted small" style="text-align:center;margin-top:22px">
        v1.0 · PWA para iPhone y Android
      </p>
    </main>`;

  document.getElementById("btnLogout").addEventListener("click", async () => {
    if (await confirmDialog("Cerrar sesión", "¿Deseas cerrar sesión en este dispositivo?", "Salir", true)) {
      session.clear();
      saveLote(null);
      try { localStorage.removeItem("qr.session"); } catch { /* modo privado */ }
      go("login");
    }
  });
  document.getElementById("btnLote")?.addEventListener("click", openLoteSheet);
  updateLoteLabels();
}

function tile(kind, route, icon, title, subtitle) {
  return `
    <button class="tile ${kind}" data-nav="${route}">
      <span class="tile-icon">${icon}</span>
      <strong>${esc(title)}</strong>
      <span>${esc(subtitle)}</span>
    </button>`;
}

function installHint() {
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone;
  if (standalone) return "";
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const text = isIOS
    ? "Para usar la cámara y abrirla como app: toca <strong>Compartir</strong> en Safari y elige <strong>Añadir a pantalla de inicio</strong>."
    : "Puedes instalarla desde el menú del navegador: <strong>Instalar app</strong> o <strong>Añadir a pantalla de inicio</strong>.";
  return `<div class="install-hint mt-14">${icons.install}<div>${text}</div></div>`;
}

/* ------------------------------- Lote sheet --------------------------- */
async function openLoteSheet() {
  if (!can("LOTE_SET")) return;
  const active = state.lote;
  const body = `
    <div class="field">
      <label>Lote activo</label>
      <div class="chip ${loteReady() ? "ok" : "warn"}" data-lote-chip><span class="dot"></span></div>
    </div>
    <div class="option-list" id="loteList"><div class="empty">Cargando lotes…</div></div>
    <div class="field">
      <label for="newLote">Crear o usar un código</label>
      <div class="input-group">
        <input class="input" id="newLote" placeholder="Ej. 1234-2026" autocapitalize="characters" spellcheck="false">
        <button class="btn primary" id="addLote">Usar</button>
      </div>
    </div>
    ${active?.codigo ? `
      <div class="btn-row">
        ${can("LOTE_CLOSE") ? `<button class="btn danger" id="closeLote">Cerrar lote</button>` : ""}
        ${session.role() === "ROOT" ? `<button class="btn" id="openLote">Reabrir</button>` : ""}
      </div>` : ""}`;

  const sheet = openSheet({ title: "Seleccionar lote", body });
  updateLoteLabels();

  const list = sheet.body.querySelector("#loteList");

  const paint = (items) => {
    if (!items.length) {
      list.innerHTML = `<div class="empty">No hay lotes todavía. Crea uno abajo.</div>`;
      return;
    }
    list.innerHTML = items.map((lote) => {
      const estado = String(lote.estado || "ABIERTO").toUpperCase();
      const isActive = lote.codigo === state.lote?.codigo;
      return `
        <button class="option ${isActive ? "active" : ""}" data-code="${esc(lote.codigo)}" data-state="${esc(estado)}">
          <span class="code">${esc(lote.codigo)}</span>
          <span class="state ${estado.toLowerCase()}">${esc(estado)}</span>
          <span class="muted small">${Number(lote.total_lecturas) || 0}</span>
        </button>`;
    }).join("");
  };

  try {
    const data = await api.listLotes({ limit: 200 });
    paint(data?.items || []);
  } catch (err) {
    if (!handleAuthError(err)) {
      list.innerHTML = `<div class="empty">No se pudieron cargar los lotes: ${esc(err.message)}</div>`;
    }
  }

  list.addEventListener("click", (event) => {
    const option = event.target.closest("[data-code]");
    if (!option) return;
    saveLote({ codigo: option.dataset.code, estado: option.dataset.state });
    sheet.close();
    toast(`Lote ${option.dataset.code} seleccionado`, "ok");
    render();
  });

  const add = async () => {
    const input = sheet.body.querySelector("#newLote");
    const codigo = input.value.trim().toUpperCase();
    if (!codigo) { toast("Escribe un código de lote", "warn"); return; }
    const button = sheet.body.querySelector("#addLote");
    button.disabled = true;
    try {
      const lote = await api.ensureLote(codigo);
      saveLote({ codigo: lote.codigo, estado: lote.estado });
      sheet.close();
      toast(`Lote ${lote.codigo} listo`, "ok");
      render();
    } catch (err) {
      if (!handleAuthError(err)) toast(err.message, "error");
      button.disabled = false;
    }
  };
  sheet.body.querySelector("#addLote").addEventListener("click", add);
  sheet.body.querySelector("#newLote").addEventListener("keydown", (event) => {
    if (event.key === "Enter") { event.preventDefault(); add(); }
  });

  const closeBtn = sheet.body.querySelector("#closeLote");
  if (closeBtn) {
    closeBtn.addEventListener("click", async () => {
      if (!state.lote?.codigo) return;
      if (!(await confirmDialog("Cerrar lote", `El lote ${state.lote.codigo} dejará de aceptar lecturas. ¿Continuar?`, "Cerrar lote", true))) return;
      try {
        const lote = await api.closeLote(state.lote.codigo);
        saveLote({ codigo: lote.codigo, estado: lote.estado });
        sheet.close();
        toast(`Lote ${lote.codigo} cerrado`, "ok");
        render();
      } catch (err) {
        if (!handleAuthError(err)) toast(err.message, "error");
      }
    });
  }

  const openBtn = sheet.body.querySelector("#openLote");
  if (openBtn) {
    openBtn.addEventListener("click", async () => {
      if (!state.lote?.codigo) return;
      try {
        const lote = await api.openLote(state.lote.codigo);
        saveLote({ codigo: lote.codigo, estado: lote.estado });
        sheet.close();
        toast(`Lote ${lote.codigo} reabierto`, "ok");
        render();
      } catch (err) {
        if (!handleAuthError(err)) toast(err.message, "error");
      }
    });
  }
}

/* ------------------------------- Cámara ------------------------------- */
function stopScanner() {
  try { state.scanner?.stop(); } catch { /* ya detenido */ }
  state.scanner = null;
}

async function startCamera(onText) {
  const video = document.getElementById("cam");
  const errorBox = document.getElementById("camError");
  if (!video || !errorBox) return;
  errorBox.hidden = true;

  const scanner = new Scanner(video, {
    deviceId: state.cameraDevice,
    onResult: (text) => { Promise.resolve(onText(text)).catch(() => {}); },
    formats: location.hash.includes("vigilancia") ? ["Code39", "QRCode"] : ["QRCode"],
    onError: (error) => {
      if (state.scanner === scanner) {
        scanner.stop();
        showCameraError(error);
      }
    },
  });
  state.scanner = scanner;

  try {
    await scanner.start();
  } catch (err) {
    if (state.scanner !== scanner) return;
    showCameraError(err);
    return;
  }
  if (state.scanner !== scanner) return;

  // iPhone can expose multiple rear lenses. Allow choosing a sharper lens
  // rather than forcing whichever "environment" camera Safari selected.
  try {
    const devices = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === "videoinput");
    if (state.scanner !== scanner) return;
    video.parentElement.querySelector("#cameraSelect")?.remove();
    if (devices.length > 1) {
      const select = document.createElement("select");
      select.id = "cameraSelect";
      select.className = "camera-select";
      select.setAttribute("aria-label", "Cámara de escaneo");
      for (const [index, device] of devices.entries()) {
        select.add(new Option(device.label || `Cámara ${index + 1}`, device.deviceId));
      }
      select.value = scanner.track?.getSettings?.().deviceId || state.cameraDevice || devices[0].deviceId;
      select.addEventListener("change", () => {
        state.cameraDevice = select.value;
        stopScanner();
        startCamera(onText);
      });
      video.parentElement.append(select);
    }
  } catch { /* camera enumeration is optional */ }

  const torch = document.getElementById("torch");
  if (torch) {
    torch.hidden = true;
    torch.classList.remove("on");
    torch.onclick = null;
  }
  if (torch && await scanner.hasTorch()) {
    torch.hidden = false;
    torch.onclick = async () => {
      const on = !torch.classList.contains("on");
      const applied = await scanner.setTorch(on);
      if (applied) torch.classList.add("on");
      else if (!on) torch.classList.remove("on");
    };
  }
}

function showCameraError(err) {
  const errorBox = document.getElementById("camError");
  if (!errorBox) return;
  const title = err instanceof ScannerError && err.code === "https"
    ? "Se necesita HTTPS"
    : "No se pudo abrir la cámara";
  errorBox.innerHTML = `
    ${icons.warning}
    <h3>${esc(title)}</h3>
    <p>${esc(err?.message || "Revisa los permisos de cámara del navegador.")}</p>
    <button class="btn small" id="retryCam">${icons.refresh} Reintentar</button>`;
  errorBox.hidden = false;
  const retry = document.getElementById("retryCam");
  if (retry) {
    retry.addEventListener("click", () => {
      stopScanner();
      const video = document.getElementById("cam");
      if (video) startCamera(window.__lastScanHandler);
    });
  }
}

function setEstado(text, kind = "") {
  const el = document.getElementById("estado");
  if (!el) return;
  el.textContent = text;
  el.className = `estado ${kind}`;
}

function flashFrame() {
  const frame = document.getElementById("frame");
  if (!frame) return;
  frame.classList.remove("ok");
  void frame.offsetWidth;
  frame.classList.add("ok");
}

/* ------------------------------- Conteo ------------------------------- */
function renderConteo() {
  if (!can("CONTEO")) { go("menu"); return; }

  app.innerHTML = `
    <div class="scanner-view">
      <header class="scanner-top">
        <button class="icon-btn" data-nav="menu" aria-label="Volver">${icons.back}</button>
        <div class="title">
          <h1>Conteo de cajas</h1>
          <small data-lote-label>${esc(loteText())}</small>
        </div>
        <button class="icon-btn" id="btnMore" aria-label="Más opciones">${icons.more}</button>
      </header>

      <div class="camera-wrap">
        <video id="cam" playsinline muted autoplay></video>
        <div class="camera-shade"></div>
        <div class="scan-frame" id="frame"><span></span></div>
        <div class="scan-line"></div>
        <div class="cam-error" id="camError" hidden></div>
        <button class="torch-btn" id="torch" hidden aria-label="Linterna">${icons.torch}</button>
      </div>

      <section class="scan-status">
        <div class="last">
          <div class="label">Último DNI</div>
          <div class="value" id="lastDni">—</div>
        </div>
        <div style="text-align:right">
          <div class="estado" id="estado">Listo</div>
          <div class="total" id="total">TOTAL: 0</div>
        </div>
      </section>

      <section class="scan-actions">
        <button class="btn" id="btnClear">${icons.clean}<span>Limpiar</span></button>
        <button class="btn primary" id="btnSend">${icons.send}<span>Enviar</span></button>
        <button class="btn" id="btnLote">${icons.box}<span>Lote</span></button>
      </section>

      <section class="grid-wrap">
        <div class="dni-grid" id="grid"></div>
      </section>
    </div>`;

  updateLoteLabels();
  refreshGrid();

  document.getElementById("btnClear").addEventListener("click", async () => {
    if (!(await confirmDialog("Nueva sesión", "Se limpiará la rejilla y el total actual. Los pendientes conservan su lote y sesión originales.", "Empezar", false))) return;
    newSession();
    document.getElementById("lastDni").textContent = "—";
    setEstado("Nueva sesión", "ok");
    refreshGrid();
  });

  document.getElementById("btnSend").addEventListener("click", sendBatch);
  document.getElementById("btnLote").addEventListener("click", openLoteSheet);
  document.getElementById("btnMore").addEventListener("click", openScannerMenu);

  if (!loteReady()) {
    toast("Selecciona un lote para empezar", "warn");
    openLoteSheet();
  }

  window.__lastScanHandler = handleConteoScan;
  startCamera(handleConteoScan);
}

async function refreshGrid() {
  const grid = document.getElementById("grid");
  if (!grid) return;
  const { total, items } = await db.countsForSession(currentSession());
  const totalEl = document.getElementById("total");
  if (totalEl) totalEl.textContent = `TOTAL: ${total}`;
  grid.innerHTML = items.length
    ? items.map((item) => `
        <div class="dni-cell">
          <span class="dni">${esc(item.dni)}</span>
          <span class="qty">x${item.qty}</span>
        </div>`).join("")
    : `<div class="grid-empty" style="grid-column:1/-1">Aún no hay lecturas en esta sesión.</div>`;
}

async function handleConteoScan(raw) {
  const payload = parseQrPayload(raw);
  if (!payload) {
    setEstado("Código inválido", "error");
    beep(false);
    return;
  }
  if (!payload.t || !/^\d{8}$/.test(payload.dni)) {
    setEstado("Token/DNI inválido", "error");
    beep(false);
    return;
  }
  if (!loteReady()) {
    setEstado("Falta LOTE", "error");
    toast("Selecciona un lote antes de escanear", "warn");
    openLoteSheet();
    return;
  }

  const inserted = await db.addScan({
    token: payload.t,
    dni: payload.dni,
    user_id: session.user(),
    scanned_at: new Date().toISOString(),
    created_at: Date.now(),
    status: db.STATUS.PENDING,
    batch_uuid: null,
    session_uuid: currentSession(),
    lote_codigo: state.lote.codigo,
    qr_id: payload.id,
    producto: payload.producto,
    version: payload.version,
    firma: payload.firma,
    raw: payload.raw,
  });

  const last = document.getElementById("lastDni");
  if (last) last.textContent = payload.dni;

  if (inserted) {
    setEstado("OK", "ok");
    beep(true);
    flashFrame();
  } else {
    setEstado("DUPLICADO", "dup");
    beep(false);
  }
  refreshGrid();
}

let sending = false;
async function sendBatch() {
  if (sending) return;
  sending = true;
  try {
    if (navigator.locks) {
      await navigator.locks.request("qrlector-sync", () => sendBatchLocked());
    } else {
      await sendBatchLocked();
    }
  } finally {
    sending = false;
  }
}

async function sendBatchLocked() {
  if (!loteReady()) {
    toast("Selecciona un lote antes de enviar", "warn");
    openLoteSheet();
    return;
  }
  const lote = state.lote.codigo;
  const button = document.getElementById("btnSend");
  if (button) button.disabled = true;

  let prepared = { batchUuid: null, rows: [] };
  try {
    await db.recoverInterruptedBatches();
    prepared = await db.prepareContext(session.user(), lote);
    if (!prepared.rows.length) {
      toast("No hay pendientes para enviar");
      setEstado("Sin pendientes", "ok");
      return;
    }

    setEstado(`Enviando (${prepared.rows.length})…`, "");
    const payload = {
      batch_uuid: prepared.batchUuid,
      session_uuid: prepared.rows[0].session_uuid,
      device_id: deviceId(),
      shift_label: null,
      lote_codigo: lote,
      scans: prepared.rows.map((row) => ({
        token: row.token,
        dni: row.dni,
        scanned_at: row.scanned_at,
        raw: row.raw || {},
      })),
    };

    const res = await api.postBatch(payload);
    if (res?.batch_uuid !== prepared.batchUuid) {
      throw new Error("El servidor confirmó otro envío");
    }
    const accepted = Number(res.accepted_count);
    const duplicates = Number(res.duplicate_count);
    if (!Number.isFinite(accepted) || !Number.isFinite(duplicates)
        || accepted < 0 || duplicates < 0
        || accepted + duplicates !== prepared.rows.length) {
      throw new Error("Respuesta de envío incompleta; se conservan los pendientes");
    }

    await db.completeBatch(prepared.batchUuid, lote, accepted, duplicates);
    if (duplicates > 0) {
      setEstado(`ENVIADO: ${accepted} | DUP: ${duplicates}`, "dup");
      toast(`Enviado. Aceptados: ${accepted} · Duplicados: ${duplicates}`, "warn", null, 4000);
    } else {
      setEstado(`ENVIADO OK (${accepted})`, "ok");
      toast(`Enviado OK (${accepted})`, "ok");
    }
    beep(true);
  } catch (err) {
    await db.rollbackBatch(prepared.batchUuid);
    if (err instanceof ApiError && err.status === 409) {
      if (state.lote?.codigo === lote) saveLote({ codigo: lote, estado: "CERRADO" });
      setEstado("LOTE CERRADO (pendiente)", "error");
      toast("El lote está cerrado. Cambia de lote o pide reabrirlo.", "error", null, 4200);
    } else if (!handleAuthError(err)) {
      setEstado("Error al enviar (pendiente)", "error");
      toast(err?.message || "No se pudo enviar", "error", null, 3800);
    }
  } finally {
    if (button) button.disabled = false;
    refreshGrid();
  }
}

function openScannerMenu() {
  const body = `
    <div class="list">
      ${can("LOTE_SET") ? `<button class="option" data-act="lote"><span class="code">Seleccionar lote</span><span class="muted">›</span></button>` : ""}
      ${can("LOTE_CLOSE") ? `<button class="option" data-act="close"><span class="code">Cerrar lote activo</span><span class="muted">›</span></button>` : ""}
      ${session.role() === "ROOT" ? `<button class="option" data-act="open"><span class="code">Reabrir lote activo</span><span class="muted">›</span></button>` : ""}
      ${can("HISTORIAL") ? `<button class="option" data-act="history"><span class="code">Historial</span><span class="muted">›</span></button>` : ""}
    </div>`;
  const sheet = openSheet({ title: "Opciones del escáner", body });
  sheet.body.addEventListener("click", async (event) => {
    const option = event.target.closest("[data-act]");
    if (!option) return;
    const action = option.dataset.act;
    sheet.close();
    if (action === "lote") return openLoteSheet();
    if (action === "history") return go("historial");
    if (!state.lote?.codigo) return toast("No hay lote activo", "warn");
    if (action === "close") {
      if (!(await confirmDialog("Cerrar lote", `El lote ${state.lote.codigo} dejará de aceptar lecturas.`, "Cerrar lote", true))) return;
      try {
        const lote = await api.closeLote(state.lote.codigo);
        saveLote({ codigo: lote.codigo, estado: lote.estado });
        toast(`Lote ${lote.codigo} cerrado`, "ok");
        render();
      } catch (err) { if (!handleAuthError(err)) toast(err.message, "error"); }
    }
    if (action === "open") {
      try {
        const lote = await api.openLote(state.lote.codigo);
        saveLote({ codigo: lote.codigo, estado: lote.estado });
        toast(`Lote ${lote.codigo} reabierto`, "ok");
        render();
      } catch (err) { if (!handleAuthError(err)) toast(err.message, "error"); }
    }
  });
}

/* ------------------------------- Historial ---------------------------- */
function renderHistorial() {
  if (!can("HISTORIAL")) { go("menu"); return; }
  let tab = 0;

  app.innerHTML = `
    <header class="topbar">
      <button class="icon-btn" data-nav="menu" aria-label="Volver">${icons.back}</button>
      <div class="title"><h1>Historial</h1><small>Cola local de este dispositivo</small></div>
      ${session.role() === "ROOT" ? `<button class="icon-btn" id="btnWipe" aria-label="Borrar historial">${icons.clean}</button>` : ""}
    </header>
    <main class="content">
      <div class="tabs" id="tabs">
        <button class="active" data-tab="0">Pendientes</button>
        <button data-tab="1">Enviados</button>
        <button data-tab="2">Duplicados</button>
      </div>
      <div id="list" class="list"><div class="empty">Cargando…</div></div>
    </main>`;

  const list = document.getElementById("list");
  const tabs = document.getElementById("tabs");

  const paint = async () => {
    list.innerHTML = `<div class="empty">Cargando…</div>`;
    const user = session.user();
    try {
      if (tab === 0) {
        const rows = await db.pendingForUser(user);
        list.innerHTML = rows.length ? rows.map((row) => `
          <div class="list-item">
            <div class="main">
              <strong>${esc(row.dni)}</strong>
              <small>Lote ${esc(row.lote_codigo || "—")} · ${esc(fmtDate(row.scanned_at))}</small>
            </div>
            <div class="side"><span class="badge badge-pending">${row.status === db.STATUS.QUEUED ? "ENVIANDO" : "PENDIENTE"}</span></div>
          </div>`).join("") : emptyBox("No hay lecturas pendientes.");
      } else if (tab === 1) {
        const rows = await db.sentForUser(user);
        list.innerHTML = rows.length ? rows.map((row) => `
          <div class="list-item">
            <div class="main">
              <strong>${esc(row.dni)}</strong>
              <small>Lote ${esc(row.lote_codigo || "—")} · ${esc(fmtDate(row.scanned_at))}</small>
            </div>
            <div class="side"><span class="badge badge-ok">ENVIADO</span></div>
          </div>`).join("") : emptyBox("Todavía no hay envíos.");
      } else {
        const rows = await db.duplicateReceipts(user);
        list.innerHTML = rows.length ? rows.map((row) => `
          <div class="list-item">
            <div class="main">
              <strong>${esc(row.lote_codigo || "—")}</strong>
              <small>${esc(fmtDate(Number(row.processed_at_ms)))} · aceptados ${Number(row.accepted) || 0}</small>
            </div>
            <div class="side"><span class="badge badge-dup">${Number(row.duplicates) || 0} dup.</span></div>
          </div>`).join("") : emptyBox("No hay envíos con duplicados.");
      }
    } catch (err) {
      list.innerHTML = emptyBox(`No se pudo leer la base local: ${err.message}`);
    }
  };

  tabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-tab]");
    if (!button) return;
    tab = Number(button.dataset.tab);
    tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === button));
    paint();
  });

  const wipe = document.getElementById("btnWipe");
  if (wipe) {
    wipe.addEventListener("click", async () => {
      if (!(await confirmDialog("Borrar historial", "Se borrarán TODAS las lecturas guardadas en este dispositivo (incluidos pendientes). Esta acción no se puede deshacer.", "Borrar todo", true))) return;
      await db.clearHistory();
      toast("Historial borrado", "ok");
      paint();
    });
  }

  paint();
}

function emptyBox(message) {
  return `<div class="empty">${icons.empty}<div>${esc(message)}</div></div>`;
}

/* ------------------------------- Reportes ----------------------------- */
async function renderReportes() {
  if (!can("REPORTES")) { go("menu"); return; }
  const today = todayLima();

  app.innerHTML = `
    <header class="topbar">
      <button class="icon-btn" data-nav="menu" aria-label="Volver">${icons.back}</button>
      <div class="title"><h1>Reportes</h1><small>Resumen por DNI</small></div>
    </header>
    <main class="content">
      <div class="card">
        <div class="field">
          <label for="loteSel">Lote (obligatorio)</label>
          <select class="select" id="loteSel"><option value="">Cargando lotes…</option></select>
        </div>
        <div class="field">
          <label for="producto">Producto (opcional)</label>
          <input class="input" id="producto" placeholder="Ej. UVA" autocapitalize="characters" spellcheck="false">
        </div>
        <div class="btn-row">
          <div class="field" style="flex:1">
            <label for="desde">Desde</label>
            <input class="input" type="date" id="desde" value="${today}">
          </div>
          <div class="field" style="flex:1">
            <label for="hasta">Hasta</label>
            <input class="input" type="date" id="hasta" value="${today}">
          </div>
        </div>
        <button class="btn primary block" id="btnConsultar">Consultar</button>
      </div>
      <div id="reportResult" class="mt-14"></div>
      <p id="reportLive" class="muted small mt-8" role="status">Producción consolidada de todos los operadores. Refresco cada 10 s tras consultar.</p>
    </main>`;

  const select = document.getElementById("loteSel");
  const result = document.getElementById("reportResult");
  const button = document.getElementById("btnConsultar");
  const live = document.getElementById("reportLive");
  let disposed = false;
  let inFlight = false;
  let activeFilters = null;
  const update = async (manual = false) => {
    if (disposed || inFlight || !activeFilters) return;
    inFlight = true;
    const filters = { ...activeFilters };
    if (manual) {
      button.disabled = true;
      button.innerHTML = `<span class="spinner"></span> Consultando…`;
    }
    try {
      const data = await api.dniSummary(filters);
      if (disposed) return;
      result.innerHTML = renderReport(data);
      live.textContent = `Todos los operadores · Actualizado ${new Date().toLocaleTimeString("es-PE")} · Refresco cada 10 s`;
    } catch (err) {
      if (disposed) return;
      if (!handleAuthError(err)) {
        live.textContent = "No se pudo actualizar. Se reintentará en 10 s; los datos anteriores pueden estar desactualizados.";
        if (manual) toast(err.message, "error");
      }
    } finally {
      inFlight = false;
      if (!disposed) {
        button.disabled = false;
        button.textContent = "Consultar";
      }
    }
  };
  const timer = setInterval(() => {
    if (document.visibilityState === "visible") update();
  }, 10000);
  const onVisible = () => { if (document.visibilityState === "visible") update(); };
  document.addEventListener("visibilitychange", onVisible);
  state.cleanup = () => {
    disposed = true;
    clearInterval(timer);
    document.removeEventListener("visibilitychange", onVisible);
  };

  try {
    const data = await api.listLotes({ limit: 200 });
    if (disposed) return;
    const items = data?.items || [];
    select.innerHTML = `<option value="">SELECCIONE LOTE…</option>` + items.map((lote) => {
      const estado = String(lote.estado || "ABIERTO").toUpperCase();
      return `<option value="${esc(lote.codigo)}">${esc(lote.codigo)}${estado === "CERRADO" ? " (CERRADO)" : ""}</option>`;
    }).join("");
    if (state.lote?.codigo && items.some((l) => l.codigo === state.lote.codigo)) {
      select.value = state.lote.codigo;
    }
  } catch (err) {
    if (!handleAuthError(err)) {
      select.innerHTML = `<option value="">No se pudieron cargar los lotes</option>`;
      toast(err.message, "error");
    }
  }

  button.addEventListener("click", () => {
    const lote = select.value.trim();
    if (!lote) { toast("Selecciona un lote antes de consultar", "warn"); return; }
    const desde = document.getElementById("desde").value;
    const hasta = document.getElementById("hasta").value;
    if (!desde || !hasta) { toast("Indica ambas fechas", "warn"); return; }
    if (hasta < desde) { toast("La fecha final debe ser mayor o igual a la inicial", "warn"); return; }

    activeFilters = {
        lote_codigo: lote,
        producto: document.getElementById("producto").value.trim() || undefined,
        date_from: desde,
        date_to: hasta,
    };
    update(true);
  });
}

function renderReport(data) {
  const totals = data?.totals || {};
  const rows = data?.rows || [];
  const total = Number(totals.total_lecturas) || 0;
  const emp = Number(totals.emp_lecturas) || 0;
  const sel = Number(totals.sel_lecturas) || 0;

  const table = rows.length ? `
    <div class="table-wrap">
      <table class="report">
        <thead>
          <tr><th>DNI</th><th>Persona</th><th>Emp.</th><th>Sel.</th><th>Total</th></tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td class="dni">${esc(row.dni)}</td>
              <td class="persona" title="${esc(row.persona)}">${esc(row.persona)}</td>
              <td class="num">${Number(row.empacador) || 0}</td>
              <td class="num">${Number(row.seleccionador) || 0}</td>
              <td class="num">${Number(row.total) || 0}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>` : emptyBox("No hay lecturas para los filtros elegidos.");

  return `
    <div class="stat-grid">
      <div class="stat total"><span class="num">${total}</span><span class="lbl">Total</span></div>
      <div class="stat emp"><span class="num">${emp}</span><span class="lbl">Empacador</span></div>
      <div class="stat sel"><span class="num">${sel}</span><span class="lbl">Seleccionador</span></div>
    </div>
    ${table}`;
}

/* ------------------------------- Consultas ---------------------------- */
function renderConsultas() {
  if (!can("CONSULTAS")) { go("menu"); return; }
  app.innerHTML = `
    <header class="topbar">
      <button class="icon-btn" data-nav="menu" aria-label="Volver">${icons.back}</button>
      <div class="title"><h1>Consultas</h1><small>Buscar persona por DNI</small></div>
    </header>
    <main class="content">
      <div class="card">
        <div class="field">
          <label for="dni">DNI de 8 dígitos</label>
          <div class="input-group">
            <input class="input" id="dni" inputmode="numeric" pattern="[0-9]*" maxlength="8"
                   placeholder="12345678" autocomplete="off">
            <button class="btn primary" id="btnBuscar">${icons.search} Buscar</button>
          </div>
        </div>
      </div>
      <div id="consultaResult" class="mt-14"></div>
    </main>`;

  const input = document.getElementById("dni");
  const result = document.getElementById("consultaResult");
  const button = document.getElementById("btnBuscar");

  const search = async () => {
    const dni = input.value.replace(/\D/g, "");
    if (!/^\d{8}$/.test(dni)) { toast("DNI inválido", "warn"); return; }
    button.disabled = true;
    result.innerHTML = `<div class="card"><span class="spinner"></span> Consultando…</div>`;
    try {
      const person = await api.persona(dni);
      if (person?.found) {
        result.innerHTML = `
          <div class="person-card">
            <span class="dni">${esc(person.dni || dni)}</span>
            <span class="name">${esc(fullName(person) || "Sin nombre")}</span>
          </div>`;
      } else {
        result.innerHTML = `
          <div class="person-card missing">
            <span class="dni">${esc(dni)}</span>
            <span class="name">Persona no encontrada</span>
            <span class="muted small">${person?.offline ? "El servicio externo no está disponible." : "No figura en la base ni en RENIEC."}</span>
          </div>`;
      }
    } catch (err) {
      if (!handleAuthError(err)) {
        result.innerHTML = `<div class="person-card missing"><span class="name">No se pudo consultar</span><span class="muted small">${esc(err.message)}</span></div>`;
      }
    } finally {
      button.disabled = false;
    }
  };

  button.addEventListener("click", search);
  input.addEventListener("keydown", (event) => { if (event.key === "Enter") search(); });
  input.addEventListener("input", () => { input.value = input.value.replace(/\D/g, "").slice(0, 8); });
  input.focus();
}

/* ------------------------------- Vigilancia --------------------------- */
function renderVigilancia() {
  if (!can("INGRESO")) { go("menu"); return; }
  state.vigItems = [];
  state.vigSeen = new Set();
  state.vigMode = "ENTRADA";

  app.innerHTML = `
    <div class="scanner-view">
      <header class="scanner-top">
        <button class="icon-btn" data-nav="menu" aria-label="Volver">${icons.back}</button>
        <div class="title"><h1>Ingreso / Vigilancia</h1><small>Escanea el gafete (Code 39)</small></div>
        <button class="btn small" id="btnMode">ENTRADA</button>
      </header>

      <div class="camera-wrap">
        <video id="cam" playsinline muted autoplay></video>
        <div class="camera-shade"></div>
        <div class="scan-frame" id="frame"><span></span></div>
        <div class="scan-line"></div>
        <div class="cam-error" id="camError" hidden></div>
        <button class="torch-btn" id="torch" hidden aria-label="Linterna">${icons.torch}</button>
      </div>

      <section class="scan-status">
        <div class="last">
          <div class="label">Último DNI</div>
          <div class="value" id="lastDni">—</div>
        </div>
        <div style="text-align:right">
          <div class="estado" id="estado">Modo: ENTRADA</div>
          <div class="total" id="total">LEÍDOS: 0</div>
        </div>
      </section>

      <section class="grid-wrap">
        <div class="list" id="vigList"></div>
      </section>
    </div>`;

  const modeButton = document.getElementById("btnMode");
  modeButton.addEventListener("click", () => {
    state.vigMode = state.vigMode === "ENTRADA" ? "SALIDA" : "ENTRADA";
    modeButton.textContent = state.vigMode;
    modeButton.classList.toggle("blue", state.vigMode === "SALIDA");
    setEstado(`Modo: ${state.vigMode}`, "");
  });

  paintVigilancia();
  document.getElementById("vigList").addEventListener("click", (event) => {
    const target = event.target.closest("[data-retry]");
    if (!target) return;
    const item = state.vigItems[Number(target.dataset.retry)];
    if (item) openPersonForm(item.dni, item.tipo, item);
  });
  window.__lastScanHandler = handleVigilanciaScan;
  startCamera(handleVigilanciaScan);
}

function paintVigilancia() {
  const list = document.getElementById("vigList");
  const total = document.getElementById("total");
  if (total) total.textContent = `LEÍDOS: ${state.vigItems.length}`;
  if (!list) return;
  if (!state.vigItems.length) {
    list.innerHTML = `<div class="grid-empty">Escanea un gafete para registrar el ingreso.</div>`;
    return;
  }
  list.innerHTML = state.vigItems.map((item, index) => {
    const badge = {
      PROCESSING: `<span class="badge badge-pending">PROCESANDO</span>`,
      OK: `<span class="badge badge-ok">${esc(item.tipo)} OK</span>`,
      DUP: `<span class="badge badge-dup">YA REGISTRADO</span>`,
      NOT_FOUND: `<span class="badge badge-pending">SIN REGISTRO</span>`,
      ERROR: `<span class="badge badge-err">ERROR</span>`,
    }[item.status] || "";
    const retry = item.status === "NOT_FOUND" || item.status === "ERROR";
    return `
      <div class="list-item" ${retry ? `data-retry="${index}" role="button" tabindex="0"` : ""}>
        <div class="main">
          <strong>${esc(item.dni)}</strong>
          <small>${esc(item.nombres || "—")}${retry ? " · toca para completar" : ""}</small>
        </div>
        <div class="side">${badge}</div>
      </div>`;
  }).join("");
}

async function handleVigilanciaScan(raw) {
  const dni = extractDni(raw);
  if (!/^\d{8}$/.test(dni)) {
    setEstado("Código inválido", "error");
    beep(false);
    return;
  }

  const tipo = state.vigMode;
  const key = `${dni}:${tipo}`;
  const last = document.getElementById("lastDni");
  if (last) last.textContent = dni;

  if (state.vigSeen.has(key)) {
    setEstado("DUPLICADO", "dup");
    beep(false);
    return;
  }
  state.vigSeen.add(key);

  const item = { dni, tipo, status: "PROCESSING", nombres: "Procesando…" };
  state.vigItems.unshift(item);
  paintVigilancia();
  setEstado("Procesando…", "");

  try {
    const person = await api.persona(dni);
    if (person?.found) {
      item.nombres = fullName(person) || "Sin nombre";
      await registrarVisita(item);
    } else if (person?.offline) {
      item.status = "ERROR";
      item.nombres = "Servicio externo no disponible";
      paintVigilancia();
      setEstado("Servicio no disponible", "error");
      openPersonForm(dni, tipo, item);
    } else {
      item.status = "NOT_FOUND";
      item.nombres = "Persona no encontrada";
      paintVigilancia();
      setEstado("No existe (registrar)", "error");
      beep(false);
      openPersonForm(dni, tipo, item);
    }
  } catch (err) {
    if (handleAuthError(err)) return;
    if (err instanceof ApiError && err.status === 404) {
      item.status = "NOT_FOUND";
      item.nombres = "Persona no encontrada";
      paintVigilancia();
      beep(false);
      openPersonForm(dni, tipo, item);
    } else {
      item.status = "ERROR";
      item.nombres = err?.message || "Error de red";
      paintVigilancia();
      setEstado("Error al consultar", "error");
      beep(false);
    }
  }
}

async function registrarVisita(item, manual = null) {
  item.status = "PROCESSING";
  paintVigilancia();
  try {
    const payload = { dni: item.dni, tipo: item.tipo, ...(manual || {}) };
    const res = await api.registrarVisita(payload);
    item.status = "OK";
    item.nombres = fullName(res) || item.nombres || "Registrado";
    setEstado(`${item.tipo} OK`, "ok");
    beep(true);
    flashFrame();
  } catch (err) {
    if (handleAuthError(err)) return;
    if (err instanceof ApiError && err.status === 409) {
      item.status = "DUP";
      item.nombres = "Ya registrado hoy";
      setEstado("YA REGISTRADO HOY", "dup");
      beep(false);
    } else if (err instanceof ApiError && (err.status === 404 || err.status === 503)) {
      item.status = "NOT_FOUND";
      item.nombres = err.message;
      setEstado("Completa el registro", "error");
      beep(false);
      openPersonForm(item.dni, item.tipo, item);
    } else {
      item.status = "ERROR";
      item.nombres = err?.message || "Error al registrar";
      setEstado("No se pudo registrar", "error");
      beep(false);
    }
  }
  paintVigilancia();
}

function openPersonForm(dni, tipo, item) {
  const body = `
    <p class="muted small">El DNI <strong>${esc(dni)}</strong> no está registrado. Completa los datos para registrar la ${esc(String(tipo).toLowerCase())}.</p>
    <div class="field mt-14">
      <label for="pNombres">Nombres</label>
      <input class="input" id="pNombres" autocomplete="off" required>
    </div>
    <div class="field">
      <label for="pPat">Apellido paterno</label>
      <input class="input" id="pPat" autocomplete="off" required>
    </div>
    <div class="field">
      <label for="pMat">Apellido materno</label>
      <input class="input" id="pMat" autocomplete="off" required>
    </div>
    <div class="form-error" id="pError" hidden></div>
    <button class="btn primary block" id="pSave">Registrar ${esc(tipo)}</button>`;

  const sheet = openSheet({ title: "Registro manual", body });
  const button = sheet.body.querySelector("#pSave");
  const error = sheet.body.querySelector("#pError");

  button.addEventListener("click", async () => {
    const nombres = sheet.body.querySelector("#pNombres").value.trim();
    const apPat = sheet.body.querySelector("#pPat").value.trim();
    const apMat = sheet.body.querySelector("#pMat").value.trim();
    if (!nombres || !apPat || !apMat) {
      error.textContent = "Completa nombres y apellidos.";
      error.hidden = false;
      return;
    }
    button.disabled = true;
    button.innerHTML = `<span class="spinner"></span> Registrando…`;
    try {
      const res = await api.registrarVisita({
        dni, tipo,
        nombres, apellido_paterno: apPat, apellido_materno: apMat,
      });
      item.status = "OK";
      item.nombres = fullName(res) || `${nombres} ${apPat} ${apMat}`;
      setEstado(`${tipo} OK`, "ok");
      beep(true);
      paintVigilancia();
      sheet.close();
      toast(`Registrado ${tipo}`, "ok");
    } catch (err) {
      if (handleAuthError(err)) return;
      if (err instanceof ApiError && err.status === 409) {
        item.status = "DUP";
        item.nombres = "Ya registrado hoy";
        paintVigilancia();
        sheet.close();
        toast("Ya estaba registrado hoy", "warn");
      } else {
        error.textContent = err.message || "No se pudo registrar.";
        error.hidden = false;
        button.disabled = false;
        button.textContent = `Registrar ${tipo}`;
      }
    }
  });
}

/* ------------------------------- Router ------------------------------- */
async function render() {
  stopScanner();
  modalRoot.replaceChildren();
  if (state.cleanup) {
    try { state.cleanup(); } catch { /* limpieza ajena */ }
    state.cleanup = null;
  }

  loadLote();
  const route = (location.hash.replace(/^#\/?/, "") || "").split("?")[0];

  if (!session.has()) {
    renderLogin();
    return;
  }

  // Con refresh token disponible se permite entrar aunque el access haya vencido.
  if (!session.access && !session.refresh) {
    renderLogin();
    return;
  }

  switch (route) {
    case "conteo": renderConteo(); break;
    case "historial": renderHistorial(); break;
    case "reportes": renderReportes(); break;
    case "consultas": renderConsultas(); break;
    case "vigilancia": renderVigilancia(); break;
    case "login":
      if (session.has()) go("menu");
      else renderLogin();
      break;
    default: renderMenu(); break;
  }
}

/* Delegación global de navegación */
document.addEventListener("click", (event) => {
  const nav = event.target.closest("[data-nav]");
  if (nav) {
    event.preventDefault();
    go(nav.dataset.nav);
  }
});

/* Pausa la cámara al salir de la app y la retoma al volver. */
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden") {
    stopScanner();
  } else if (session.has()) {
    const route = (location.hash.replace(/^#\/?/, "") || "").split("?")[0];
    if ((route === "conteo" || route === "vigilancia") && !state.scanner && window.__lastScanHandler) {
      startCamera(window.__lastScanHandler);
    }
  }
});

/* Refresco proactivo al volver tras inactividad. */
window.addEventListener("online", () => {
  const banner = document.getElementById("offlineBanner");
  if (banner) banner.remove();
  if (session.has() && session.expiresSoon(300)) refreshSession().catch(() => {});
});
window.addEventListener("offline", () => {
  if (!document.getElementById("offlineBanner") && session.has()) {
    const banner = document.createElement("div");
    banner.id = "offlineBanner";
    banner.className = "offline-banner";
    banner.textContent = "Sin conexión: las lecturas se guardan en el dispositivo.";
    document.body.prepend(banner);
  }
});

window.addEventListener("hashchange", render);

/* ------------------------------- Arranque ----------------------------- */
render();
// Enrich sessions created before the name field existed; keep offline data intact.
if (session.has()) {
  const user = session.user();
  api.me().then(profile => {
    if (session.user() !== user) return;
    session.saveProfile(profile);
    const route = location.hash.replace(/^#\/?/, "");
    if ((!route || route === "menu") && !modalRoot.childElementCount) renderMenu();
  }).catch(() => { /* Offline: retain the last known profile. */ });
}
if (!navigator.onLine) window.dispatchEvent(new Event("offline"));

/* ------------------------------- PWA ---------------------------------- */
if ("serviceWorker" in navigator) {
  let hadController = Boolean(navigator.serviceWorker.controller);
  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("./sw.js", {
        scope: "./",
        updateViaCache: "none",
      });

      const promptUpdate = (worker) => {
        toast("Hay una nueva versión disponible", "warn", {
          label: "Actualizar",
          onClick: () => {
            worker.postMessage({ type: "SKIP_WAITING" });
          },
        }, 15000);
      };

      if (registration.waiting) promptUpdate(registration.waiting);

      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        if (!worker) return;
        worker.addEventListener("statechange", () => {
          if (worker.state === "installed" && navigator.serviceWorker.controller) {
            promptUpdate(worker);
          }
        });
      });

      let reloading = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        // First installation claims the page; it must not interrupt login/camera.
        if (!hadController) {
          hadController = true;
          return;
        }
        if (reloading) return;
        reloading = true;
        window.location.reload();
      });

      // Busca actualizaciones al volver a primer plano.
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") registration.update().catch(() => {});
      });
    } catch { /* la app funciona aunque el SW no se registre */ }
  });
}
