import { CameraView, useCameraPermissions, type CameraType } from 'expo-camera';
import { Directory, File, Paths } from 'expo-file-system';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { colors } from '../theme';
import {
  getPersistedCaptureFileName,
  getSafeCapturePathSegment,
  type StructuredLightingCaptureStep,
} from '../features/lighting/structuredLightingCapture';

interface StructuredLightingCameraProps {
  disabled?: boolean;
  onUploadStep: (stepIndex: number, uri: string) => void;
  selectedSessionId: string;
  selectedStepIndex?: number;
  steps: StructuredLightingCaptureStep[];
}


function persistCapturedFile(sessionId: string, stepIndex: number, uri: string): string {
  if (!uri.startsWith('file://')) {
    return uri;
  }

  const directory = new Directory(
    Paths.cache,
    'structured-lighting',
    getSafeCapturePathSegment(sessionId),
  );
  directory.create({ idempotent: true, intermediates: true });
  const destination = new File(
    directory,
    getPersistedCaptureFileName(sessionId, stepIndex, uri),
  );
  if (destination.exists) {
    destination.delete();
  }
  new File(uri).copy(destination);
  return destination.uri;
}

export function StructuredLightingCamera({
  disabled = false,
  onUploadStep,
  selectedSessionId,
  selectedStepIndex,
  steps,
}: StructuredLightingCameraProps) {
  const cameraRef = useRef<CameraView>(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [cameraReady, setCameraReady] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [facing, setFacing] = useState<CameraType>('back');
  const [manualUri, setManualUri] = useState('');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(String(selectedStepIndex ?? steps[0]?.index ?? 0));
  useEffect(() => {
    const nextStepIndex = selectedStepIndex ?? steps.find((step) => step.status !== 'uploaded')?.index ?? steps[0]?.index;
    if (nextStepIndex !== undefined) {
      setStepIndex(String(nextStepIndex));
    }
  }, [selectedStepIndex, steps]);

  const selectedStep = useMemo(
    () => steps.find((step) => String(step.index) === stepIndex) ?? steps[0],
    [stepIndex, steps],
  );

  const canUseCamera = Boolean(permission?.granted && selectedStep && !disabled);
  const canCapture = canUseCamera && cameraReady && !capturing;
  const canUploadManual = Boolean(selectedStep && manualUri.trim()) && !disabled;

  async function captureSelectedStep() {
    if (!selectedStep || !cameraRef.current || !canCapture) {
      return;
    }

    setCapturing(true);
    try {
      setCameraError(null);
      const picture = await cameraRef.current.takePictureAsync({ quality: 1, imageType: 'jpg' });
      if (picture?.uri) {
        const persistedUri = persistCapturedFile(selectedSessionId, selectedStep.index, picture.uri);
        onUploadStep(selectedStep.index, persistedUri);
      }
    } catch (captureError) {
      setCameraError(captureError instanceof Error ? captureError.message : 'Camera capture failed.');
    } finally {
      setCapturing(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Mobile camera capture</Text>
      <Text style={styles.noteText}>
        Use the device camera for each projected pattern. Captures are saved to app cache by expo-camera and uploaded to the backend decoder.
      </Text>
      <View style={styles.stepRow}>
        {steps.map((step) => (
          <Pressable
            key={step.index}
            accessibilityRole="button"
            disabled={disabled}
            onPress={() => setStepIndex(String(step.index))}
            style={[
              styles.stepPill,
              String(step.index) === stepIndex && styles.stepPillActive,
              step.status === 'uploaded' && styles.stepPillUploaded,
            ]}
          >
            <Text style={styles.stepText}>{step.index}</Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.detailText}>
        Selected: {selectedStep ? `${selectedStep.label} (${selectedStep.status})` : 'no plan loaded'}
      </Text>

      {!permission ? (
        <Text style={styles.noteText}>Checking camera permission...</Text>
      ) : null}
      {permission && !permission.granted ? (
        <Pressable
          accessibilityRole="button"
          disabled={disabled}
          onPress={() => void requestPermission()}
          style={[styles.button, disabled && styles.disabled]}
        >
          <Text style={styles.buttonText}>Grant camera permission</Text>
        </Pressable>
      ) : null}

      {permission?.granted ? (
        <View style={styles.cameraFrame}>
          <CameraView
            active={!disabled}
            animateShutter
            facing={facing}
            mode="picture"
            onCameraReady={() => {
              setCameraReady(true);
              setCameraError(null);
            }}
            onMountError={(event) => setCameraError(event.message)}
            ref={cameraRef}
            responsiveOrientationWhenOrientationLocked
            style={styles.camera}
          />
        </View>
      ) : null}

      {cameraError ? <Text style={styles.errorText}>{cameraError}</Text> : null}

      <View style={styles.actionsRow}>
        <Pressable
          accessibilityRole="button"
          disabled={!canCapture}
          onPress={() => void captureSelectedStep()}
          style={[styles.button, !canCapture && styles.disabled]}
        >
          <Text style={styles.buttonText}>{capturing ? 'Capturing...' : 'Capture + upload'}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          disabled={disabled}
          onPress={() => setFacing((current) => (current === 'back' ? 'front' : 'back'))}
          style={[styles.secondaryButton, disabled && styles.disabled]}
        >
          <Text style={styles.secondaryButtonText}>Flip</Text>
        </Pressable>
      </View>

      <Text style={styles.noteText}>Fallback: paste a local file URI if camera preview is unavailable.</Text>
      <TextInput
        autoCapitalize="none"
        onChangeText={setManualUri}
        placeholder="file:///.../capture.jpg"
        placeholderTextColor={colors.mutedText}
        style={styles.input}
        value={manualUri}
      />
      <Pressable
        accessibilityRole="button"
        disabled={!canUploadManual}
        onPress={() => {
          if (selectedStep && manualUri.trim()) {
            onUploadStep(selectedStep.index, manualUri.trim());
            setManualUri('');
          }
        }}
        style={[styles.secondaryButton, !canUploadManual && styles.disabled]}
      >
        <Text style={styles.secondaryButtonText}>Upload URI fallback</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 10,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 12,
    backgroundColor: colors.elevatedPanel,
  },
  title: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  noteText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  detailText: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
    lineHeight: 18,
  },
  stepRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  stepPill: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    minWidth: 38,
    paddingHorizontal: 10,
    paddingVertical: 8,
    alignItems: 'center',
  },
  stepPillActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentMuted,
  },
  stepPillUploaded: {
    borderColor: colors.success,
  },
  stepText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: '700',
  },
  cameraFrame: {
    overflow: 'hidden',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
  },
  camera: {
    minHeight: 280,
  },
  actionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  input: {
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    color: colors.text,
    fontSize: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  button: {
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: colors.accent,
    backgroundColor: colors.accent,
  },
  secondaryButton: {
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.panel,
  },
  disabled: {
    opacity: 0.6,
  },
  buttonText: {
    color: '#07111a',
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
});
