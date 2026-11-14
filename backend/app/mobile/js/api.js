/* ============================================================
   Cliente HTTP de la PWA.
   - Guarda access + refresh token (la sesión sobrevive inactividad).
   - Renueva el access token antes de que expire y reintenta un 401.
   ============================================================ */

const HERE = new URL(".", window.location.href);
export const API_ROOT = new URL("..", HERE).pathname.replace(/\/+$/, "");

const K_ACCESS = "qr.access";
const K_REFRESH = "qr.refresh";
const K_USER = "qr.user";
const K_ROLE = "qr.role";

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/* ------------------------------ Sesión ------------------------------ */

function read(key) {
  try { return localStorage.getItem(key) || ""; } catch { return ""; }
}
function write(key, value) {
  try { localStorage.setItem(key, value); } catch { /* modo privado */ }
}
function remove(key) {
  try { localStorage.removeItem(key); } catch { /* modo privado */ }
}

export function jwtPayload(token) {
  try {
    const part = String(token || "").split(".")[1];
    if (!part) return null;
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const bytes = Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

function normalizeRole(raw) {
  let r = String(raw || "").trim().toUpperCase();
  if (r === "OPERARIO") r = "OPERADOR";
  if (r === "ADMIN") r = "ROOT";
  if (r === "MANAGER") r = "GERENCIA";
  if (r === "AGENTE") r = "VIGILANCIA";
  return r;
}

export const session = {
  get access() { return read(K_ACCESS); },
  get refresh() { return read(K_REFRESH); },
  user() { return read(K_USER); },
  role() { return normalizeRole(read(K_ROLE) || jwtPayload(this.access)?.rol); },
  has() { return Boolean(this.access || this.refresh); },
  save(data) {
    write(K_ACCESS, data.access_token || "");
    if (data.refresh_token) write(K_REFRESH, data.refresh_token);
    write(K_USER, data.usuario || jwtPayload(data.access_token)?.sub || "");
    write(K_ROLE, normalizeRole(data.rol || jwtPayload(data.access_token)?.rol));
  },
  clear() {
    remove(K_ACCESS); remove(K_REFRESH); remove(K_USER); remove(K_ROLE);
  },
  expiresSoon(marginSeconds = 90) {
    const payload = jwtPayload(this.access);
    if (!payload || !payload.exp) return true;
    return payload.exp * 1000 - Date.now() < marginSeconds * 1000;
  },
};

/* ------------------------------ Refresh ----------------------------- */

let refreshInFlight = null;

async function doRefresh() {
  const token = session.refresh;
  if (!token) throw new ApiError(401, "Sesión expirada");
  const res = await fetch(`${API_ROOT}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: token }),
    cache: "no-store",
    signal: AbortSignal.timeout(20000),
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* respuesta no JSON */ }
  if (!res.ok || !data?.access_token) {
    // Un fallo temporal del servidor no invalida las credenciales guardadas.
    if (res.status === 401 || res.status === 403) session.clear();
    throw new ApiError(res.status || 401, "La sesión expiró. Inicia sesión de nuevo.", data);
  }
  session.save(data);
  return data;
}

export function refreshSession() {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

/* ------------------------------ Request ----------------------------- */

async function parseBody(res) {
  const text = await res.text();
  if (!text) return null;
  try { return JSON.parse(text); } catch { return text; }
}

function errorMessage(status, body) {
  if (body && typeof body === "object") {
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
    }
  }
  if (typeof body === "string" && body.trim()) return body.trim().slice(0, 240);
  if (status === 401) return "Sesión expirada";
  if (status === 403) return "No tienes permisos para esta acción";
  if (status === 409) return "Conflicto: el registro ya existe";
  return `Error del servidor (${status})`;
}

/**
 * Petición autenticada con renovación automática.
 * @param {string} path ruta relativa a /api, p. ej. "/scans/batch"
 */
export async function request(path, { method = "GET", body, auth = true, retry = true, timeout = 20000 } = {}) {
  if (auth && session.has() && session.expiresSoon()) {
    try { await refreshSession(); } catch { /* el 401 lo maneja abajo */ }
  }

  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && session.access) headers.Authorization = `Bearer ${session.access}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  let res;
  try {
    res = await fetch(`${API_ROOT}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });
  } catch (err) {
    clearTimeout(timer);
    if (err?.name === "AbortError") throw new ApiError(0, "El servidor tardó demasiado en responder");
    throw new ApiError(0, "Sin conexión con el servidor");
  }
  clearTimeout(timer);

  if (res.status === 401 && auth && retry && session.refresh) {
    try {
      await refreshSession();
      return await request(path, { method, body, auth, retry: false, timeout });
    } catch (err) {
      throw err instanceof ApiError ? err : new ApiError(401, "Sesión expirada");
    }
  }

  const data = await parseBody(res);
  if (!res.ok) throw new ApiError(res.status, errorMessage(res.status, data), data);
  return data;
}

/* ------------------------------ Endpoints --------------------------- */

function qs(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      search.set(key, String(value).trim());
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const api = {
  login(usuario, password) {
    return request("/auth/login", { method: "POST", body: { usuario, password }, auth: false });
  },
  me() { return request("/auth/me"); },

  listLotes({ limit = 200, offset = 0, q = "", estado } = {}) {
    return request(`/lotes${qs({ limit, offset, q, estado })}`);
  },
  ensureLote(codigo) {
    return request("/lotes/ensure", { method: "POST", body: { codigo } });
  },
  closeLote(codigo) {
    return request(`/lotes/${encodeURIComponent(codigo)}/close`, { method: "POST" });
  },
  openLote(codigo) {
    return request(`/lotes/${encodeURIComponent(codigo)}/open`, { method: "POST" });
  },

  postBatch(payload) {
    return request("/scans/batch", { method: "POST", body: payload, timeout: 30000 });
  },
  tokenExists(token) {
    return request(`/scans/exists/${encodeURIComponent(token)}`);
  },

  dniSummary({ lote_codigo, producto, scanned_by, date_from, date_to }) {
    return request(`/reports/dni-summary${qs({ lote_codigo, producto, scanned_by, date_from, date_to })}`);
  },
  operatorSummary({ lote_codigo, producto, scanned_by, date_from, date_to }) {
    return request(`/reports/operator-summary${qs({ lote_codigo, producto, scanned_by, date_from, date_to })}`);
  },

  persona(dni) {
    return request(`/vigilancia/persona/${qs({ dni })}`);
  },
  registrarVisita(payload) {
    return request("/vigilancia/visita", { method: "POST", body: payload });
  },
  visitas(fecha, limit = 500) {
    return request(`/vigilancia/visitas${qs({ fecha, limit })}`);
  },
};
