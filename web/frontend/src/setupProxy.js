const fs = require('fs');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const BACKEND_TARGET = 'http://localhost:8000';
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
  };

  try {
    if (!fs.existsSync(PROJECTOR_REDIRECT_CONFIG_PATH)) {
      return defaults;
    }
    const raw = fs.readFileSync(PROJECTOR_REDIRECT_CONFIG_PATH, 'utf8');
    const stored = raw ? JSON.parse(raw) : {};
    return {
      ...defaults,
      ...stored,
      enabled: Boolean(stored && stored.enabled),
      client_ip: String((stored && stored.client_ip) || '').trim(),
      target_path: String((stored && stored.target_path) || defaults.target_path).trim() || defaults.target_path,
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
  if (!redirectConfig || !redirectConfig.enabled) {
    return null;
  }

  const configuredClientIp = normalizeIpCandidate(redirectConfig.client_ip);
  if (!configuredClientIp) {
    return null;
  }

  if (!['GET', 'HEAD'].includes(req.method) || !requestTargetsHtmlDocument(req)) {
    return null;
  }

  const clientIp = getRequestClientIp(req);
  if (clientIp !== configuredClientIp) {
    return null;
  }

  const targetPath = String(redirectConfig.target_path || '').trim();
  if (!targetPath || targetMatchesRequest(req, targetPath)) {
    return null;
  }

  return targetPath;
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
  app.use((req, res, next) => {
    const redirectConfig = getProjectorRedirectConfig();
    const redirectTarget = shouldRedirectRequest(req, redirectConfig);
    if (!redirectTarget) {
      next();
      return;
    }

    console.log(
      `Projector redirect: ${getRequestClientIp(req)} ${req.originalUrl || req.url} -> ${redirectTarget}`
    );
    res.redirect(307, redirectTarget);
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
