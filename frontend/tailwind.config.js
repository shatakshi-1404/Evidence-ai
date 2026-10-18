/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF7F2",
        surface: "#FFFFFF",
        line: "#E8E2D8",
        navy: { DEFAULT: "#0F1B2D", soft: "#4A5568" },
        teal: { DEFAULT: "#0F766E", dark: "#0B5E57", light: "#CCE8E4" },
        danger: "#B42318",
      },
      fontFamily: {
        serif: ["Fraunces", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 27, 45, 0.04), 0 4px 16px rgba(15, 27, 45, 0.04)",
      },
    },
  },
  plugins: [],
};
