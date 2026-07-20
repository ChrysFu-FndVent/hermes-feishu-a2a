'use strict';

class HealthMonitor {
  constructor({ registry, check, recover, intervalMs = 60000, logger = console, clock = () => Date.now() }) {
    this.registry = registry; this.check = check; this.recover = recover; this.intervalMs = intervalMs; this.logger = logger; this.clock = clock; this.timer = null;
  }
  async runOnce() {
    const report = [];
    for (const agent of this.registry.list()) {
      try {
        const result = await this.check(agent);
        this.registry.updateStatus(agent.id, 'healthy', { health: result, lastSeenAt: this.clock() });
        report.push({ id: agent.id, status: 'healthy', result });
      } catch (error) {
        this.registry.updateStatus(agent.id, 'unhealthy', { healthError: error.message });
        this.logger.warn?.(`health check failed for ${agent.id}: ${error.message}`);
        let recovered = false;
        if (this.recover) { try { recovered = Boolean(await this.recover(agent, error)); } catch (recoveryError) { this.logger.error?.(`recovery failed for ${agent.id}: ${recoveryError.message}`); } }
        report.push({ id: agent.id, status: 'unhealthy', error: error.message, recovered });
      }
    }
    return report;
  }
  start() { if (this.timer) return; this.timer = setInterval(() => this.runOnce().catch((error) => this.logger.error?.(error)), this.intervalMs); this.timer.unref?.(); }
  stop() { if (this.timer) clearInterval(this.timer); this.timer = null; }
}

module.exports = { HealthMonitor };
