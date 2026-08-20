import '@testing-library/jest-dom/vitest';

// Node 26 ships an experimental `localStorage` global that shadows jsdom's
// Storage implementation, leaving `window.localStorage` undefined under
// vitest. Provide a minimal in-memory polyfill so code paths that persist
// the active chat session (chatStore) behave like a real browser.
function installLocalStoragePolyfill() {
  const store = new Map<string, string>();
  const storage: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key: string) => (store.has(key) ? store.get(key)! : null),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key);
    },
    setItem: (key: string, value: string) => {
      store.set(key, String(value));
    },
  };

  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: storage,
  });
}

installLocalStoragePolyfill();