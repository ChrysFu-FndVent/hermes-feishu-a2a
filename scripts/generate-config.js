'use strict';
const fs = require('node:fs');
const path = require('node:path');
const source = path.join(__dirname, '..', 'config', 'agents.example.json');
const target = process.argv[2] || path.join(process.cwd(), 'config', 'agents.json');
if (fs.existsSync(target) && !process.argv.includes('--force')) { console.error(`${target} exists; use --force to overwrite`); process.exit(1); }
fs.mkdirSync(path.dirname(target), { recursive: true }); fs.copyFileSync(source, target); console.log(`Generated ${target}. Replace every placeholder before use.`);
