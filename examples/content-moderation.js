'use strict';
const { WorkflowRunner } = require('../src/workflow');

async function main() {
  const runner = new WorkflowRunner();
  return runner.run({ id: 'content-moderation', mode: 'parallel', steps: [{ id: 'text-policy' }, { id: 'image-policy' }, { id: 'brand-safety' }] }, { execute: async (step) => ({ completed: `${step.id} checked`, evidence: [`demo://${step.id}`], risks: [] }) });
}
if (require.main === module) main().then((result) => console.log(JSON.stringify(result, null, 2)));
module.exports = { main };
