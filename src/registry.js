'use strict';

class AgentRegistry {
  constructor({ clock = () => Date.now() } = {}) {
    this.clock = clock;
    this.agents = new Map();
  }

  register(agent) {
    if (!agent || !agent.id || !agent.name || !agent.openId || !agent.role) throw new Error('agent requires id, name, openId and role');
    if (!/^ou_/.test(agent.openId)) throw new Error('agent.openId must be a Feishu open_id');
    const existing = this.agents.get(agent.id);
    const record = { ...existing, ...agent, status: agent.status || existing?.status || 'unknown', lastSeenAt: agent.lastSeenAt || existing?.lastSeenAt || null, updatedAt: this.clock() };
    this.agents.set(agent.id, record);
    return { ...record };
  }

  remove(id) { return this.agents.delete(id); }
  get(id) { return this.agents.has(id) ? { ...this.agents.get(id) } : null; }
  list({ chatId, role } = {}) { return [...this.agents.values()].filter((a) => (!chatId || a.chatId === chatId) && (!role || a.role === role)).map((a) => ({ ...a })); }
  findByOpenId(openId) { return [...this.agents.values()].find((a) => a.openId === openId) || null; }
  updateStatus(id, status, details = {}) {
    const agent = this.agents.get(id);
    if (!agent) throw new Error(`unknown agent: ${id}`);
    Object.assign(agent, details, { status, lastSeenAt: this.clock(), updatedAt: this.clock() });
    return { ...agent };
  }
}

module.exports = { AgentRegistry };
