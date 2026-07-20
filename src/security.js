'use strict';

const crypto = require('node:crypto');

function canonicalEnvelope(envelope) {
  return JSON.stringify({
    version: envelope.version,
    kind: envelope.kind,
    taskId: envelope.taskId,
    parentId: envelope.parentId || '',
    chatId: envelope.chatId,
    from: envelope.from,
    to: envelope.to,
    expiresAt: envelope.expiresAt,
    body: envelope.body || {},
  });
}

function signEnvelope(envelope, secret) {
  return crypto.createHmac('sha256', secret).update(canonicalEnvelope(envelope)).digest('hex');
}

function verifyEnvelope(envelope, secret, now = Date.now()) {
  if (!envelope || envelope.version !== 1 || !envelope.sig || !secret) return { ok: false, reason: 'missing_signature' };
  if (Number(envelope.expiresAt) <= now) return { ok: false, reason: 'expired' };
  const expected = signEnvelope(envelope, secret);
  const a = Buffer.from(expected, 'hex');
  const b = Buffer.from(String(envelope.sig), 'hex');
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return { ok: false, reason: 'invalid_signature' };
  return { ok: true };
}

function verifyFeishuSignature({ timestamp, nonce, encrypt, signature }, verificationToken) {
  if (!timestamp || !nonce || !encrypt || !signature || !verificationToken) return false;
  const digest = crypto.createHash('sha1').update(String(timestamp) + String(nonce) + verificationToken + String(encrypt)).digest('hex');
  return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(String(signature)));
}

module.exports = { canonicalEnvelope, signEnvelope, verifyEnvelope, verifyFeishuSignature };
