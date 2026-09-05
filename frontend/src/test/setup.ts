import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement these -- framer-motion's useInView needs
// IntersectionObserver, and AuditTable's jump-to-row scrolls the DOM.
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// @ts-expect-error -- test polyfill, not a spec-complete implementation
window.IntersectionObserver = MockIntersectionObserver
window.HTMLElement.prototype.scrollIntoView = () => {}
