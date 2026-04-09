import type { JsonRecord } from '../../types/api.ts';

export interface ProjectorRedirectRule extends JsonRecord {
  id: string;
  name: string;
  enabled: boolean;
  client_ip: string;
  target_path: string;
}

export interface ProjectorRedirectConfig extends JsonRecord {
  enabled: boolean;
  client_ip: string;
  target_path: string;
  rules: ProjectorRedirectRule[];
}

export const DEFAULT_PROJECTOR_REDIRECT_TARGET =
  '/backend-static/overlay_window.html?config_id=5&controls=hidden';

export function createRedirectRule(index = 1): ProjectorRedirectRule {
  return {
    id: `rule-${index}`,
    name: `Projector ${index}`,
    enabled: index === 1,
    client_ip: '',
    target_path: DEFAULT_PROJECTOR_REDIRECT_TARGET,
  };
}

export function normalizeProjectorRedirectConfig(value: unknown): ProjectorRedirectConfig {
  const record =
    value && typeof value === 'object' && !Array.isArray(value)
      ? (value as JsonRecord)
      : {};
  const rawRules = Array.isArray(record.rules) ? record.rules : [];
  const rules = rawRules.length
    ? rawRules.map((rule, index) => {
        const nextRule =
          rule && typeof rule === 'object' && !Array.isArray(rule) ? (rule as JsonRecord) : {};
        return {
          id: String(nextRule.id ?? `rule-${index + 1}`),
          name: String(nextRule.name ?? `Projector ${index + 1}`),
          enabled: Boolean(nextRule.enabled),
          client_ip: String(nextRule.client_ip ?? ''),
          target_path: String(nextRule.target_path ?? DEFAULT_PROJECTOR_REDIRECT_TARGET),
        };
      })
    : [createRedirectRule()];

  const activeRule = rules.find((rule) => rule.enabled) ?? rules[0];
  return {
    enabled: Boolean(record.enabled ?? activeRule?.enabled),
    client_ip: String(record.client_ip ?? activeRule?.client_ip ?? ''),
    target_path: String(
      record.target_path ?? activeRule?.target_path ?? DEFAULT_PROJECTOR_REDIRECT_TARGET,
    ),
    rules,
  };
}

export function selectPreferredIncidentId(
  snapshot: JsonRecord | null,
  currentIncidentId: string,
  preserveSelection: boolean,
): string {
  const incidentIds = Array.isArray(snapshot?.recent_incidents)
    ? snapshot.recent_incidents
        .map((item) =>
          item && typeof item === 'object' && !Array.isArray(item)
            ? String((item as JsonRecord).incident_id ?? '')
            : '',
        )
        .filter(Boolean)
    : [];

  if (preserveSelection && currentIncidentId && incidentIds.includes(currentIncidentId)) {
    return currentIncidentId;
  }

  return incidentIds[0] ?? '';
}
