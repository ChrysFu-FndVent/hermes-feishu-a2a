'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { AgentRegistry } = require('../src/registry');
const { TaskStore } = require('../src/task-store');
const { WorkflowRunner } = require('../src/workflow');
const { signEnvelope, verifyEnvelope } = require('../src/security');
const { extractBlockText } = require('../src/feishu');
const { HealthMonitor } = require('../src/health');

test('registry registers and updates agent health', () => {
  const registry = new AgentRegistry({ clock: () => 100 });
  registry.register({ id: 'qoder', name: 'Qoder', openId: 'ou_qoder', role: 'member', chatId: 'oc_demo' });
  assert.equal(registry.get('qoder').status, 'unknown');
  registry.updateStatus('qoder', 'healthy');
  assert.equal(registry.findByOpenId('ou_qoder').status, 'healthy');
});

test('task store enforces lifecycle transitions and records events', () => {
  const store = new TaskStore({ clock: () => 100 });
  store.create({ id: 'tsk_1', chatId: 'oc_demo', assignee: 'qoder' });
  store.transition('tsk_1', 'running'); store.transition('tsk_1', 'succeeded', { completed: 'done' });
  assert.equal(store.get('tsk_1').status, 'succeeded');
  assert.equal(store.eventsFor('tsk_1')[1].from, 'queued');
  assert.throws(() => store.transition('tsk_1', 'delivered'), /invalid transition/);
});

test('workflow runner supports serial and parallel modes', async () => {
  const runner = new WorkflowRunner();
  const serial = await runner.run({ id: 'serial', mode: 'serial', steps: [{ id: 'a' }, { id: 'b' }] }, { execute: async (step, prior) => ({ completed: step.id, evidence: prior.length }) });
  assert.deepEqual(serial.results.map((r) => r.completed), ['a', 'b']);
  assert.equal(serial.results[1].evidence, 1);
  const parallel = await runner.run({ mode: 'parallel', steps: [{ id: 'a' }, { id: 'b' }] }, { execute: async (step) => ({ completed: step.id }) });
  assert.equal(parallel.results.length, 2);
});

test('signed envelopes reject tampering and expired messages', () => {
  const envelope = { version: 1, kind: 'task', taskId: 'tsk_1', chatId: 'oc_demo', from: 'ou_h', to: 'ou_q', expiresAt: Date.now() + 1000, body: { objective: 'x' } };
  const signed = { ...envelope, sig: signEnvelope(envelope, 'a'.repeat(32)) };
  assert.equal(verifyEnvelope(signed, 'a'.repeat(32)).ok, true);
  assert.equal(verifyEnvelope({ ...signed, body: { objective: 'tampered' } }, 'a'.repeat(32)).reason, 'invalid_signature');
  assert.equal(verifyEnvelope(signed, 'a'.repeat(32), Date.now() + 2000).reason, 'expired');
});

test('announcement block extraction collects nested text runs', () => {
  assert.equal(extractBlockText([{ block: { text_run: { content: 'AAA' } } }, { text_run: { content: '工作群' } }]), 'AAA工作群');
});

test('health monitor marks failures and invokes recovery', async () => {
  const registry = new AgentRegistry(); registry.register({ id: 'a', name: 'A', openId: 'ou_a', role: 'member' });
  let recovered = false;
  const monitor = new HealthMonitor({ registry, check: async () => { throw new Error('offline'); }, recover: async () => { recovered = true; return true; }, intervalMs: 100000 });
  const report = await monitor.runOnce();
  assert.equal(report[0].status, 'unhealthy'); assert.equal(report[0].recovered, true); assert.equal(recovered, true); assert.equal(registry.get('a').status, 'unhealthy');
});
