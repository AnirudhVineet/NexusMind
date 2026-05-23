import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d12",
        surface: "#11141b",
        border: "#1f2330",
        muted: "#7c8497",
        accent: "#6c8cff",
      },
    },
  },
  plugins: [],
};

export default config;
