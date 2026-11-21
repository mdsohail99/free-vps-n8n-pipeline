// Self-check for the daily free-model scan (Node 5) and the reasoning-retry (Node 6).
// Run: node research-engine/tests/test_workflow_models.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert';

const wf = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../ai_daily_briefing_workflow.json');
const src = JSON.parse(fs.readFileSync(wf, 'utf8'));
const js = name => src.nodes.find(n => n.name === name).parameters.jsCode;

const nowStub = {
  toSeconds: () => 1763769600,
  minus: () => ({ toSeconds: () => 1763164800, toFormat: () => '2026-11-15' }),
  toFormat: () => '2026-11-22',
};

async function runNode5(catalog) {
  const fn = new Function('$input', '$now', js('Node 5: Build Pricing Section'));
  const out = await fn({ first: () => ({ json: { data: catalog } }) }, nowStub);
  return out[0].json;
}

const m = (id, prompt, completion, ctx, outs = ['text']) => ({
  id, name: id, created: 1763000000, context_length: ctx,
  pricing: { prompt, completion },
  architecture: { input_modalities: ['text'], output_modalities: outs },
});

// 1. stealth text model wins; music model excluded
let r = await runNode5([
  m('google/lyria-3-pro-preview', '0', '0', 1048576, ['text', 'audio']),
  m('acme/whisper-x-preview', '0', '0', 1000000),
  m('nvidia/nemotron-3.5-super-vl:free', '0', '0', 1000000),
  m('nvidia/nemotron-3.5-lightning:free', '0', '0', 1000000),
  m('big/ctx:free', '0', '0', 2000000),
  m('openrouter/free', '0', '0', 200000),
  m('paid/model', '0.000001', '0.000002', 1000000),
]);
assert.equal(r.freeModels[0], 'acme/whisper-x-preview', 'stealth model must be first');
assert.ok(!r.freeModels.includes('google/lyria-3-pro-preview'), 'music model must be excluded');
assert.ok(!r.freeModels.includes('paid/model'), 'paid model must be excluded');
assert.ok(r.freeModels.length <= 4, 'chain must stay bounded');
assert.ok(r.freeModels.includes('nvidia/nemotron-3.5-super-vl:free'), 'known-good must be in chain');

// 2. no stealth live -> known-good pair leads
r = await runNode5([
  m('nvidia/nemotron-3.5-super-vl:free', '0', '0', 1000000),
  m('nvidia/nemotron-3.5-lightning:free', '0', '0', 1000000),
  m('openrouter/free', '0', '0', 200000),
]);
assert.equal(r.freeModels[0], 'nvidia/nemotron-3.5-super-vl:free');
assert.equal(r.freeModels[1], 'nvidia/nemotron-3.5-lightning:free');

// 3. empty catalog -> still a usable chain (known-good pair, then the router)
r = await runNode5([]);
assert.deepEqual(r.freeModels, ['nvidia/nemotron-3.5-super-vl:free', 'nvidia/nemotron-3.5-lightning:free', 'openrouter/free']);

// ── Node 6: reasoning-retry ──────────────────────────────────────────────────
async function runNode6(handler, freeModels) {
  const calls = [];
  const ctx = {
    helpers: { httpRequest: async opts => { calls.push(opts.body); return handler(opts.body); } },
  };
  const $ = name => {
    if (name.startsWith('Node 2')) return { first: () => ({ json: { isoDate: '2026-11-22' } }) };
    if (name.startsWith('Node 3')) return { first: () => ({ json: { stdout: 'x'.repeat(200) + '===DEALS===deals' } }) };
    if (name.startsWith('Node 5')) return { first: () => ({ json: { pricingSection: 'P', freeModels } }) };
    throw new Error('unexpected node ' + name);
  };
  // arrow so `this` (the n8n execution context) reaches the node body
  const fn = new Function('$', '$env', 'return (async () => {' + js('Node 6: AI Generate Report') + '})()');
  const out = await fn.call(ctx, $, { OPENROUTER_API_KEY: 'k' });
  return { out, calls };
}

const good = '```json\n{"a":1}\n```\n' + 'body '.repeat(60);

// 3a. 400 "Reasoning is mandatory" -> retried with reasoning on, succeeds
let res = await runNode6(body => {
  if (body.reasoning.enabled === false && body.model === 'a:free') {
    throw new Error('400 - {"error":{"message":"Reasoning is mandatory for this model"}}');
  }
  return { choices: [{ message: { content: good } }] };
}, ['a:free', 'b:free']);
assert.equal(res.calls.length, 2, 'must retry exactly once');
assert.deepEqual(res.calls.map(c => c.reasoning.enabled), [false, true]);
assert.equal(res.calls[1].model, 'a:free', 'retry must hit the same model');
assert.ok(res.out[0].json.choices[0].message.content.includes('```json'));

// 3b. other errors skip straight to the next model, no retry
res = await runNode6(body => {
  if (body.model === 'a:free') throw new Error('429 rate limited');
  return { choices: [{ message: { content: good } }] };
}, ['a:free', 'b:free']);
assert.deepEqual(res.calls.map(c => c.model), ['a:free', 'b:free']);
assert.deepEqual(res.calls.map(c => c.reasoning.enabled), [false, false]);

// 3c. all models dead -> clear error, no infinite loop
await assert.rejects(
  runNode6(() => { throw new Error('Reasoning is mandatory'); }, ['a:free', 'b:free']),
  /All fallback models exhausted/,
);

console.log('OK — scan + reasoning-retry self-check passed');
