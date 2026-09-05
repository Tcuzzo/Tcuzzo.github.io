import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = p => readFileSync(new URL(p, import.meta.url), 'utf8');

test('the portrait and keyboard-operable film have separate uncropped treatments', () => {
  const h=read('index.html'), css=read('landing.css');
  assert.match(h, /class="hero-portrait"/);
  assert.match(h, /<details class="hero-film">\s*<summary/);
  assert.match(h, /<video[^>]*controls/);
  assert.match(css, /video:focus-visible/);
  assert.match(css, /video:focus-within/);
  assert.match(css, /object-fit: contain/);
  assert.match(css, /aspect-ratio: var\(--hero-film-ratio\)/);
  assert.doesNotMatch(h, /autoplay|<script\b/);
});

test('the research entry shows existing editorial art without altering the paper', () => {
  const h=read('index.html');
  assert.match(h, /class="research-art"/);
  assert.match(h, /src="research\/figures\/backs-operating-body-editorial.png"/);
  assert.match(h, /Conceptual editorial illustration/);
  assert.equal((read('research/index.html').match(/<figure>/g)||[]).length,24);
});

test('landing additions extend three-tier tokens and reduced-motion rules', () => {
  const tokens=JSON.parse(read('design-tokens.json'));
  assert.ok(tokens.primitive && tokens.semantic && tokens.component);
  assert.ok(tokens.component.landing);
  assert.match(read('landing.css'), /prefers-reduced-motion/);
  assert.match(read('landing-tokens.css'), /--hero-film-ratio/);
  assert.doesNotMatch(read('landing.css'), /#[0-9a-f]{3,8}\b|font-family:\s*["']/i);
});
