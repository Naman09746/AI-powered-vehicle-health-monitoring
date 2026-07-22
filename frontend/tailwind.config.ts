import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        base: {
          DEFAULT: "rgb(var(--base-bg) / <alpha-value>)",
          surface: "rgb(var(--base-surface) / <alpha-value>)",
          elevated: "rgb(var(--base-elevated) / <alpha-value>)",
        },
        border: {
          DEFAULT: "rgb(var(--border) / <alpha-value>)",
        },
        accent: {
          sky: "rgb(var(--accent-sky) / <alpha-value>)",
          green: "rgb(var(--accent-green) / <alpha-value>)",
          amber: "rgb(var(--accent-amber) / <alpha-value>)",
          red: "rgb(var(--accent-red) / <alpha-value>)",
        },
        text: {
          primary: "rgb(var(--text-primary) / <alpha-value>)",
          muted: "rgb(var(--text-muted) / <alpha-value>)",
        },
      },
      fontFamily: {
        heading: ["Space Grotesk", "sans-serif"],
        body: ["Inter", "sans-serif"],
      },
      backdropBlur: {
        xs: "2px",
      },
      boxShadow: {
        glow: "0 0 20px rgba(14, 165, 233, 0.15)",
        "glow-lg": "0 0 40px rgba(14, 165, 233, 0.1)",
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-out",
        "slide-up": "slideUp 0.3s ease-out",
        "count-up": "countUp 0.6s ease-out",
        "pulse-glow": "pulseGlow 2s infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 20px rgba(14, 165, 233, 0.1)" },
          "50%": { boxShadow: "0 0 30px rgba(14, 165, 233, 0.25)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
