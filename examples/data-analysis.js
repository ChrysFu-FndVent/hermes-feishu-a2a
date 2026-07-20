'use strict';
const { WorkflowRunner } = require('../src/workflow');

async function main() {
  const runner = new WorkflowRunner();
  return runner.run({ id: 'data-analysis', mode: 'serial', steps: [{ id: 'clean' }, { id: 'analyze' }, { id: 'review' }] }, { execute: async (step, prior) => ({ completed: `${step.id} complete`, evidence: [`rows:${prior.length}`], risks: step.id === 'review' ? ['demo result requires human review'] : [] }) });
}
if (require.main === module) main().then((result) => console.log(JSON.stringify(result, null, 2)));
module.exports = { main };
