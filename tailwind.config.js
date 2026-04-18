/** @type {import('tailwindcss').Config} */
let daisyuiPlugin = () => {};

try {
  daisyuiPlugin = require("daisyui");
} catch (error) {
  daisyuiPlugin = () => {};
}

module.exports = {
  content: ["./app/templates/**/*.html", "./app/static/js/**/*.js", "./app/static/js/*.js"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Noto Sans TC"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        kgi: {
          navy: "#00367B",
          orange: "#E83E0B",
          sky: "#A2C0EF",
        },
      },
      boxShadow: {
        soft: "0 18px 50px rgba(0, 54, 123, 0.12)",
        lift: "0 12px 24px rgba(0, 54, 123, 0.12)",
      },
      backgroundImage: {
        "smart-grid":
          "radial-gradient(circle at top left, rgba(162, 192, 239, 0.32), transparent 34%), radial-gradient(circle at right 15%, rgba(232, 62, 11, 0.14), transparent 22%), linear-gradient(180deg, rgba(248, 250, 252, 0.96), rgba(240, 245, 252, 1))",
      },
    },
  },
  plugins: [daisyuiPlugin],
  daisyui: {
    themes: [
      {
        smartnudge: {
          primary: "#00367B",
          secondary: "#A2C0EF",
          accent: "#E83E0B",
          neutral: "#0F172A",
          "base-100": "#F8FAFC",
          "base-200": "#EEF3F9",
          "base-300": "#D6E0EE",
          info: "#2563EB",
          success: "#0F9D58",
          warning: "#D97706",
          error: "#DC2626",
        },
      },
    ],
    darkTheme: false,
    base: true,
    styled: true,
    utils: true,
    logs: false,
  },
};
