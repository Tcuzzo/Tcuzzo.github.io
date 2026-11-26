import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('the homepage private routing card opens the private source map', () => {
  const home = readFileSync(new URL('index.html', import.meta.url), 'utf8');
  const paper = readFileSync(new URL('research/index.html', import.meta.url), 'utf8');
  const card = [...home.matchAll(/<article\b[^>]*>[\s\S]*?<\/article>/g)]
    .map(match => match[0]).find(article => article.includes('Needle scores roles'));
  assert.ok(card, 'the private routing card must be present');
  assert.match(card, /href="research\/#november-routing"/);
  assert.match(card, /private BACKS source/);
  assert.doesNotMatch(card, /href="hydra\/#routing"/);
  assert.match(paper, /id="november-routing"/);
});
