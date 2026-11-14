/* ============================================================
   Escáner de cámara para Safari/iOS y Android.
   Usa ZXing-C++ WebAssembly en un Worker sobre getUserMedia.
   Formatos: QR (etiquetas) y Code 39 (gafetes de vigilancia).
   ============================================================ */

export class Scanner {
  constructor(video, { onResult, onError, formats, deviceId } = {}) {
    this.video = video;
    this.onResult = onResult || (() => {});
    this.onError = onError || (() => {});
    this.formats = formats || ["QRCode", "Code39"];
    this.deviceId = deviceId;
    this.worker = null;
    this.timer = null;
    this.cancelInit = null;
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
    try {
      await this.initDecoder();
      if (this.stopped) return;
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          ...(this.deviceId ? { deviceId: { exact: this.deviceId } } : { facingMode: { ideal: "environment" } }),
          width: { ideal: 1920 }, height: { ideal: 1080 },
        },
      });
      if (this.stopped) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      this.stream = stream;
      this.video.muted = true;
      this.video.setAttribute("playsinline", "");
      this.video.srcObject = stream;
      this.track = this.stream?.getVideoTracks?.()[0] || null;
      await this.video.play();
      // Continuous autofocus is optional; Safari may not expose the capability.
      const caps = this.track?.getCapabilities?.() || {};
      if (caps.focusMode?.includes("continuous")) {
        await this.track.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
      }
      this.canvas = document.createElement("canvas");
      this.context = this.canvas.getContext("2d", { willReadFrequently: true });
      if (!this.context) throw new Error("No se pudo preparar la imagen de cámara");
      if (!this.stopped) this.capture();
    } catch (err) {
      this.stop();
      throw this.translate(err);
    }
  }

  initDecoder() {
    return new Promise((resolve, reject) => {
      const worker = new Worker(new URL("./decoder-worker.js", import.meta.url));
      this.worker = worker;
      let initialized = false;
      const timeout = setTimeout(() => fail(new Error("El motor de lectura tardó demasiado en cargar")), 20000);
      const fail = error => {
        clearTimeout(timeout);
        if (!initialized) reject(error);
        else if (!this.stopped) this.onError(error);
      };
      this.cancelInit = () => fail(new Error("Lectura cancelada"));
      worker.onerror = () => fail(new Error("No se pudo ejecutar ZXing-C++. Recarga la app con conexión."));
      worker.onmessage = ({ data }) => {
        if (data.type === "ready") {
          clearTimeout(timeout);
          initialized = true;
          this.cancelInit = null;
          resolve();
        } else if (data.type === "error") {
          fail(new Error(data.message));
        } else if (data.type === "result" && !this.stopped) {
          if (data.text) this.emit(data.text);
          this.timer = setTimeout(() => this.capture(), 140);
        }
      };
    });
  }

  capture() {
    if (this.stopped) return;
    const { videoWidth: width, videoHeight: height } = this.video;
    if (!width || !height || this.video.readyState < 2) {
      this.timer = setTimeout(() => this.capture(), 150);
      return;
    }
    try {
      // Decode the entire frame; the overlay does not crop away dense QR codes.
      const scale = Math.min(1, 1600 / Math.max(width, height));
      this.canvas.width = Math.round(width * scale);
      this.canvas.height = Math.round(height * scale);
      this.context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
      const image = this.context.getImageData(0, 0, this.canvas.width, this.canvas.height);
      this.worker.postMessage({
        type: "decode", width: image.width, height: image.height,
        buffer: image.data.buffer, formats: this.formats,
      }, [image.data.buffer]);
    } catch (error) {
      this.onError(error);
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
    clearTimeout(this.timer);
    this.cancelInit?.();
    this.cancelInit = null;
    this.worker?.terminate();
    this.worker = null;
    try {
      const stream = this.stream || this.video?.srcObject;
      stream?.getTracks?.().forEach((track) => track.stop());
    } catch { /* stream ya cerrado */ }
    if (this.video) {
      try { this.video.pause(); } catch { /* sin video */ }
      try { this.video.srcObject = null; } catch { /* sin video */ }
    }
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
