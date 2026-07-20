'use strict';

const crypto = require('node:crypto');
const { signEnvelope, verifyEnvelope } = require('./security');

class Coordinator {
  constructor({ config, registry, tasks, feishu, logger = console, health }) { this.config = config; this.registry = registry; this.tasks = tasks; this.feishu = feishu; this.logger = logger; this.health = health; this.processed = new Set(); }
  createEnvelope({ kind = 'task', taskId, parentId = '', chatId, from, to, body }) {
    const envelope = { version: 1, kind, taskId, parentId, chatId, from, to, expiresAt: Date.now() + this.config.a2a.taskTtlSeconds * 1000, body };
    return { ...envelope, sig: signEnvelope(envelope, this.config.a2a.signingSecret) };
  }
  async delegate({ chatId, from = 'hermes', to, objective, expectedResult, mode = 'serial', steps = [] }) {
    const agent = this.registry.get(to); if (!agent) throw new Error(`unknown target agent: ${to}`);
    const taskId = `tsk_${crypto.randomBytes(8).toString('hex')}`;
    const task = this.tasks.create({ id: taskId, chatId, assignee: to, requester: from, objective, expectedResult, mode, steps });
    const envelope = this.createEnvelope({ taskId, chatId, from, to: agent.openId, body: { objective, expectedResult, mode, steps } });
    await this.feishu.sendMention(chatId, `[H-A2A v1 task=${taskId}] ${objective}`, agent.openId);
    this.tasks.transition(taskId, 'running');
    return { task, envelope };
  }
  acceptEnvelope(envelope, { senderOpenId, chatId }) {
    if (this.processed.has(envelope.taskId)) return { ok: false, reason: 'duplicate' };
    const verification = verifyEnvelope(envelope, this.config.a2a.signingSecret);
    if (!verification.ok) return verification;
    const sender = this.registry.findByOpenId(senderOpenId);
    if (!sender || sender.openId !== envelope.from || sender.chatId !== chatId) return { ok: false, reason: 'unregistered_sender' };
    this.processed.add(envelope.taskId); return { ok: true, sender };
  }
  async report({ taskId, status, completed, evidence = [], risks = [], needsDecision = 'none' }) {
    const task = this.tasks.get(taskId); if (!task) throw new Error('unknown task');
    const target = this.registry.get(task.requester); if (!target) throw new Error('requester is not registered');
    const next = status === 'completed' ? 'succeeded' : status === 'blocked' ? 'failed' : 'failed';
    const updated = this.tasks.transition(taskId, next, { completed, evidence, risks, needsDecision });
    await this.feishu.sendMention(task.chatId, `[H-A2A v1 result=${taskId}] ${completed}`, target.openId);
    return updated;
  }
  snapshot() { return { agents: this.registry.list(), tasks: this.tasks.list(), health: this.health ? 'running' : 'disabled' }; }
}

module.exports = { Coordinator };
