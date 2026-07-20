'use strict';
const { WorkflowRunner } = require('../src/workflow');

async function main() {
  const runner = new WorkflowRunner();
  return runner.run({ id: 'multi-agent-qa', mode: 'parallel', steps: [{ id: 'research' }, { id: 'counterexample' }, { id: 'source-check' }] }, { execute: async (step) => ({ completed: `${step.id} answer`, evidence: [`demo://source/${step.id}`], needsDecision: 'none' }) });
}
if (require.main === module) main().then((result) => console.log(JSON.stringify(result, null, 2)));
module.exports = { main };
