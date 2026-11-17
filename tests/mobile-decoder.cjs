/* Real pixels -> camera stream -> Scanner -> Worker -> ZXing-C++ -> decoded text.
 * Requires playwright-core and qrcode in NODE_PATH. No business API writes.
 */
const assert = require("node:assert/strict");
const { chromium } = require("playwright-core");
const QRCode = require("qrcode");
const { execFileSync } = require("node:child_process");

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN || "/usr/bin/google-chrome", args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(process.env.MOBILE_URL || "http://127.0.0.1:8000/api/movil/");
    const compact = { t: "AbCdEf0123_-XY89", dni: "12345678", id: "007", p: "UVA" };
    // PNG real del backend, incluido el recuadro y el número centrales.
    const png = execFileSync(process.env.PYTHON_BIN || ".venv/bin/python", ["-c", [
      "import sys,base64",
      "sys.path.insert(0,'backend')",
      "from app.services.qr_service import generar_qr_memoria",
      "print(base64.b64encode(generar_qr_memoria('AbCdEf0123_-XY89','12345678','007','UVA').getvalue()).decode())",
    ].join(";")]).toString().trim();
    for (const mode of ["normal", "rotated", "inverted", "blurred", "legacy", "offline"]) {
      if (mode === "offline") {
        await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
        await page.context().setOffline(true);
      }
      const text = JSON.stringify(mode === "legacy"
        ? { ...compact, p: "UVA", v: 1, sig: "legacy-signature-value" }
        : compact);
      const image = mode === "legacy"
        ? await QRCode.toDataURL(text, { width: 180, margin: 4, errorCorrectionLevel: "H" })
        : `data:image/png;base64,${png}`;
      const decoded = await page.evaluate(async ({ image, mode }) => {
        const { Scanner } = await import("./js/scanner.js");
        const canvas = document.createElement("canvas");
        canvas.width = 1920;
        canvas.height = 1080;
        const ctx = canvas.getContext("2d");
        const img = new Image();
        img.src = image;
        await img.decode();
        const paint = () => {
          ctx.fillStyle = mode === "inverted" ? "#000" : "#fff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.save();
          ctx.translate(canvas.width / 2, canvas.height / 2);
          if (mode === "rotated") ctx.rotate(Math.PI / 2);
          if (mode === "inverted") ctx.filter = "invert(1)";
          if (mode === "blurred") ctx.filter = "blur(1px)";
          ctx.drawImage(img, -90, -90, 180, 180);
          ctx.restore();
        };
        paint();
        const stream = canvas.captureStream(10);
        const paintTimer = setInterval(paint, 100);
        const original = navigator.mediaDevices.getUserMedia;
        navigator.mediaDevices.getUserMedia = async () => stream;
        const video = document.createElement("video");
        video.setAttribute("playsinline", "");
        video.muted = true;
        document.body.append(video);
        let scanner, timeout;
        try {
          return await new Promise((resolve, reject) => {
            timeout = setTimeout(() => reject(new Error(`No QR decoded: ${mode}`)), 15000);
            scanner = new Scanner(video, { formats: ["QRCode"], onResult: resolve, onError: reject });
            scanner.start().catch(reject);
          });
        } finally {
          clearTimeout(timeout);
          clearInterval(paintTimer);
          scanner?.stop();
          stream.getTracks().forEach(track => track.stop());
          navigator.mediaDevices.getUserMedia = original;
          video.remove();
        }
      }, { image, mode });
      assert.equal(decoded, text);
      console.log(`PASS: real camera-pixel pipeline (${mode}, 180px in 1920px frame)`);
    }
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
