import type { PropsWithChildren } from 'react';
import { ScrollView, StyleSheet } from 'react-native';

export function ScreenLayout({ children }: PropsWithChildren) {
  return (
    <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 20,
    gap: 16,
  },
});
