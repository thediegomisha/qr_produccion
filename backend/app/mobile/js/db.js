/* ============================================================
   Cola local de escaneos (IndexedDB).
   Replica el comportamiento de Room en la APK:
   - Un token solo puede entrar una vez (duplicado visible).
   - Estados: 0 pendiente, 1 en envío, 2 enviado, 9 inválido.
   - La rejilla y el total se calculan por sesión.
   ============================================================ */

const DB_NAME = "qrlector-pwa";
const DB_VERSION = 1;

export const STATUS = {
  PENDING: 0,
  QUEUED: 1,
  SENT: 2,
  INVALID: 9,
};

let dbPromise = null;

function uuid() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function openDB() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("scans")) {
        const store = db.createObjectStore("scans", { keyPath: "id", autoIncrement: true });
        store.createIndex("by_token", "token", { unique: true });
        store.createIndex("by_status", "status");
        store.createIndex("by_session", "session_uuid");
        store.createIndex("by_batch", "batch_uuid");
        store.createIndex("by_lote", "lote_codigo");
      }
      if (!db.objectStoreNames.contains("receipts")) {
        const receipts = db.createObjectStore("receipts", { keyPath: "batch_uuid" });
        receipts.createIndex("by_duplicates", "duplicates");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
    req.onblocked = () => reject(new Error("La base local está bloqueada por otra pestaña"));
  });
  return dbPromise;
}

function done(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error("Transacción cancelada"));
  });
}

/* ----------------------------- Escrituras ---------------------------- */

export async function addScan(scan) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("scans", "readwrite");
    const req = tx.objectStore("scans").add(scan);
    let inserted = true;
    req.onerror = (event) => {
      if (req.error?.name === "ConstraintError") {
        inserted = false;
        event.preventDefault();
        event.stopPropagation();
      } else {
        reject(req.error);
      }
    };
    tx.oncomplete = () => resolve(inserted);
    tx.onabort = () => reject(tx.error || new Error("No se pudo guardar el escaneo"));
  });
}

export async function pendingForUser(userId) {
  const db = await openDB();
  const all = await new Promise((resolve, reject) => {
    const tx = db.transaction("scans", "readonly");
    const req = tx.objectStore("scans").getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
  return all
    .filter((s) => (s.status === STATUS.PENDING || s.status === STATUS.QUEUED) && (!userId || s.user_id === userId))
    .sort((a, b) => String(b.scanned_at).localeCompare(String(a.scanned_at)));
}

export async function sentForUser(userId) {
  const db = await openDB();
  const all = await new Promise((resolve, reject) => {
    const tx = db.transaction("scans", "readonly");
    const req = tx.objectStore("scans").getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
  return all
    .filter((s) => s.status === STATUS.SENT && (!userId || s.user_id === userId))
    .sort((a, b) => String(b.scanned_at).localeCompare(String(a.scanned_at)));
}

export async function duplicateReceipts(userId) {
  const db = await openDB();
  const [receipts, scans] = await Promise.all([
    new Promise((resolve, reject) => {
      const tx = db.transaction("receipts", "readonly");
      const req = tx.objectStore("receipts").getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    }),
    new Promise((resolve, reject) => {
      const tx = db.transaction("scans", "readonly");
      const req = tx.objectStore("scans").getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    }),
  ]);
  const owners = new Map();
  for (const scan of scans) {
    if (scan.batch_uuid && !owners.has(scan.batch_uuid)) owners.set(scan.batch_uuid, scan.user_id);
  }
  return receipts
    .filter((r) => Number(r.duplicates) > 0 && (!userId || owners.get(r.batch_uuid) === userId))
    .sort((a, b) => Number(b.processed_at_ms) - Number(a.processed_at_ms));
}

export async function countsForSession(sessionUuid) {
  const db = await openDB();
  const rows = await new Promise((resolve, reject) => {
    const tx = db.transaction("scans", "readonly");
    const req = tx.objectStore("scans").index("by_session").getAll(sessionUuid);
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
  const map = new Map();
  let total = 0;
  for (const scan of rows) {
    if (scan.status === STATUS.INVALID) continue;
    total += 1;
    const entry = map.get(scan.dni) || { dni: scan.dni, qty: 0, last: "" };
    entry.qty += 1;
    if (String(scan.scanned_at) > entry.last) entry.last = String(scan.scanned_at);
    map.set(scan.dni, entry);
  }
  return {
    total,
    items: [...map.values()].sort((a, b) => String(b.last).localeCompare(String(a.last))),
  };
}

/**
 * Selecciona los pendientes más antiguos de un usuario+lote (una sola sesión,
 * igual que la APK) y los marca como "en envío".
 */
export async function prepareContext(userId, loteCodigo, max = 500) {
  const db = await openDB();
  const prepared = await new Promise((resolve, reject) => {
    const tx = db.transaction("scans", "readwrite");
    const store = tx.objectStore("scans");
    const req = store.getAll();
    let result = { batchUuid: null, rows: [] };
    tx.oncomplete = () => resolve(result);
    tx.onabort = () => reject(tx.error || new Error("No se pudo preparar el envío"));
    req.onsuccess = () => {
      const all = req.result || [];
      const candidates = all
        .filter((s) => s.status === STATUS.PENDING && s.user_id === userId && s.lote_codigo === loteCodigo)
        .sort((a, b) => {
          const byDate = String(a.scanned_at).localeCompare(String(b.scanned_at));
          return byDate !== 0 ? byDate : Number(a.id) - Number(b.id);
        });
      if (!candidates.length) {
        return;
      }
      const session = candidates[0].session_uuid;
      const batchUuid = uuid();
      const selected = candidates.filter((s) => s.session_uuid === session).slice(0, max);
      for (const scan of selected) {
        scan.status = STATUS.QUEUED;
        scan.batch_uuid = batchUuid;
        store.put(scan);
      }
      result = { batchUuid, rows: selected };
    };
    req.onerror = () => reject(req.error);
  });
  return prepared;
}

export async function completeBatch(batchUuid, loteCodigo, accepted, duplicates) {
  const db = await openDB();
  const tx = db.transaction(["scans", "receipts"], "readwrite");
  const scans = tx.objectStore("scans");
  const index = scans.index("by_batch");
  const req = index.getAll(batchUuid);
  req.onsuccess = () => {
    for (const scan of req.result || []) {
      scan.status = STATUS.SENT;
      scans.put(scan);
    }
  };
  tx.objectStore("receipts").put({
    batch_uuid: batchUuid,
    lote_codigo: loteCodigo,
    accepted: Number(accepted) || 0,
    duplicates: Number(duplicates) || 0,
    processed_at_ms: Date.now(),
  });
  await done(tx);
}

export async function rollbackBatch(batchUuid) {
  if (!batchUuid) return;
  const db = await openDB();
  const tx = db.transaction("scans", "readwrite");
  const scans = tx.objectStore("scans");
  const req = scans.index("by_batch").getAll(batchUuid);
  req.onsuccess = () => {
    for (const scan of req.result || []) {
      if (scan.status === STATUS.QUEUED) {
        scan.status = STATUS.PENDING;
        scan.batch_uuid = null;
        scans.put(scan);
      }
    }
  };
  await done(tx);
}

export async function clearHistory() {
  const db = await openDB();
  const tx = db.transaction(["scans", "receipts"], "readwrite");
  tx.objectStore("scans").clear();
  tx.objectStore("receipts").clear();
  await done(tx);
}

// Solo se ejecuta al arrancar, bajo el bloqueo exclusivo de sincronización.
export async function recoverInterruptedBatches() {
  const database = await openDB();
  const tx = database.transaction("scans", "readwrite");
  const store = tx.objectStore("scans");
  const req = store.index("by_status").getAll(STATUS.QUEUED);
  req.onsuccess = () => {
    for (const scan of req.result || []) {
      scan.status = STATUS.PENDING;
      scan.batch_uuid = null;
      store.put(scan);
    }
  };
  await done(tx);
}

export async function clearSessionScans(sessionUuid) {
  const db = await openDB();
  const tx = db.transaction("scans", "readwrite");
  const store = tx.objectStore("scans");
  const req = store.index("by_session").getAllKeys(sessionUuid);
  req.onsuccess = () => {
    for (const key of req.result || []) store.delete(key);
  };
  await done(tx);
}

export async function countPendingForLote(loteCodigo) {
  const db = await openDB();
  const rows = await new Promise((resolve, reject) => {
    const tx = db.transaction("scans", "readonly");
    const req = tx.objectStore("scans").index("by_lote").getAll(loteCodigo);
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
  return rows.filter((s) => s.status === STATUS.PENDING).length;
}
