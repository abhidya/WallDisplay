const fs = require('fs');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const BACKEND_TARGET = 'http://localhost:8000';
const RECENT_PROJECTOR_REQUEST_LIMIT = 100;
const recentProjectorRequests = [];
const PROJECTOR_REDIRECT_CONFIG_PATH = path.resolve(
  __dirname,
  '../../backend/uploads/env.overlay_projector_redirect.json'
);

function normalizeIpCandidate(value) {
  let candidate = String(value || '').trim().replace(/^["']|["']$/g, '');
  if (!candidate) {
    return '';
  }
  if (candidate.toLowerCase().startsWith('for=')) {
    candidate = candidate.slice(4).trim().replace(/^["']|["']$/g, '');
  }
  if (candidate.startsWith('[') && candidate.includes(']')) {
    candidate = candidate.slice(1, candidate.indexOf(']'));
  } else if ((candidate.match(/:/g) || []).length === 1 && candidate.includes('.')) {
    candidate = candidate.slice(0, candidate.lastIndexOf(':'));
  }
  if (candidate.startsWith('::ffff:')) {
    candidate = candidate.slice(7);
  }
  return candidate;
}

function getRequestClientIp(req) {
  const forwardedFor = req.headers['x-forwarded-for'];
  if (typeof forwardedFor === 'string' && forwardedFor.trim()) {
    for (const value of forwardedFor.split(',')) {
      const candidate = normalizeIpCandidate(value);
      if (candidate && candidate.toLowerCase() !== 'unknown') {
        return candidate;
      }
    }
  }

  const forwarded = req.headers.forwarded;
  if (typeof forwarded === 'string' && forwarded.trim()) {
    for (const entry of forwarded.split(',')) {
      for (const part of entry.split(';')) {
        const trimmed = part.trim();
        if (trimmed.toLowerCase().startsWith('for=')) {
          const candidate = normalizeIpCandidate(trimmed);
          if (candidate && candidate.toLowerCase() !== 'unknown') {
            return candidate;
          }
        }
      }
    }
  }

  const realIp = normalizeIpCandidate(req.headers['x-real-ip']);
  if (realIp) {
    return realIp;
  }

  return normalizeIpCandidate(req.socket && req.socket.remoteAddress);
}

function requestTargetsHtmlDocument(req) {
  const secFetchDest = String(req.headers['sec-fetch-dest'] || '').toLowerCase();
  if (['document', 'iframe', 'frame'].includes(secFetchDest)) {
    return true;
  }

  const secFetchMode = String(req.headers['sec-fetch-mode'] || '').toLowerCase();
  if (secFetchMode === 'navigate') {
    return true;
  }

  const accept = String(req.headers.accept || '').toLowerCase();
  return accept.includes('text/html');
}

function getProjectorRedirectConfig() {
  const defaults = {
    enabled: false,
    client_ip: '',
    target_path: '/backend-static/overlay_window.html?config_id=5&controls=hidden',
    rules: [],
  };

  try {
    if (!fs.existsSync(PROJECTOR_REDIRECT_CONFIG_PATH)) {
      return defaults;
    }
    const raw = fs.readFileSync(PROJECTOR_REDIRECT_CONFIG_PATH, 'utf8');
    const stored = raw ? JSON.parse(raw) : {};
    const merged = {
      ...defaults,
      ...stored,
    };
    const rules = Array.isArray(merged.rules) && merged.rules.length
      ? merged.rules
      : [{
        id: 'rule-1',
        name: 'Default projector',
        enabled: Boolean(merged.enabled),
        client_ip: String(merged.client_ip || '').trim(),
        target_path: String(merged.target_path || defaults.target_path).trim() || defaults.target_path,
      }];
    const primaryRule = rules.find((rule) => rule && rule.enabled) || rules[0];
    return {
      ...merged,
      enabled: Boolean(primaryRule && primaryRule.enabled),
      client_ip: String((primaryRule && primaryRule.client_ip) || '').trim(),
      target_path: String((primaryRule && primaryRule.target_path) || defaults.target_path).trim() || defaults.target_path,
      rules: rules.map((rule, index) => ({
        id: String((rule && rule.id) || `rule-${index + 1}`),
        name: String((rule && rule.name) || `Projector ${index + 1}`),
        enabled: Boolean(rule && rule.enabled),
        client_ip: String((rule && rule.client_ip) || '').trim(),
        target_path: String((rule && rule.target_path) || defaults.target_path).trim() || defaults.target_path,
      })),
    };
  } catch (error) {
    console.warn('Failed to read projector redirect config:', error.message);
    return defaults;
  }
}

function targetMatchesRequest(req, targetPath) {
  try {
    const targetUrl = new URL(targetPath, 'http://localhost');
    const requestUrl = new URL(req.originalUrl || req.url || '/', 'http://localhost');
    return requestUrl.pathname === targetUrl.pathname && requestUrl.search === targetUrl.search;
  } catch (error) {
    return false;
  }
}

function shouldRedirectRequest(req, redirectConfig) {
  if (!redirectConfig) {
    return null;
  }

  if (!['GET', 'HEAD'].includes(req.method) || !requestTargetsHtmlDocument(req)) {
    return null;
  }

  const clientIp = getRequestClientIp(req);
  const rules = Array.isArray(redirectConfig.rules) && redirectConfig.rules.length
    ? redirectConfig.rules
    : [{
      name: 'Default projector',
      enabled: Boolean(redirectConfig.enabled),
      client_ip: redirectConfig.client_ip,
      target_path: redirectConfig.target_path,
    }];
  for (const rule of rules) {
    if (!rule || !rule.enabled) {
      continue;
    }
    const configuredClientIp = normalizeIpCandidate(rule.client_ip);
    if (!configuredClientIp || clientIp !== configuredClientIp) {
      continue;
    }
    const targetPath = String(rule.target_path || '').trim();
    if (!targetPath || targetMatchesRequest(req, targetPath)) {
      continue;
    }
    return {
      targetPath,
      ruleName: String(rule.name || '').trim() || 'Projector redirect',
    };
  }
  return null;
}

function recordProjectorRequest(req, redirectMatch) {
  recentProjectorRequests.unshift({
    timestamp: new Date().toISOString(),
    client_ip: getRequestClientIp(req),
    method: req.method,
    path: req.path || req.originalUrl || req.url || '',
    query: req.query ? new URLSearchParams(req.query).toString() : '',
    matched_rule_name: redirectMatch ? redirectMatch.ruleName : '',
    redirect_target: redirectMatch ? redirectMatch.targetPath : '',
    redirected: Boolean(redirectMatch),
  });
  if (recentProjectorRequests.length > RECENT_PROJECTOR_REQUEST_LIMIT) {
    recentProjectorRequests.length = RECENT_PROJECTOR_REQUEST_LIMIT;
  }
}

function createBackendProxy(options = {}) {
  return createProxyMiddleware({
    target: BACKEND_TARGET,
    changeOrigin: true,
    xfwd: true,
    ...options,
  });
}

module.exports = function setupProxy(app) {
  app.get('/api/overlay/projector-redirect/recent', (req, res) => {
    const limit = Math.max(1, Math.min(Number(req.query.limit) || 50, RECENT_PROJECTOR_REQUEST_LIMIT));
    res.json({
      items: recentProjectorRequests.slice(0, limit),
    });
  });

  app.use((req, res, next) => {
    const redirectConfig = getProjectorRedirectConfig();
    const redirectMatch = shouldRedirectRequest(req, redirectConfig);
    if (['GET', 'HEAD'].includes(req.method) && requestTargetsHtmlDocument(req)) {
      recordProjectorRequest(req, redirectMatch);
    }
    if (!redirectMatch) {
      next();
      return;
    }

    console.log(
      `Projector redirect: ${getRequestClientIp(req)} ${req.originalUrl || req.url} -> ${redirectMatch.targetPath}`
    );
    res.redirect(307, redirectMatch.targetPath);
  });

  app.use('/api', createBackendProxy());

  app.use('/docs', createBackendProxy());

  app.use('/redoc', createBackendProxy());

  app.use('/openapi.json', createBackendProxy());

  app.use(
    '/backend-static',
    createBackendProxy({
      pathRewrite: {
        '^/backend-static': '/static',
      },
    })
  );
};
