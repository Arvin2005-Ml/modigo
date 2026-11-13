import type { Config } from 'tailwindcss';
export default {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {extend: {colors: {ink: '#24352e', muted: '#536259', green: '#315b48', warm: '#f8f6f1', soft: '#e7efe8'}}},
  plugins: []
} satisfies Config;
