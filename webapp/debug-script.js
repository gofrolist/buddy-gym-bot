// Debug script to manually set up mock Telegram WebApp
// Run this in the browser console if the automatic setup isn't working

console.log("🔧 Running debug script to set up mock Telegram WebApp...");

// Create mock Telegram WebApp
const createMockTelegramWebApp = (userId = 123456789) => ({
  initData: '',
  initDataUnsafe: {
    user: {
      id: userId,
      first_name: 'Dev User',
      last_name: 'Test',
      username: 'devuser',
      language_code: 'en'
    }
  },
  colorScheme: 'light',
  themeParams: {
    bg_color: '#ffffff',
    text_color: '#000000',
    hint_color: '#999999',
    link_color: '#2481cc',
    button_color: '#2481cc',
    button_text_color: '#ffffff',
    secondary_bg_color: '#f1f1f1'
  },
  isExpanded: true,
  viewportHeight: 600,
  viewportStableHeight: 600,
  expand: () => console.log("🔧 Mock: expand() called"),
  close: () => console.log("🔧 Mock: close() called"),
  ready: () => console.log("🔧 Mock: ready() called"),
  MainButton: {
    text: '',
    color: '',
    textColor: '',
    isVisible: false,
    isActive: false,
    show: () => {},
    hide: () => {},
    enable: () => {},
    disable: () => {},
    setText: () => {},
    onClick: () => {},
    offClick: () => {}
  },
  BackButton: {
    isVisible: false,
    show: () => {},
    hide: () => {},
    onClick: () => {},
    offClick: () => {}
  },
  onEvent: () => {},
  offEvent: () => {}
});

// Set up the mock
const mockTg = createMockTelegramWebApp(123456789);
window.Telegram = { WebApp: mockTg };

console.log("🔧 Mock Telegram WebApp created with user ID:", mockTg.initDataUnsafe.user.id);
console.log("🔧 window.Telegram.WebApp =", window.Telegram.WebApp);

// Force a page reload to trigger the React component to re-render
console.log("🔧 Reloading page to apply changes...");
window.location.reload();
