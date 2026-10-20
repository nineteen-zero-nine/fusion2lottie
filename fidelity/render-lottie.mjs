// Render chosen frames of a Lottie file with lottie-web (the player lottie-react wraps) in headless Chrome.
// Usage: node fidelity/render-lottie.mjs anim.json out-dir 0 5 10 ...
// Chrome: $CHROME, else the usual install paths.
import { existsSync } from 'node:fs';
import { mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import puppeteer from 'puppeteer-core';

const here = path.dirname(fileURLToPath(import.meta.url));
const [src, outDir, ...frames] = process.argv.slice(2);
const chrome = [process.env.CHROME, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find((p) => p && existsSync(p));
if (!chrome) {
  console.error('no Chrome found: set CHROME');
  process.exit(3);
}
const animation = JSON.parse(await readFile(src, 'utf8'));
await mkdir(outDir, { recursive: true });
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: animation.w, height: animation.h, deviceScaleFactor: 1 });
await page.setContent(`<body style="margin:0;background:#f0f"><div id="c" style="width:${animation.w}px;height:${animation.h}px"></div></body>`);
await page.addScriptTag({ path: path.join(here, 'node_modules/lottie-web/build/player/lottie.min.js') });
await page.evaluate((data) => {
  window.anim = lottie.loadAnimation({ container: document.getElementById('c'), renderer: 'svg', loop: false, autoplay: false, animationData: data });
}, animation);
const el = await page.$('#c');
for (const f of (frames.length ? frames.map(Number) : [...Array(animation.op).keys()])) {
  await page.evaluate((f) => window.anim.goToAndStop(f, true), f);
  await el.screenshot({ path: path.join(outDir, `f_${String(f).padStart(4, '0')}.png`) });
}
await browser.close();
