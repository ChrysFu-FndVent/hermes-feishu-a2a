'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { loadConfig, validateConfig } = require('../src/config');
const config = loadConfig();
const hasRuntimeSecret = Boolean(process.env.A2A_SIGNING_SECRET && process.env.A2A_SIGNING_SECRET.length >= 32);
const errors = hasRuntimeSecret ? validateConfig(config, { requireFeishu: false }) : [];
if (!hasRuntimeSecret) console.warn('No runtime A2A_SIGNING_SECRET found; validating file structure only.');
const file = process.argv[2] || path.join(process.cwd(), 'config/agents.example.json');
try {
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!data.group?.id?.startsWith('oc_')) errors.push('group.id must be an open chat ID beginning with oc_');
  const ids = new Set(); for (const agent of data.agents || []) { if (ids.has(agent.id)) errors.push(`duplicate agent id: ${agent.id}`); ids.add(agent.id); if (!file.endsWith('agents.example.json') && (!agent.openId?.startsWith('ou_') || agent.openId.includes('replace'))) errors.push(`replace ${agent.id}.openId with a real ou_ value`); }
} catch (error) { errors.push(`cannot read ${file}: ${error.message}`); }
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
console.log('Configuration structure is valid.');
