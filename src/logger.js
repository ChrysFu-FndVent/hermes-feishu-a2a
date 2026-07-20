'use strict';

function createLogger({ level = 'info', sink = console } = {}) {
  const levels = { debug: 10, info: 20, warn: 30, error: 40 };
  const threshold = levels[level] ?? levels.info;
  function write(name, args) {
    if (levels[name] < threshold) return;
    const line = `[${new Date().toISOString()}] ${name.toUpperCase()}`;
    (sink[name] || sink.log).call(sink, line, ...args);
  }
  return { debug: (...args) => write('debug', args), info: (...args) => write('info', args), warn: (...args) => write('warn', args), error: (...args) => write('error', args) };
}

module.exports = { createLogger };
