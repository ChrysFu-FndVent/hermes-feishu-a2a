'use strict';

const transitions = {
  queued: new Set(['running', 'cancelled', 'timed_out']),
  running: new Set(['succeeded', 'failed', 'cancelled', 'timed_out']),
  succeeded: new Set(['accepted', 'failed']),
  failed: new Set(['queued', 'cancelled']),
  timed_out: new Set(['queued', 'cancelled']),
  accepted: new Set(['co_reviewed', 'queued']),
  co_reviewed: new Set(['delivery_authorized', 'queued']),
  delivery_authorized: new Set(['delivered']),
  delivered: new Set(),
  cancelled: new Set(),
};

class TaskStore {
  constructor({ clock = () => Date.now() } = {}) { this.clock = clock; this.tasks = new Map(); this.events = []; }
  create(input) {
    if (!input.id || !input.chatId || !input.assignee) throw new Error('task requires id, chatId and assignee');
    if (this.tasks.has(input.id)) throw new Error(`duplicate task: ${input.id}`);
    const task = { ...input, status: 'queued', createdAt: this.clock(), updatedAt: this.clock(), attempts: 0 };
    this.tasks.set(task.id, task); this.events.push({ type: 'created', taskId: task.id, at: this.clock() }); return { ...task };
  }
  get(id) { return this.tasks.has(id) ? { ...this.tasks.get(id) } : null; }
  list() { return [...this.tasks.values()].map((task) => ({ ...task })); }
  transition(id, status, patch = {}) {
    const task = this.tasks.get(id); if (!task) throw new Error(`unknown task: ${id}`);
    if (!transitions[task.status]?.has(status)) throw new Error(`invalid transition ${task.status} -> ${status}`);
    const from = task.status;
    Object.assign(task, patch, { status, updatedAt: this.clock() });
    this.events.push({ type: 'transition', taskId: id, from, to: status, at: this.clock(), patch });
    return { ...task };
  }
  incrementAttempt(id) { const task = this.tasks.get(id); if (!task) throw new Error(`unknown task: ${id}`); task.attempts += 1; task.updatedAt = this.clock(); return task.attempts; }
  eventsFor(id) { return this.events.filter((event) => event.taskId === id).map((event) => ({ ...event })); }
}

module.exports = { TaskStore, transitions };
