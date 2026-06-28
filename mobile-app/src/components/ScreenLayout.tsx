import type { PropsWithChildren } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { colors, spacing } from '../theme';

export function ScreenLayout({ children }: PropsWithChildren) {
  return (
    <ScrollView
      contentContainerStyle={styles.content}
      indicatorStyle="white"
      showsVerticalScrollIndicator={false}
    >
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    backgroundColor: colors.background,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.md,
  },
});
