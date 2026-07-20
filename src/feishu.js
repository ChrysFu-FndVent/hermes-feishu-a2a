'use strict';

class FeishuClient {
  constructor({ appId, appSecret, domain = 'feishu', fetchImpl = globalThis.fetch, logger = console }) {
    this.appId = appId; this.appSecret = appSecret; this.base = domain === 'lark' ? 'https://open.larksuite.com' : 'https://open.feishu.cn'; this.fetch = fetchImpl; this.logger = logger; this.token = null; this.tokenExpiresAt = 0;
  }
  async tenantToken() {
    if (this.token && Date.now() < this.tokenExpiresAt - 60000) return this.token;
    const response = await this.fetch(`${this.base}/open-apis/auth/v3/tenant_access_token/internal`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ app_id: this.appId, app_secret: this.appSecret }) });
    const json = await response.json(); if (!response.ok || json.code) throw new Error(`tenant token failed: ${json.msg || response.status}`);
    this.token = json.tenant_access_token; this.tokenExpiresAt = Date.now() + Number(json.expire || 7200) * 1000; return this.token;
  }
  async request(method, pathname, body) {
    const token = await this.tenantToken();
    const response = await this.fetch(`${this.base}${pathname}`, { method, headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    const json = await response.json(); if (!response.ok || json.code) throw new Error(`Feishu API ${pathname} failed: ${json.msg || response.status}`); return json;
  }
  async getAnnouncement(chatId) { const json = await this.request('GET', `/open-apis/docx/v1/chats/${encodeURIComponent(chatId)}/announcement/blocks`); return extractBlockText(json.data?.items || json.data?.blocks || []); }
  async sendText(chatId, text) { return this.request('POST', '/open-apis/im/v1/messages?receive_id_type=chat_id', { receive_id: chatId, msg_type: 'text', content: JSON.stringify({ text }) }); }
  async sendMention(chatId, text, targetOpenId) {
    if (!/^ou_/.test(targetOpenId)) throw new Error('targetOpenId must be a Feishu open_id');
    const content = { zh_cn: { content: [{ tag: 'text', text }, { tag: 'at', user_id: targetOpenId, user_name: targetOpenId }] } };
    return this.request('POST', '/open-apis/im/v1/messages?receive_id_type=chat_id', { receive_id: chatId, msg_type: 'post', content: JSON.stringify(content) });
  }
}

function extractBlockText(blocks) {
  const out = [];
  const walk = (node) => {
    if (!node || typeof node !== 'object') return;
    if (node.text_run?.content) out.push(node.text_run.content);
    if (node.text?.content) out.push(node.text.content);
    for (const value of Object.values(node)) { if (value && typeof value === 'object') Array.isArray(value) ? value.forEach(walk) : walk(value); }
  };
  blocks.forEach(walk); return out.join('');
}

module.exports = { FeishuClient, extractBlockText };
