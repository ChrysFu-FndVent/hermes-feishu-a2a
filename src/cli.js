'use strict';

const { createApplication, loadConfig, validateConfig } = require('./index');
const fs = require('node:fs');
const path = require('node:path');

const command = process.argv[2] || 'serve';
const config = loadConfig();
if (command === 'config:validate') { const errors = validateConfig(config); if (errors.length) { console.error(errors.join('\n')); process.exitCode = 1; } else console.log('Configuration is valid.'); }
else if (command === 'serve') {
  const errors = validateConfig(config);
  if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
  let agents = [];
  const agentFile = path.join(process.cwd(), 'config', 'agents.json');
  if (fs.existsSync(agentFile)) agents = JSON.parse(fs.readFileSync(agentFile, 'utf8')).agents || [];
  const app = createApplication({ config, agents });
  app.server.listen(config.server.port, config.server.host, () => console.log(`Hermes Feishu A2A listening on http://${config.server.host}:${config.server.port}`));
  app.health.start();
  const stop = () => { app.health.stop(); app.server.close(() => process.exit(0)); };
  process.on('SIGINT', stop); process.on('SIGTERM', stop);
} else { console.error(`Unknown command: ${command}`); process.exitCode = 1; }
