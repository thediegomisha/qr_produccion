/* Real pixels -> camera stream -> Scanner -> Worker -> ZXing-C++ -> decoded text.
 * Requires playwright-core and qrcode in NODE_PATH. No business API writes.
 */
const assert = require("node:assert/strict");
const { chromium } = require("playwright-core");
const QRCode = require("qrcode");

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN || "/usr/bin/google-chrome", args: ["--no-sandbox"],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(process.env.MOBILE_URL || "http://127.0.0.1:8000/api/movil/");
    for (const mode of ["normal", "rotated", "inverted", "offline"]) {
      if (mode === "offline") {
        await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
        await page.context().setOffline(true);
      }
      const text = JSON.stringify({
        t: `scan-${mode}`, dni: "12345678", id: "A123", producto: "UVA",
        version: "1", firma: "signed-qr-" + "abcdef1234567890".repeat(6),
      });
      const image = await QRCode.toDataURL(text, { width: 500, margin: 4 });
      const decoded = await page.evaluate(async ({ image, mode }) => {
        const { Scanner } = await import("./js/scanner.js");
        const canvas = document.createElement("canvas");
        canvas.width = 720;
        canvas.height = 960;
        const ctx = canvas.getContext("2d");
        const img = new Image();
        img.src = image;
        await img.decode();
        const paint = () => {
          ctx.fillStyle = mode === "inverted" ? "#000" : "#fff";
          ctx.fillRect(0, 0, 720, 960);
          ctx.save();
          ctx.translate(360, 480);
          if (mode === "rotated") ctx.rotate(Math.PI / 2);
          if (mode === "inverted") ctx.filter = "invert(1)";
          ctx.drawImage(img, -250, -250, 500, 500);
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
      console.log(`PASS: real camera-pixel pipeline (${mode})`);
    }
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
