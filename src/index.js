'use strict';

const { loadConfig, validateConfig } = require('./config');
const { createLogger } = require('./logger');
const { AgentRegistry } = require('./registry');
const { TaskStore } = require('./task-store');
const { FeishuClient } = require('./feishu');
const { Coordinator } = require('./coordinator');
const { HealthMonitor } = require('./health');
const { WorkflowRunner } = require('./workflow');
const { createServer } = require('./server');

function createApplication({ config = loadConfig(), logger = createLogger({ level: config.logLevel }), feishu, agents = [] } = {}) {
  const registry = new AgentRegistry();
  for (const agent of agents) registry.register(agent);
  const tasks = new TaskStore();
  const client = feishu || new FeishuClient({ ...config.feishu, logger });
  const health = new HealthMonitor({ registry, intervalMs: config.a2a.healthIntervalSeconds * 1000, check: async (agent) => ({ agent: agent.id, checkedAt: new Date().toISOString() }), logger });
  const coordinator = new Coordinator({ config, registry, tasks, feishu: client, logger, health });
  const server = createServer({ config, coordinator, logger });
  return { config, logger, registry, tasks, feishu: client, coordinator, health, workflow: new WorkflowRunner({ logger }), server };
}

module.exports = { createApplication, loadConfig, validateConfig, AgentRegistry, TaskStore, WorkflowRunner, HealthMonitor, FeishuClient };
