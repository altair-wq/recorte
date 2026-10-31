/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#F7F5F0',
        paper2: '#EFECE4',
        ink: '#1B1B1B',
        ink2: '#5A5853',
        line: '#D9D5CB',
        teal: '#0F6E56',
        tealsoft: '#DCEDE6',
        amber: '#B7791F',
        ambersoft: '#F6E7C8',
        red: '#B42318',
        redsoft: '#F4D4D0',
      },
      fontFamily: {
        serif: ['Newsreader', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: { card: '12px' },
    },
  },
  plugins: [],
}
