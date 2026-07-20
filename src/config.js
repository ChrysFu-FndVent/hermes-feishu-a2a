'use strict';

const fs = require('node:fs');
const path = require('node:path');

function loadDotEnv(file = path.join(process.cwd(), '.env')) {
  if (!fs.existsSync(file)) return {};
  const values = {};
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
    if (!match || match[1].startsWith('#')) continue;
    values[match[1]] = match[2].replace(/^['"]|['"]$/g, '');
  }
  return values;
}

function envValue(env, dotEnv, key, fallback = '') {
  return env[key] ?? dotEnv[key] ?? fallback;
}

function loadConfig({ env = process.env, dotEnvFile } = {}) {
  const dotEnv = loadDotEnv(dotEnvFile);
  const toInt = (key, fallback) => Number.parseInt(envValue(env, dotEnv, key, fallback), 10);
  return {
    server: {
      host: envValue(env, dotEnv, 'HOST', '127.0.0.1'),
      port: toInt('PORT', 8787),
      nodeEnv: envValue(env, dotEnv, 'NODE_ENV', 'development'),
    },
    feishu: {
      domain: envValue(env, dotEnv, 'FEISHU_DOMAIN', 'feishu'),
      appId: envValue(env, dotEnv, 'FEISHU_APP_ID'),
      appSecret: envValue(env, dotEnv, 'FEISHU_APP_SECRET'),
      encryptKey: envValue(env, dotEnv, 'FEISHU_ENCRYPT_KEY'),
      verificationToken: envValue(env, dotEnv, 'FEISHU_VERIFICATION_TOKEN'),
      defaultChatId: envValue(env, dotEnv, 'FEISHU_DEFAULT_CHAT_ID'),
    },
    a2a: {
      signingSecret: envValue(env, dotEnv, 'A2A_SIGNING_SECRET'),
      taskTtlSeconds: toInt('A2A_TASK_TTL_SECONDS', 900),
      maxRetries: toInt('A2A_MAX_RETRIES', 2),
      healthIntervalSeconds: toInt('A2A_HEALTH_INTERVAL_SECONDS', 60),
      allowedHumanOpenIds: envValue(env, dotEnv, 'A2A_ALLOWED_HUMAN_OPEN_IDS')
        .split(',').map((value) => value.trim()).filter(Boolean),
    },
    logLevel: envValue(env, dotEnv, 'LOG_LEVEL', 'info'),
  };
}

function validateConfig(config, { requireFeishu = true } = {}) {
  const errors = [];
  if (!Number.isInteger(config.server.port) || config.server.port < 1 || config.server.port > 65535) errors.push('PORT must be an integer between 1 and 65535');
  if (!config.a2a.signingSecret || config.a2a.signingSecret.length < 32 || /replace|change|example/i.test(config.a2a.signingSecret)) errors.push('A2A_SIGNING_SECRET must be a random secret of at least 32 characters');
  if (config.a2a.taskTtlSeconds < 1 || config.a2a.taskTtlSeconds > 86400) errors.push('A2A_TASK_TTL_SECONDS must be between 1 and 86400');
  if (config.a2a.maxRetries < 0 || config.a2a.maxRetries > 10) errors.push('A2A_MAX_RETRIES must be between 0 and 10');
  if (requireFeishu) {
    for (const key of ['appId', 'appSecret', 'encryptKey', 'verificationToken']) {
      if (!config.feishu[key] || /replace|xxxxxxxx|example/i.test(config.feishu[key])) errors.push(`FEISHU_${key.replace(/[A-Z]/g, (m) => `_${m}`).toUpperCase()} is required`);
    }
  }
  return errors;
}

module.exports = { loadConfig, loadDotEnv, validateConfig };
