/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/features/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#131313',
          dim: '#131313',
          low: '#1c1b1b',
          container: '#201f1f',
          'container-high': '#2a2a2a',
          'container-highest': '#353534',
          bright: '#3a3939',
          lowest: '#0e0e0e',
          variant: '#353534',
        },
        brand: {
          primary: '#4edea3',
          'primary-dim': '#4edea3',
          'primary-tint': '#6ffbbe',
          'on-primary': '#003824',
          secondary: '#b9c7e0',
          error: '#ffb4ab',
        },
        content: {
          DEFAULT: '#e5e2e1',
          muted: '#bbcabf',
        },
        chess: {
          light: '#f0d9b5',
          dark: '#b58863',
          white: '#ffffff',
          black: '#000000',
        },
      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'system-ui', 'sans-serif'],
        display: ['Geist', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        chess: '0.125rem',
        'chess-md': '0.375rem',
      },
      boxShadow: {
        'brand-glow': '0 0 20px rgba(132, 255, 0, 0.3)',
        'brand-glow-lg': '0 0 30px rgba(132, 255, 0, 0.45)',
        'brand-ambient': '0 8px 24px rgba(132, 255, 0, 0.04)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
