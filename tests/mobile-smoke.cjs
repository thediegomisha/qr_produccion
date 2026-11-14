/* Local smoke test: all API calls are mocked; no database writes.
 * NODE_PATH=/path/to/node_modules CHROME_BIN=/path/to/chrome node tests/mobile-smoke.cjs
 */
const assert = require("node:assert/strict");
const { chromium } = require("playwright-core");

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN || "/usr/bin/google-chrome",
    args: ["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    let refreshes = 0;
    const access = () => `e30.${Buffer.from(JSON.stringify({
      sub: "smoke", rol: "ROOT", exp: Math.floor(Date.now() / 1000) + 3600,
    })).toString("base64url")}.test`;
    await context.route("**/api/**", async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (path.startsWith("/api/movil/")) return route.continue();
      let body;
      if (path === "/api/auth/login" || path === "/api/auth/refresh") {
        if (path.endsWith("refresh")) refreshes++;
        body = { access_token: access(), refresh_token: "mock-refresh", usuario: "smoke", rol: "ROOT" };
      } else if (path === "/api/lotes") {
        body = { items: [{ codigo: "SMOKE", estado: "ABIERTO" }] };
      } else if (path === "/api/lotes/ensure") {
        body = { codigo: "SMOKE", estado: "ABIERTO" };
      } else if (path === "/api/scans/batch") {
        const batch = request.postDataJSON();
        body = { batch_uuid: batch.batch_uuid, accepted_count: batch.scans.length, duplicate_count: 0 };
      } else if (path.startsWith("/api/reports/")) {
        body = { totals: { total_lecturas: 3 }, rows: [] };
      } else if (path.startsWith("/api/vigilancia/")) {
        body = { found: true, dni: "12345678", nombres: "PERSONA", apellido_paterno: "PRUEBA" };
      } else {
        throw new Error(`Unexpected API request: ${path}`);
      }
      await route.fulfill({ json: body });
    });
    await page.goto(process.env.MOBILE_URL || "http://127.0.0.1:8000/api/movil/");
    await page.getByLabel("Usuario", { exact: true }).fill("smoke");
    await page.getByLabel("Contraseña", { exact: true }).fill("not-a-real-password");
    await page.getByRole("button", { name: "Iniciar sesión", exact: true }).click();
    await page.getByRole("button", { name: /Conteo de cajas/ }).waitFor();
    await page.getByRole("button", { name: /Cambiar/ }).click();
    await page.locator('[data-code="SMOKE"]').click();
    await page.getByRole("button", { name: /Conteo de cajas/ }).click();
    await page.waitForFunction(() => Boolean(window.__lastScanHandler));
    await page.evaluate(async () => {
      const scan = JSON.stringify({ t: "test-token", dni: "12345678", id: "1" });
      await window.__lastScanHandler(scan);
      await window.__lastScanHandler(scan);
    });
    await page.waitForFunction(() => document.querySelector("#total")?.textContent === "TOTAL: 1");
    assert.equal(await page.locator("#estado").textContent(), "DUPLICADO");
    await page.getByRole("button", { name: "Enviar", exact: true }).click();
    await page.waitForFunction(() => document.querySelector("#estado")?.textContent === "ENVIADO OK (1)");

    // Recovery from a tab killed after preparing but before recording a receipt.
    await page.evaluate(async () => {
      const db = await import("./js/db.js");
      await db.addScan({
        token: "interrupted", dni: "87654321", user_id: "smoke",
        lote_codigo: "SMOKE", session_uuid: localStorage.getItem("qr.session"),
        status: 0, scanned_at: new Date().toISOString(), raw: {},
      });
      await db.prepareContext("smoke", "SMOKE");
    });
    await page.reload();
    await page.getByRole("button", { name: "Enviar", exact: true }).click();
    await page.waitForFunction(() => document.querySelector("#estado")?.textContent === "ENVIADO OK (1)");
    await page.evaluate(() => localStorage.setItem("qr.access", "expired"));
    await page.getByRole("button", { name: "Volver", exact: true }).click();
    await page.getByRole("button", { name: /^Reportes/ }).click();
    await page.waitForFunction(() => document.querySelector("#loteSel")?.options.length > 1);
    assert.ok(refreshes > 0, "Refresh was requested after access token expired");

    // Wait for shell activation, then reload with all HTTP disabled.
    await page.waitForFunction(() => Boolean(navigator.serviceWorker.controller));
    await context.setOffline(true);
    await page.reload();
    await page.getByRole("button", { name: "Volver", exact: true }).click();
    await page.getByRole("button", { name: /Conteo de cajas/ }).click();
    await page.locator("#grid").waitFor();
    await page.evaluate(() => window.__lastScanHandler(JSON.stringify({ t: "offline-token", dni: "12345678" })));
    await page.waitForFunction(() => document.querySelector("#total")?.textContent === "TOTAL: 3");
    assert.deepEqual(errors, []);
    console.log("PASS: login, lot, duplicate, send, interrupted queue, refresh, offline shell and local scan");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
