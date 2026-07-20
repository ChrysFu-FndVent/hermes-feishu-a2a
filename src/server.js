'use strict';

const http = require('node:http');
const { verifyFeishuSignature } = require('./security');

function createServer({ config, coordinator, logger = console }) {
  return http.createServer(async (req, res) => {
    try {
      if (req.method === 'GET' && req.url === '/healthz') return json(res, 200, { ok: true, ...coordinator.snapshot() });
      if (req.method !== 'POST' || req.url !== '/webhook/feishu') return json(res, 404, { error: 'not_found' });
      const payload = await readJson(req);
      if (payload.challenge) return json(res, 200, { challenge: payload.challenge });
      const headers = Object.fromEntries(Object.entries(req.headers).map(([key, value]) => [key.toLowerCase(), value]));
      if (config.feishu.verificationToken && headers['x-lark-signature'] && !verifyFeishuSignature({ timestamp: headers['x-lark-request-timestamp'], nonce: headers['x-lark-request-nonce'], encrypt: headers['x-lark-request-body'], signature: headers['x-lark-signature'] }, config.feishu.verificationToken)) return json(res, 401, { error: 'invalid_signature' });
      const event = payload.event || payload;
      logger.info?.('received Feishu event', event.header?.event_type || event.type || 'unknown');
      return json(res, 200, { ok: true });
    } catch (error) { logger.error?.(error); return json(res, 500, { error: 'internal_error' }); }
  });
}
function readJson(req) { return new Promise((resolve, reject) => { let data = ''; req.on('data', (chunk) => { data += chunk; if (data.length > 2e6) reject(new Error('payload too large')); }); req.on('end', () => { try { resolve(data ? JSON.parse(data) : {}); } catch (error) { reject(error); } }); req.on('error', reject); }); }
function json(res, status, body) { res.writeHead(status, { 'content-type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(body)); }
module.exports = { createServer };
