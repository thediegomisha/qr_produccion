/* ============================================================
   Escáner de cámara para Safari/iOS y Android.
   Usa ZXing (incluido localmente) sobre getUserMedia.
   Formatos: QR (etiquetas) y Code 39 (gafetes de vigilancia).
   ============================================================ */

const FORMATS = () => {
  const Z = window.ZXing;
  return [Z.BarcodeFormat.QR_CODE, Z.BarcodeFormat.CODE_39];
};

export class Scanner {
  constructor(video, { onResult, onError, formats } = {}) {
    this.video = video;
    this.onResult = onResult || (() => {});
    this.onError = onError || (() => {});
    this.formats = formats || FORMATS();
    this.reader = null;
    this.controls = null;
    this.stream = null;
    this.lastText = "";
    this.lastAt = 0;
    this.stopped = false;
    this.track = null;
  }

  async start() {
    this.stopped = false;

    if (!window.isSecureContext) {
      throw new ScannerError(
        "https",
        "La cámara necesita una conexión segura (HTTPS). Abre la app con la dirección WAN."
      );
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new ScannerError("unsupported", "Este navegador no permite usar la cámara.");
    }
    if (!window.ZXing) {
      throw new ScannerError("decoder", "No se pudo cargar el lector. Recarga la página.");
    }

    const Z = window.ZXing;
    const hints = new Map();
    hints.set(Z.DecodeHintType.POSSIBLE_FORMATS, this.formats);
    hints.set(Z.DecodeHintType.TRY_HARDER, true);

    this.reader = new Z.BrowserMultiFormatReader(hints, 180);

    try {
      this.controls = await this.reader.decodeFromConstraints(
        {
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
        },
        this.video,
        (result) => {
          if (this.stopped || !result) return;
          const text = result.getText ? result.getText() : String(result);
          if (text) this.emit(text);
        }
      );
      this.stream = this.video.srcObject;
      if (this.stopped) {
        this.stop();
        return;
      }
      this.track = this.stream?.getVideoTracks?.()[0] || null;
      try { await this.video.play(); } catch { /* iOS a veces resuelve solo */ }
    } catch (err) {
      this.stop();
      throw this.translate(err);
    }
  }

  emit(text) {
    const now = Date.now();
    // Evita ráfagas del mismo código mientras la cámara sigue enfocando.
    if (text === this.lastText && now - this.lastAt < 1400) return;
    this.lastText = text;
    this.lastAt = now;
    this.onResult(text);
  }

  translate(err) {
    const name = err?.name || "";
    if (name === "NotAllowedError" || name === "SecurityError") {
      return new ScannerError(
        "permission",
        "Permiso de cámara denegado. Actívalo en Ajustes de Safari para este sitio."
      );
    }
    if (name === "NotFoundError" || name === "OverconstrainedError") {
      return new ScannerError("nodevice", "No se encontró una cámara disponible en este dispositivo.");
    }
    if (name === "NotReadableError" || name === "AbortError") {
      return new ScannerError("busy", "La cámara está siendo usada por otra aplicación.");
    }
    return new ScannerError("unknown", err?.message || "No se pudo iniciar la cámara.");
  }

  async hasTorch() {
    try {
      const caps = this.track?.getCapabilities?.();
      return Boolean(caps?.torch);
    } catch {
      return false;
    }
  }

  async setTorch(on) {
    if (!this.track) return false;
    try {
      await this.track.applyConstraints({ advanced: [{ torch: Boolean(on) }] });
      return Boolean(on);
    } catch {
      return false;
    }
  }

  stop() {
    this.stopped = true;
    try { this.controls?.stop?.(); } catch { /* ya detenido */ }
    try { this.reader?.reset?.(); } catch { /* ya liberado */ }
    try {
      const stream = this.stream || this.video?.srcObject;
      stream?.getTracks?.().forEach((track) => track.stop());
    } catch { /* stream ya cerrado */ }
    if (this.video) {
      try { this.video.pause(); } catch { /* sin video */ }
      try { this.video.srcObject = null; } catch { /* sin video */ }
    }
    this.reader = null;
    this.controls = null;
    this.stream = null;
    this.track = null;
  }
}

export class ScannerError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "ScannerError";
    this.code = code;
  }
}

/* ------------------------- Utilidades de payload ------------------------- */

/** Extrae el JSON del QR aunque venga con prefijo o saltos de línea. */
export function parseQrPayload(raw) {
  if (!raw) return null;
  let text = String(raw).trim();
  const start = text.indexOf("{");
  if (start < 0) return null;
  text = text.slice(start);
  try {
    const obj = JSON.parse(text);
    if (!obj || typeof obj !== "object") return null;
    return {
      t: String(obj.t ?? "").trim(),
      dni: String(obj.dni ?? "").replace(/\D/g, ""),
      id: String(obj.id ?? "").trim(),
      producto: String(obj.producto ?? "").trim(),
      version: String(obj.version ?? "").trim(),
      firma: String(obj.firma ?? "").trim(),
      raw: obj,
    };
  } catch {
    return null;
  }
}

/** Para Code 39: acepta JSON con dni o cualquier texto que contenga 8 dígitos. */
export function extractDni(raw) {
  const payload = parseQrPayload(raw);
  if (payload?.dni) return payload.dni;
  const digits = String(raw || "").replace(/\D/g, "");
  if (digits.length === 8) return digits;
  const match = String(raw || "").match(/(\d{8})/);
  return match ? match[1] : "";
}
