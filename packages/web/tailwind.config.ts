// Tailwind v4 is CSS-first and does not use this config file for processing.
// Content paths and theme customisation are handled via @source / @theme in
// src/index.css.  This file is kept as a reference / placeholder.
import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
}

export default config
