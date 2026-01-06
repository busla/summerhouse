import '@testing-library/jest-dom/vitest'

// Polyfill ResizeObserver for tests (required by input-otp component)
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

// Mock document.elementFromPoint (required by input-otp's password manager badge detection)
if (typeof document !== 'undefined' && !document.elementFromPoint) {
  document.elementFromPoint = () => null
}

// Mock pointer capture APIs (required by Radix UI Select component)
// jsdom doesn't implement these, causing "target.hasPointerCapture is not a function" errors
if (typeof Element !== 'undefined') {
  Element.prototype.hasPointerCapture = () => false
  Element.prototype.setPointerCapture = () => {}
  Element.prototype.releasePointerCapture = () => {}
  // Mock scrollIntoView (required by Radix UI Select's keyboard navigation)
  Element.prototype.scrollIntoView = () => {}
}
