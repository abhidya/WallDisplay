import { StatusBar } from 'expo-status-bar';
import { Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';

import { ScreenLayout } from './src/components/ScreenLayout';
import { useAppShell, tabs } from './src/features/app/useAppShell';
import { DevicesScreen } from './src/screens/DevicesScreen';
import { DepthProcessingScreen } from './src/screens/DepthProcessingScreen';
import { MediaScreen } from './src/screens/MediaScreen';
import { LogsScreen } from './src/screens/LogsScreen';
import { OperationsScreen } from './src/screens/OperationsScreen';
import { OverlayProjectionScreen } from './src/screens/OverlayProjectionScreen';
import { OverviewScreen } from './src/screens/OverviewScreen';
import { ProjectionAnimationScreen } from './src/screens/ProjectionAnimationScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { StructuredLightingScreen } from './src/screens/StructuredLightingScreen';
import { colors } from './src/theme';

export default function App() {
  const {
    activeTab,
    appMode,
    apiBaseUrl,
    client,
    hydrated,
    selectedDeviceId,
    selectedDeviceLabel,
    setActiveTab,
    applyApiBaseUrl,
    applyAppMode,
    selectDevice,
  } = useAppShell();

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />
      <View style={styles.appShell}>
        <View style={styles.header}>
          <View style={styles.headerTextBlock}>
            <Text style={styles.eyebrow}>WallDisplay Ops</Text>
            <Text style={styles.title}>Mobile operator console</Text>
            <Text style={styles.subtitle}>
              Local-first controls for devices, media, projection, overlay casting, diagnostics, and structured-lighting workflows.
            </Text>
          </View>
          <View style={styles.headerMetaRow}>
            <View style={[styles.endpointChip, appMode === 'local' && styles.localModeChip]}>
              <Text style={styles.endpointLabel}>Mode</Text>
              <Text style={styles.endpointValue}>{appMode}</Text>
            </View>
            {appMode === 'remote' ? (
              <View style={styles.endpointChip}>
                <Text style={styles.endpointLabel}>Fallback API</Text>
                <Text style={styles.endpointValue}>{apiBaseUrl}</Text>
              </View>
            ) : null}
            {selectedDeviceLabel ? (
              <View style={styles.selectionChip}>
                <Text style={styles.selectionChipLabel}>Target</Text>
                <Text style={styles.selectionChipValue}>
                  {selectedDeviceLabel} ({String(selectedDeviceId)})
                </Text>
              </View>
            ) : null}
          </View>
        </View>

        <View style={styles.tabBar}>
          {tabs.map((tab) => {
            const isActive = tab.key === activeTab;
            return (
              <Pressable
                key={tab.key}
                accessibilityRole="button"
                accessibilityLabel={`Open ${tab.label}`}
                accessibilityState={{ selected: isActive }}
                hitSlop={4}
                onPress={() => setActiveTab(tab.key)}
                style={({ pressed }) => [
                  styles.tabButton,
                  isActive && styles.activeTabButton,
                  pressed && styles.pressedTabButton,
                ]}
              >
                <Text style={[styles.tabLabel, isActive && styles.activeTabLabel]}>{tab.label}</Text>
              </Pressable>
            );
          })}
        </View>

        {activeTab === 'overview' && (
          <ScreenLayout>
            <OverviewScreen apiBaseUrl={apiBaseUrl} appMode={appMode} client={client} />
          </ScreenLayout>
        )}
        {activeTab === 'devices' && (
          <ScreenLayout>
            <DevicesScreen
              appMode={appMode}
              client={client}
              selectedDeviceId={selectedDeviceId}
              onSelectDevice={selectDevice}
            />
          </ScreenLayout>
        )}
        {activeTab === 'media' && (
          <ScreenLayout>
            <MediaScreen
              appMode={appMode}
              client={client}
              selectedDeviceId={selectedDeviceId}
              selectedDeviceLabel={selectedDeviceLabel}
            />
          </ScreenLayout>
        )}
        {activeTab === 'operations' && (
          <ScreenLayout>
            <OperationsScreen appMode={appMode} client={client} />
          </ScreenLayout>
        )}
        {activeTab === 'lighting' && (
          <ScreenLayout>
            <StructuredLightingScreen apiBaseUrl={apiBaseUrl} appMode={appMode} />
          </ScreenLayout>
        )}
        {activeTab === 'depth' && (
          <ScreenLayout>
            <DepthProcessingScreen apiBaseUrl={apiBaseUrl} appMode={appMode} />
          </ScreenLayout>
        )}
        {activeTab === 'projection' && (
          <ScreenLayout>
            <ProjectionAnimationScreen apiBaseUrl={apiBaseUrl} appMode={appMode} />
          </ScreenLayout>
        )}
        {activeTab === 'overlay' && (
          <ScreenLayout>
            <OverlayProjectionScreen apiBaseUrl={apiBaseUrl} appMode={appMode} />
          </ScreenLayout>
        )}
        {activeTab === 'logs' && (
          <ScreenLayout>
            <LogsScreen apiBaseUrl={apiBaseUrl} appMode={appMode} />
          </ScreenLayout>
        )}
        {activeTab === 'settings' && (
          <ScreenLayout>
            <SettingsScreen
              apiBaseUrl={apiBaseUrl}
              appMode={appMode}
              client={client}
              hydrated={hydrated}
              onApplyApiBaseUrl={applyApiBaseUrl}
              onApplyAppMode={applyAppMode}
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
    paddingHorizontal: 24,
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
    fontSize: 26,
    fontWeight: '700',
  },
  subtitle: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  headerMetaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  endpointChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
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
  localModeChip: {
    borderColor: colors.success,
    backgroundColor: colors.elevatedPanel,
  },
  endpointValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
  selectionChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.accentMuted,
    borderWidth: 1,
    borderColor: colors.secondary,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 4,
  },
  selectionChipLabel: {
    color: colors.secondary,
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  selectionChipValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
  tabBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.panel,
  },
  tabButton: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    minHeight: 44,
    justifyContent: 'center',
    borderRadius: 8,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  activeTabButton: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  pressedTabButton: {
    opacity: 0.82,
  },
  tabLabel: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '600',
  },
  activeTabLabel: {
    color: colors.onAccent,
  },
});
