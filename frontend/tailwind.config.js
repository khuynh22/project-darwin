/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        arena: {
          bg: '#09090b',
          panel: '#18181b',
          accent: '#3b82f6',
        },
      },
    },
  },
  plugins: [],
};
