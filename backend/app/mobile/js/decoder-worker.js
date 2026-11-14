/* ZXing-C++ runs outside the UI thread. All resources are same-origin/offline. */
importScripts("../vendor/zxing-wasm-reader.js");

const ready = ZXingWASM.prepareZXingModule({
  overrides: {
    locateFile: (path) => new URL(`../vendor/${path}`, self.location.href).href,
  },
  fireImmediately: true,
});
ready.then(
  () => self.postMessage({ type: "ready" }),
  error => self.postMessage({ type: "error", message: error.message || "No se pudo cargar ZXing-C++" }),
);

self.onmessage = async ({ data }) => {
  if (data.type !== "decode") return;
  try {
    await ready;
    const results = await ZXingWASM.readBarcodes({
      data: new Uint8ClampedArray(data.buffer), width: data.width, height: data.height,
    }, {
      formats: data.formats, tryHarder: true, tryRotate: true,
      tryInvert: true, tryDownscale: true, maxNumberOfSymbols: 1,
    });
    self.postMessage({ type: "result", text: results.find(result => result.isValid)?.text || "" });
  } catch (error) {
    self.postMessage({ type: "error", message: error.message || "Error al decodificar" });
  }
};
