'use strict';
const fs = require('node:fs');
const path = require('node:path');
const template = fs.readFileSync(path.join(__dirname, '..', 'docs', 'group-announcement.md'), 'utf8');
const target = process.argv[2] || path.join(process.cwd(), 'config', 'group-announcement.md');
fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, template); console.log(`Wrote announcement template to ${target}`);
