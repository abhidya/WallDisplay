declare module 'expo-sqlite/kv-store' {
  const storage: {
    getItem?: (key: string) => Promise<string | null> | string | null;
    setItem?: (key: string, value: string) => Promise<void> | void;
    removeItem?: (key: string) => Promise<void> | void;
    getItemAsync?: (key: string) => Promise<string | null>;
    setItemAsync?: (key: string, value: string) => Promise<void>;
    Storage?: {
      getItemAsync?: (key: string) => Promise<string | null>;
      setItemAsync?: (key: string, value: string) => Promise<void>;
    };
  };
  export default storage;
  export const Storage: typeof storage.Storage;
  export const getItemAsync: typeof storage.getItemAsync;
  export const setItemAsync: typeof storage.setItemAsync;
}
