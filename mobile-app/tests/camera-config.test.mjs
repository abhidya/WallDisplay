import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const appConfig = JSON.parse(await readFile(new URL('../app.json', import.meta.url), 'utf8'));
const packageJson = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8'));

test('Expo config declares native camera permissions for structured-lighting capture', () => {
  const expo = appConfig.expo;

  assert.match(
    expo.ios.infoPlist.NSCameraUsageDescription,
    /structured-lighting calibration patterns/,
  );
  assert.ok(expo.android.permissions.includes('android.permission.CAMERA'));
  assert.ok(
    expo.plugins.some((plugin) => Array.isArray(plugin) && plugin[0] === 'expo-camera'),
    'expected expo-camera config plugin',
  );
});

test('mobile dependencies include Expo camera and file-system capture stack', () => {
  assert.equal(packageJson.dependencies['expo-camera'], '~17.0.10');
  assert.match(packageJson.dependencies['expo-file-system'], /^~19\.0\./);
});
