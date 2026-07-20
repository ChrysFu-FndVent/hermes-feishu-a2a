'use strict';

class WorkflowRunner {
  constructor({ logger = console } = {}) { this.logger = logger; }

  async run(definition, context = {}) {
    if (!definition || !Array.isArray(definition.steps) || !definition.steps.length) throw new Error('workflow requires at least one step');
    const execute = async (step, prior) => {
      if (typeof context.execute !== 'function') throw new Error('workflow context.execute is required');
      return context.execute(step, prior);
    };
    let results = [];
    if (definition.mode === 'parallel') {
      results = await Promise.all(definition.steps.map((step) => execute(step, [])));
    } else {
      let prior = [];
      for (const step of definition.steps) { const result = await execute(step, prior); results.push(result); prior = [...results]; }
    }
    return { workflowId: definition.id || null, mode: definition.mode || 'serial', results, summary: this.aggregate(results) };
  }

  aggregate(results) {
    return results.reduce((acc, result) => {
      const value = result && typeof result === 'object' ? result : { completed: result };
      acc.completed.push(value.completed || value.output || '');
      acc.evidence.push(...(Array.isArray(value.evidence) ? value.evidence : value.evidence ? [value.evidence] : []));
      acc.risks.push(...(Array.isArray(value.risks) ? value.risks : value.risks ? [value.risks] : []));
      if (value.needsDecision && value.needsDecision !== 'none') acc.needsDecision.push(value.needsDecision);
      return acc;
    }, { completed: [], evidence: [], risks: [], needsDecision: [] });
  }
}

module.exports = { WorkflowRunner };
