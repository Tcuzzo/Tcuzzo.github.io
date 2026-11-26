import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
const read = p => readFileSync(new URL(p, import.meta.url), 'utf8');
const privateContract = /HYDRA_BACKS_URL|BACKS_ENDPOINT|BACKS_DEPLOY_ROOT|\.env\.backs|backs-host|needle-url|\/api\/router\/|BACKS decision service|BACKS IDE Auto|Fleet asks/i;

test('public Hydra prose, chart sources and rendered charts contain no private integration instructions', () => {
  for (const dir of ['hydra/charts', 'hydra/figures']) {
    for (const file of readdirSync(new URL(dir + '/', import.meta.url))) {
      if (!/\.(mmd|svg)$/.test(file)) continue;
      assert.doesNotMatch(read(dir + '/' + file), privateContract, dir + '/' + file);
    }
  }
  assert.doesNotMatch(read('hydra/index.html'), privateContract);
});

test('private routing is scoped to research with its own chart and source boundary', () => {
  const paper = read('research/index.html');
  assert.match(paper, /src="figures\/diagram-private-routing-20261125\.svg"/);
  assert.ok(existsSync(new URL('research/charts/private-routing.mmd', import.meta.url)));
  assert.ok(existsSync(new URL('research/figures/diagram-private-routing-20261125.svg', import.meta.url)));
  const section = paper.slice(paper.indexOf('id="november-routing"'), paper.indexOf('<h2>9'));
  assert.doesNotMatch(section, /Public Hydra<\/strong>[\s\S]*?<\/tr>/);
  assert.doesNotMatch(section, /href="\.\.\/hydra\/#routing"/);
  assert.match(section, /private source/i);
  assert.match(section, /not a live/i);
});
