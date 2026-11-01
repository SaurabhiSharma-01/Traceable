/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#3730A3',
          dark: '#312E81',
          light: '#4F46E5',
          soft: '#EEF2FF',
        },
        surface: '#F8FAFC',
        sourced: {
          DEFAULT: '#16A34A',
          bg: '#DCFCE7',
          border: '#86EFAC',
        },
        gap: {
          DEFAULT: '#D97706',
          bg: '#FEF3C7',
          border: '#FCD34D',
        },
        conflict: {
          DEFAULT: '#DC2626',
          bg: '#FEE2E2',
          border: '#FCA5A5',
        },
        uncertain: {
          DEFAULT: '#64748B',
          bg: '#F1F5F9',
          border: '#CBD5E1',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
