import { useEffect, useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { Panel } from '../components/Panel';
import { emulatorConnectionNotes } from '../data/features';
import { normalizeApiBaseUrl } from '../services/api';
import { colors } from '../theme';

interface SettingsScreenProps {
  apiBaseUrl: string;
  onApplyApiBaseUrl: (value: string) => void;
}

export function SettingsScreen({
  apiBaseUrl,
  onApplyApiBaseUrl,
}: SettingsScreenProps) {
  const [draftValue, setDraftValue] = useState(apiBaseUrl);

  useEffect(() => {
    setDraftValue(apiBaseUrl);
  }, [apiBaseUrl]);

  const normalized = normalizeApiBaseUrl(draftValue);

  return (
    <>
      <Panel
        title="Backend connection"
        subtitle="Set the FastAPI base URL used by the mobile rewrite. The app always normalizes the value to an /api endpoint."
      >
        <TextInput
          autoCapitalize="none"
          autoCorrect={false}
          defaultValue={apiBaseUrl}
          onChangeText={setDraftValue}
          placeholder="http://127.0.0.1:8000/api"
          placeholderTextColor={colors.mutedText}
          style={styles.input}
          value={draftValue}
        />
        <Text style={styles.normalizedLabel}>Normalized: {normalized}</Text>
        <ActionButton label="Apply base URL" onPress={() => onApplyApiBaseUrl(draftValue)} />
      </Panel>

      <Panel
        title="Connection notes"
        subtitle="These defaults matter because localhost behaves differently on simulator, emulator, and physical hardware."
      >
        {emulatorConnectionNotes.map((note) => (
          <View key={note} style={styles.noteRow}>
            <View style={styles.noteDot} />
            <Text style={styles.noteText}>{note}</Text>
          </View>
        ))}
      </Panel>

      <Panel
        title="OMX team kickoff"
        subtitle="Use the installed oh-my-codex runtime to continue the rewrite with a durable coordinated team."
      >
        <Text style={styles.commandText}>
          omx team 3:executor "Continue the nano-dlna mobile rewrite in mobile-app using the
          existing FastAPI endpoints as the control plane."
        </Text>
      </Panel>
    </>
  );
}

const styles = StyleSheet.create({
  input: {
    backgroundColor: colors.elevatedPanel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    color: colors.text,
    fontSize: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  normalizedLabel: {
    color: colors.accent,
    fontSize: 13,
    lineHeight: 18,
  },
  noteRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'flex-start',
  },
  noteDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: colors.accent,
    marginTop: 6,
  },
  noteText: {
    flex: 1,
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  commandText: {
    color: colors.text,
    fontFamily: 'Courier',
    fontSize: 13,
    lineHeight: 20,
  },
});
