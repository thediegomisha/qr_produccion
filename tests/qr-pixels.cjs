/* Backend PNG -> real PWA ZXing WASM. No camera or network required.
 * PYTHON_BIN=.venv/bin/python NODE_PATH=/path/to/node_modules node tests/qr-pixels.cjs
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");
const { PNG } = require("pngjs");

(async () => {
  vm.runInThisContext(fs.readFileSync("backend/app/mobile/vendor/zxing-wasm-reader.js", "utf8"));
  await ZXingWASM.prepareZXingModule({
    overrides: { wasmBinary: fs.readFileSync("backend/app/mobile/vendor/zxing_reader.wasm") },
    fireImmediately: true,
  });
  for (const [size, blur] of [[120, 0], [160, 0], [180, 1], [220, 1.5]]) {
    const png = execFileSync(process.env.PYTHON_BIN || ".venv/bin/python", ["-c", [
      "import sys,io",
      "sys.path.insert(0,'backend')",
      "from PIL import Image,ImageFilter",
      "from app.services.qr_service import generar_qr_memoria",
      "img=Image.open(generar_qr_memoria('AbCdEf0123_-XY89','12345678','007','UVA'))",
      `img=img.resize((${size},${size}),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(${blur}))`,
      "out=io.BytesIO();img.save(out,format='PNG');sys.stdout.buffer.write(out.getvalue())",
    ].join(";")]);
    const image = PNG.sync.read(png);
    const results = await ZXingWASM.readBarcodes({
      data: new Uint8ClampedArray(image.data), width: image.width, height: image.height,
    }, {
      formats: ["QRCode"], tryHarder: true, tryRotate: true,
      tryInvert: true, tryDownscale: true, maxNumberOfSymbols: 1,
    });
    assert.equal(results.find(result => result.isValid)?.text,
      '{"t":"AbCdEf0123_-XY89","dni":"12345678","id":"007","p":"UVA"}');
    console.log(`PASS: backend PNG + central number, ${size}px, blur ${blur}px`);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
