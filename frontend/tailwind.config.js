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
          DEFAULT: '#0a0f14',
          dim: '#0a0f14',
          low: '#0e1419',
          container: '#141a20',
          'container-high': '#1a2027',
          'container-highest': '#1f262e',
          bright: '#252d35',
          lowest: '#000000',
          variant: '#1f262e',
        },
        brand: {
          primary: '#84ff00',
          'primary-dim': '#7bef00',
          'primary-tint': '#cfffa7',
          'on-primary': '#214800',
          secondary: '#69f6b8',
          error: '#ff7351',
        },
        content: {
          DEFAULT: '#e7ebf3',
          muted: '#a7abb2',
        },
        chess: {
          light: '#f0d9b5',
          dark: '#b58863',
          white: '#ffffff',
          black: '#000000',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
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
