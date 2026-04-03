import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_PROJECTOR_REDIRECT_TARGET,
  createRedirectRule,
  normalizeProjectorRedirectConfig,
  selectPreferredIncidentId,
} from '../src/features/settings/useSettingsController.ts';

test('normalizeProjectorRedirectConfig produces a safe editable rule set', () => {
  const normalized = normalizeProjectorRedirectConfig({
    enabled: true,
    rules: [
      {
        id: 'alpha',
        name: 'Front projector',
        enabled: true,
        client_ip: '10.0.0.12',
        target_path: '/docs',
      },
    ],
  });

  assert.equal(normalized.enabled, true);
  assert.equal(normalized.client_ip, '10.0.0.12');
  assert.equal(normalized.target_path, '/docs');
  assert.equal(normalized.rules.length, 1);
  assert.equal(normalized.rules[0]?.id, 'alpha');
});

test('normalizeProjectorRedirectConfig seeds a default rule when payload is empty', () => {
  const normalized = normalizeProjectorRedirectConfig(null);

  assert.equal(normalized.rules.length, 1);
  assert.equal(normalized.rules[0]?.target_path, DEFAULT_PROJECTOR_REDIRECT_TARGET);
  assert.equal(normalized.rules[0]?.enabled, true);
});

test('selectPreferredIncidentId preserves current selection when possible', () => {
  const diagnostics = {
    recent_incidents: [{ incident_id: 'a' }, { incident_id: 'b' }],
  };

  assert.equal(selectPreferredIncidentId(diagnostics, 'b', true), 'b');
  assert.equal(selectPreferredIncidentId(diagnostics, 'z', true), 'a');
  assert.equal(selectPreferredIncidentId(diagnostics, 'b', false), 'a');
});

test('createRedirectRule creates deterministic defaults for mobile editing', () => {
  const rule = createRedirectRule(3);

  assert.equal(rule.id, 'rule-3');
  assert.equal(rule.name, 'Projector 3');
  assert.equal(rule.enabled, false);
  assert.equal(rule.target_path, DEFAULT_PROJECTOR_REDIRECT_TARGET);
});
