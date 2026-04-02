import { StyleSheet, Text, View } from 'react-native';

import {
  currentProductAreas,
  mobileModules,
  mobileRewritePrinciples,
} from '../data/features';
import { Panel } from '../components/Panel';
import { colors } from '../theme';

interface OverviewScreenProps {
  apiBaseUrl: string;
}

export function OverviewScreen({ apiBaseUrl }: OverviewScreenProps) {
  return (
    <>
      <Panel
        title="Rewrite target"
        subtitle="This mobile app mirrors the current product architecture instead of replacing the backend."
      >
        <Text style={styles.body}>
          The existing system is a FastAPI control plane plus a React dashboard for device
          discovery, media streaming, overlay/projection workflows, and runtime diagnostics.
          The mobile rewrite consumes that same backend from a dedicated Expo source tree.
        </Text>
        <Text style={styles.apiLine}>Connected base URL: {apiBaseUrl}</Text>
      </Panel>

      <Panel
        title="Current product areas"
        subtitle="These are the main capabilities already present in the web + Python stack."
      >
        {currentProductAreas.map((item) => (
          <View key={item.title} style={styles.card}>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.body}>{item.description}</Text>
            <Text style={styles.endpointLine}>{item.endpoints.join('  •  ')}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="Mobile modules"
        subtitle="The first rewrite pass focuses on operator workflows with clean backend reuse."
      >
        {mobileModules.map((module) => (
          <View key={module.title} style={styles.card}>
            <Text style={styles.cardTitle}>{module.title}</Text>
            <Text style={styles.body}>{module.description}</Text>
            <Text style={styles.endpointLine}>{module.endpoints.join('  •  ')}</Text>
          </View>
        ))}
      </Panel>

      <Panel title="Rewrite rules">
        {mobileRewritePrinciples.map((principle) => (
          <View key={principle} style={styles.ruleRow}>
            <View style={styles.ruleDot} />
            <Text style={styles.ruleText}>{principle}</Text>
          </View>
        ))}
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  body: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  apiLine: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '600',
  },
  card: {
    gap: 6,
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  endpointLine: {
    color: colors.accent,
    fontSize: 12,
    lineHeight: 18,
  },
  ruleRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
  },
  ruleDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: colors.accent,
    marginTop: 6,
  },
  ruleText: {
    flex: 1,
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
});
