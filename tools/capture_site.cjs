// Review the actual static pages in the runner's browser before capturing them.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { createRequire } = require('node:module');

const requireTools = createRequire(path.join(process.env.SITE_REVIEW_TOOLS, 'package.json'));
const puppeteer = requireTools('puppeteer');
const { PNG } = requireTools('pngjs');
const targets = [
  { name: 'home', page: '/', anchor: '#november-title' },
  { name: 'hydra', page: '/hydra/', anchor: '#routing' },
  { name: 'research', page: '/research/', anchor: '#november-routing' },
  { name: 'router', page: '/hydra/', anchor: '#routing-map', element: true },
];

async function main() {
  await fs.mkdir('site-review', { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH,
    headless: true,
    args: ['--no-sandbox'],
  });
  const results = [];
  try {
    for (const width of [1440, 390]) {
      for (const target of targets) {
        const page = await browser.newPage();
        const failures = [];
        page.on('pageerror', error => failures.push(String(error)));
        page.on('response', response => {
          if (response.status() >= 400 && ['document', 'stylesheet', 'image', 'font'].includes(response.request().resourceType())) {
            failures.push(`${response.status()} ${response.url()}`);
          }
        });
        await page.setViewport({ width, height: 1000, deviceScaleFactor: 1 });
        const response = await page.goto(`http://127.0.0.1:4187${target.page}`, { waitUntil: 'networkidle0' });
        assert.equal(response.status(), 200, target.name);
        const element = await page.waitForSelector(target.anchor, { visible: true });
        await element.evaluate(node => node.scrollIntoView({ block: 'start' }));
        await page.evaluate(async () => {
          await document.fonts.ready;
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        });
        await page.waitForFunction(() => [...document.images].every(img => {
          const box = img.getBoundingClientRect();
          return box.bottom <= 0 || box.top >= innerHeight || (img.complete && img.naturalWidth > 0);
        }));
        const metrics = await page.evaluate(() => ({
          width: innerWidth,
          overflow: document.documentElement.scrollWidth > innerWidth + 1,
          title: document.title,
        }));
        assert.equal(metrics.width, width);
        assert.equal(metrics.overflow, false, `${target.name} overflows at ${width}px`);
        assert.deepEqual(failures, [], target.name);
        const screenshot = `site-review/${target.name}-${width}.png`;
        const box = target.element ? await element.boundingBox() : { width, height: 1000 };
        if (target.element) await element.screenshot({ path: screenshot });
        else await page.screenshot({ path: screenshot });
        const png = PNG.sync.read(await fs.readFile(screenshot));
        assert.ok(Math.abs(png.width - Math.round(box.width)) <= 1, screenshot);
        assert.ok(Math.abs(png.height - Math.round(box.height)) <= 1, screenshot);
        const firstPixel = png.data.readUInt32BE(0);
        let varied = false;
        for (let i = 4; i < png.data.length && !varied; i += 4) varied = png.data.readUInt32BE(i) !== firstPixel;
        assert.ok(varied, `${screenshot} is uniformly blank`);
        results.push({ ...metrics, target: target.name, screenshot, imageWidth: png.width, imageHeight: png.height, varied, failures });
        await page.close();
      }
    }
    assert.equal(results.length, 8);
  } finally {
    await fs.writeFile('site-review/browser-checks.json', JSON.stringify(results, null, 2) + '\n');
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
