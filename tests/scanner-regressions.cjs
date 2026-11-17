/* Deterministic parser/capture/watchdog checks; no camera, network or timers. */
const assert = require("node:assert/strict");
const fs = require("node:fs");

(async () => {
  const source = fs.readFileSync("backend/app/mobile/js/scanner.js", "utf8");
  const { Scanner, parseQrPayload } = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const compact = { t: "UV-ABCDEF12", dni: "12345678", id: "007" };
  assert.equal(parseQrPayload(JSON.stringify(compact)).t, compact.t);
  const legacy = { ...compact, p: "UVA", v: 1, sig: "old-signature" };
  const parsed = parseQrPayload(JSON.stringify(legacy));
  assert.equal(parsed.producto, "UVA");
  assert.equal(parsed.version, "1");
  assert.equal(parsed.firma, "old-signature");
  assert.deepEqual(parsed.raw, legacy);
  assert.equal(parseQrPayload("not a QR"), null);

  const originalSet = global.setTimeout;
  const originalClear = global.clearTimeout;
  const pending = new Map();
  let seq = 0;
  global.setTimeout = (fn, ms) => { const id = ++seq; pending.set(id, { fn, ms }); return id; };
  global.clearTimeout = id => pending.delete(id);
  try {
    let failures = 1, sent = 0, terminated = 0, errors = 0;
    const scanner = new Scanner({
      videoWidth: 1920, videoHeight: 1080, readyState: 2, pause() {},
    }, { onError: () => errors++ });
    scanner.canvas = {};
    scanner.context = {
      drawImage() {},
      getImageData() {
        if (failures-- > 0) throw new Error("Transient video frame");
        return { width: 1920, height: 1080, data: new Uint8ClampedArray(4) };
      },
    };
    scanner.worker = { postMessage() { sent++; }, terminate() { terminated++; } };
    scanner.capture();
    assert.equal(errors, 0);
    assert.equal(pending.get(scanner.timer).ms, 250);
    const retry = pending.get(scanner.timer);
    pending.delete(scanner.timer);
    retry.fn();
    assert.equal(sent, 1);
    assert.equal(scanner.canvas.width, 1920);
    assert.equal(pending.get(scanner.watchdog).ms, 10000);
    pending.get(scanner.watchdog).fn();
    assert.equal(scanner.stopped, true);
    assert.equal(terminated, 1);
    assert.equal(errors, 1);
    assert.equal(pending.size, 0);
    console.log("PASS: compact/legacy parser, transient capture retry, native resolution, watchdog cleanup");
  } finally {
    global.setTimeout = originalSet;
    global.clearTimeout = originalClear;
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
