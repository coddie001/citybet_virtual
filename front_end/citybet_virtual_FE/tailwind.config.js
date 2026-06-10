/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0a0a0a',
          raised: '#111111',
          panel: '#0d1a0d',
          border: '#1a2e1a',
        },
        brand: {
          DEFAULT: '#22c55e',
          dim: '#16a34a',
          glow: '#4ade80',
        },
        loss: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        'fluid-xs': 'clamp(0.7rem, 0.65rem + 0.2vw, 0.85rem)',
        'fluid-sm': 'clamp(0.8rem, 0.75rem + 0.25vw, 1rem)',
        'fluid-base': 'clamp(0.95rem, 0.9rem + 0.3vw, 1.15rem)',
        'fluid-lg': 'clamp(1.1rem, 1rem + 0.5vw, 1.5rem)',
        'fluid-xl': 'clamp(1.35rem, 1.2rem + 0.75vw, 2rem)',
        'fluid-2xl': 'clamp(1.75rem, 1.5rem + 1.25vw, 3rem)',
        'fluid-3xl': 'clamp(2.25rem, 1.8rem + 2vw, 4.5rem)',
      },
      maxWidth: {
        uhd: '3840px',
      },
      animation: {
        'fade-in': 'fadeIn 0.35s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
