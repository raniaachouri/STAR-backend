/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      borderRadius: { "2xl": "1rem" },
      boxShadow: { soft: "0 1px 2px rgba(0,0,0,.06)" }
    },
  },
  plugins: [],
}
