import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
const read = p => readFileSync(new URL(p, import.meta.url), 'utf8');
test('hero routes to the full research page and public harness', () => {
  const h=read('index.html');
  assert.match(h, /<h1[^>]*>B\.A\.C\.K\.S/);
  assert.match(h, /href="research\/"[^>]*>Read the research/);
  assert.match(h, /href="https:\/\/github.com\/Tcuzzo\/backs-aios-skills"[^>]*>Get the harness/);
  assert.match(h, /<video[^>]*controls/);
  assert.match(h, /src="assets\/backs-hero.mp4"/);
  assert.doesNotMatch(h, /autoplay|System Active|6 Providers|9 Agents|onMFAUnlock|onGuestMode/);
});
test('bottom directory has every inventoried public repo and upstream fork credit', () => {
  const h=read('index.html'), repos=JSON.parse(read('public-repos.json'));
  const footer=h.slice(h.indexOf('id="public-projects"'));
  assert.ok(h.indexOf('id="public-projects"') > h.indexOf('</section>'));
  assert.equal(repos.repositories.length,4);
  for (const repo of repos.repositories) {
    assert.equal(repo.private,false);
    assert.ok(footer.includes(`href="${repo.html_url}"`), repo.name);
  }
  assert.ok(footer.includes('href="https://github.com/calesthio/OpenMontage"'));
  assert.match(footer,/Fork/);
  assert.ok(footer.includes('href="https://github.com/Tcuzzo/tcuzzo.github.io"'));
});
test('full corrected paper preserves chapters, figures, and source credits', () => {
  const h=read('research/index.html');
  assert.equal((h.match(/<figure>/g)||[]).length,24);
  for(const term of ['Matt Pocock','Robert C. Martin','Uncle Bob','Executive Team','Wolf Pack','BUCKS','HydraAgent','References'])assert.ok(h.includes(term),term);
  assert.match(h,/href="\.\.\/#public-projects"/);
  assert.doesNotMatch(h,/Final narrator approval has not yet been issued/);
  for(const match of h.matchAll(/<img[^>]*src="([^"]+)"/g))assert.ok(existsSync(new URL('research/'+match[1],import.meta.url)),match[1]);
});
test('public pages have no executable app or operator-only data links', () => {
  for(const page of ['index.html','research/index.html']){
    const h=read(page);
    assert.doesNotMatch(h,/<script\b|<iframe\b|<form\b|operator_records|AUTHORITY_PROPOSAL|CANONICAL_LEDGER|file:\/\/|\/(?:opt|home|mnt)\//i);
    assert.doesNotMatch(h,/\b(?:192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)\b/);
  }
  assert.ok(existsSync(new URL('.nojekyll',import.meta.url)));
});
test('every public page ships a link-preview card backed by a real 1200x630 image', () => {
  const pages = { 'index.html': 'https://tcuzzo.github.io/', 'research/index.html': 'https://tcuzzo.github.io/research/' };
  for (const [page, canonical] of Object.entries(pages)) {
    const h = read(page);
    const tag = (attr, key) => h.match(new RegExp(`<meta[^>]*(?:${attr}="${key}"[^>]*content="([^"]*)"|content="([^"]*)"[^>]*${attr}="${key}")`));
    for (const key of ['og:title', 'og:description', 'og:url', 'og:image', 'og:type', 'og:image:alt'])
      assert.ok(tag('property', key), `${page} missing ${key}`);
    assert.ok(tag('name', 'twitter:card'), `${page} missing twitter:card`);
    const url = m => (m[1] ?? m[2]);
    assert.equal(url(tag('property', 'og:url')), canonical, `${page} og:url must equal its canonical`);
    // og:image must be absolute https (relative URLs are silently dropped by crawlers)
    // and must resolve to a real PNG on disk at exactly 1200x630.
    const img = url(tag('property', 'og:image'));
    assert.match(img, /^https:\/\/tcuzzo\.github\.io\/assets\/[\w-]+\.png$/, `${page} og:image must be an absolute https URL`);
    const file = new URL(img.replace('https://tcuzzo.github.io/', ''), import.meta.url);
    assert.ok(existsSync(file), `${page} og:image ${img} has no file on disk`);
    const png = readFileSync(file);
    assert.equal(png.toString('ascii', 1, 4), 'PNG', `${img} is not a PNG`);
    assert.equal(png.readUInt32BE(16), 1200, `${img} width must be 1200`);
    assert.equal(png.readUInt32BE(20), 630, `${img} height must be 630`);
    assert.ok(png.length < 5 * 1024 * 1024, `${img} exceeds the 5MB share-card limit`);
    assert.equal(url(tag('property', 'og:image:width')), '1200');
    assert.equal(url(tag('property', 'og:image:height')), '630');
  }
});
