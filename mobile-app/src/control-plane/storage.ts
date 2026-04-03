const memoryStorage = new Map<string, string>();

interface AsyncStorageLike {
  getItem: (key: string) => Promise<string | null> | string | null;
  setItem: (key: string, value: string) => Promise<void> | void;
  removeItem?: (key: string) => Promise<void> | void;
}

function createLocalStorageAdapter(storage: Storage): AsyncStorageLike {
  return {
    getItem: (key) => storage.getItem(key),
    setItem: (key, value) => {
      storage.setItem(key, value);
    },
    removeItem: (key) => {
      storage.removeItem(key);
    },
  };
}

function createMemoryAdapter(): AsyncStorageLike {
  return {
    getItem: async (key) => memoryStorage.get(key) ?? null,
    setItem: async (key, value) => {
      memoryStorage.set(key, value);
    },
    removeItem: async (key) => {
      memoryStorage.delete(key);
    },
  };
}

let resolvedStoragePromise: Promise<AsyncStorageLike> | null = null;

async function resolveStorage(): Promise<AsyncStorageLike> {
  if (resolvedStoragePromise) {
    return resolvedStoragePromise;
  }

  resolvedStoragePromise = (async () => {
    const runningInNode =
      typeof process !== 'undefined' && typeof process.release?.name === 'string'
        ? process.release.name === 'node'
        : false;

    if (
      !runningInNode &&
      typeof globalThis.localStorage !== 'undefined' &&
      globalThis.localStorage &&
      typeof globalThis.localStorage.getItem === 'function' &&
      typeof globalThis.localStorage.setItem === 'function'
    ) {
      return createLocalStorageAdapter(globalThis.localStorage);
    }

    try {
      const specifier = ['expo-sqlite', 'kv-store'].join('/');
      const dynamicImport = new Function('s', 'return import(s)') as (
        s: string,
      ) => Promise<{
        default?: Partial<AsyncStorageLike>;
      } & Partial<AsyncStorageLike>>;
      const module = await dynamicImport(specifier);
      const candidate = (module.default ?? module) as Partial<AsyncStorageLike>;
      if (candidate && typeof candidate.getItem === 'function' && typeof candidate.setItem === 'function') {
        return {
          getItem: async (key) => {
            const value = await candidate.getItem?.(key);
            return value ?? null;
          },
          setItem: async (key, value) => {
            await candidate.setItem?.(key, value);
          },
          removeItem: async (key) => {
            await candidate.removeItem?.(key);
          },
        };
      }
    } catch {
      // Fall through to in-memory storage in non-Expo / test environments.
    }

    return createMemoryAdapter();
  })();

  return resolvedStoragePromise;
}

export async function getStoredJson<T>(key: string, fallback: T): Promise<T> {
  const storage = await resolveStorage();
  const raw = await storage.getItem(key);
  if (!raw) {
    return fallback;
  }

  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function setStoredJson<T>(key: string, value: T): Promise<void> {
  const storage = await resolveStorage();
  await storage.setItem(key, JSON.stringify(value));
}

export async function removeStoredValue(key: string): Promise<void> {
  const storage = await resolveStorage();
  await storage.removeItem?.(key);
}
