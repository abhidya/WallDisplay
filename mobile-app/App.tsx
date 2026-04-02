import { StatusBar } from 'expo-status-bar';
import { useMemo, useState } from 'react';
import { Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';

import { ScreenLayout } from './src/components/ScreenLayout';
import { colors } from './src/theme';
import { DevicesScreen } from './src/screens/DevicesScreen';
import { MediaScreen } from './src/screens/MediaScreen';
import { OperationsScreen } from './src/screens/OperationsScreen';
import { OverviewScreen } from './src/screens/OverviewScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import {
  DEFAULT_API_BASE_URL,
  NanoDlnaApiClient,
  normalizeApiBaseUrl,
} from './src/services/api';

type TabKey = 'overview' | 'devices' | 'media' | 'operations' | 'settings';

interface TabDefinition {
  key: TabKey;
  label: string;
}

const tabs: TabDefinition[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'devices', label: 'Devices' },
  { key: 'media', label: 'Media' },
  { key: 'operations', label: 'Ops' },
  { key: 'settings', label: 'Settings' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);

  const client = useMemo(() => new NanoDlnaApiClient(apiBaseUrl), [apiBaseUrl]);

  const handleApplyApiBaseUrl = (value: string) => {
    setApiBaseUrl(normalizeApiBaseUrl(value));
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <View style={styles.appShell}>
        <View style={styles.header}>
          <View style={styles.headerTextBlock}>
            <Text style={styles.eyebrow}>nano-dlna mobile rewrite</Text>
            <Text style={styles.title}>Cross-platform operator console</Text>
            <Text style={styles.subtitle}>
              Separate Expo app for iOS and Android, backed by the existing FastAPI
              media-control APIs.
            </Text>
          </View>
          <View style={styles.endpointChip}>
            <Text style={styles.endpointLabel}>API</Text>
            <Text style={styles.endpointValue}>{apiBaseUrl}</Text>
          </View>
        </View>

        <View style={styles.tabBar}>
          {tabs.map((tab) => {
            const isActive = tab.key === activeTab;
            return (
              <Pressable
                key={tab.key}
                accessibilityRole="button"
                onPress={() => setActiveTab(tab.key)}
                style={[styles.tabButton, isActive && styles.activeTabButton]}
              >
                <Text style={[styles.tabLabel, isActive && styles.activeTabLabel]}>
                  {tab.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {activeTab === 'overview' && (
          <ScreenLayout>
            <OverviewScreen apiBaseUrl={apiBaseUrl} />
          </ScreenLayout>
        )}
        {activeTab === 'devices' && (
          <ScreenLayout>
            <DevicesScreen client={client} />
          </ScreenLayout>
        )}
        {activeTab === 'media' && (
          <ScreenLayout>
            <MediaScreen client={client} />
          </ScreenLayout>
        )}
        {activeTab === 'operations' && (
          <ScreenLayout>
            <OperationsScreen client={client} />
          </ScreenLayout>
        )}
        {activeTab === 'settings' && (
          <ScreenLayout>
            <SettingsScreen
              apiBaseUrl={apiBaseUrl}
              onApplyApiBaseUrl={handleApplyApiBaseUrl}
            />
          </ScreenLayout>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  appShell: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 16,
    gap: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.panel,
  },
  headerTextBlock: {
    gap: 6,
  },
  eyebrow: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: '700',
  },
  subtitle: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  endpointChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 4,
  },
  endpointLabel: {
    color: colors.mutedText,
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  endpointValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
  tabBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.panel,
  },
  tabButton: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  activeTabButton: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  tabLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  activeTabLabel: {
    color: '#0a0f19',
  },
});
