/**
 * Global test setup and configuration
 */

// Import testing library matchers
import '@testing-library/jest-dom';

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
};

function isKnownTestWarning(value) {
  return (
    typeof value === 'string' &&
    (value.includes('ReactDOMTestUtils.act') ||
     value.includes('React Router Future Flag Warning'))
  );
}

// Suppress known framework warnings during tests.
const originalError = console.error;
const originalWarn = console.warn;
beforeAll(() => {
  console.error = (...args) => {
    if (isKnownTestWarning(args[0])) {
      return;
    }
    originalError.call(console, ...args);
  };
  console.warn = (...args) => {
    if (isKnownTestWarning(args[0])) {
      return;
    }
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});

// Clean up after each test
afterEach(() => {
  // Clear all mocks
  jest.clearAllMocks();
  
  // Clear local storage
  if (window.localStorage) {
    window.localStorage.clear();
  }
});
