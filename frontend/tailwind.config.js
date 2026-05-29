/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-nunito)', 'Nunito', 'system-ui', 'sans-serif'],
        display: ['var(--font-fredoka)', 'Fredoka', 'Nunito', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        cozy: {
          bg1: '#FFF4E3',
          bg2: '#FFE4CC',
          bg3: '#FFD7B0',
          ink: '#4A3A2E',
          'ink-soft': '#8B7560',
          'ink-faint': '#C2B099',
          card: '#FFFBF3',
          'card-edge': '#F0E2C8',
          line: '#EBDCC1',
          accent: '#E8956A',
          green: '#6FBF8E',
          blue: '#7DA7E1',
          red: '#E68A8A',
          amber: '#E6B570',
          purple: '#B594D8',
        },
      },
      boxShadow: {
        cozy: '0 2px 0 rgba(74,58,46,.06), 0 4px 12px rgba(74,58,46,.06)',
        'cozy-md': '0 3px 0 rgba(74,58,46,.07), 0 10px 28px rgba(74,58,46,.10)',
        'cozy-lg': '0 6px 0 rgba(74,58,46,.08), 0 18px 50px rgba(74,58,46,.14)',
      },
      borderRadius: {
        pill: '14px',
        bubble: '14px',
      },
      keyframes: {
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'fade-out': { from: { opacity: '1' }, to: { opacity: '0' } },
        'zoom-in-95': {
          from: { opacity: '0', transform: 'translate(-50%, -50%) scale(0.95)' },
          to: { opacity: '1', transform: 'translate(-50%, -50%) scale(1)' },
        },
        'zoom-out-95': {
          from: { opacity: '1', transform: 'translate(-50%, -50%) scale(1)' },
          to: { opacity: '0', transform: 'translate(-50%, -50%) scale(0.95)' },
        },
        'log-in': {
          '0%': { opacity: '0', transform: 'translateX(-6px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'ts-pulse': {
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(1.04)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 150ms ease-out',
        'fade-out': 'fade-out 120ms ease-in',
        'dialog-in': 'zoom-in-95 180ms cubic-bezier(0.16, 1, 0.3, 1)',
        'dialog-out': 'zoom-out-95 140ms ease-in',
        'log-in': 'log-in 0.3s ease-out',
        'ts-pulse': 'ts-pulse 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
