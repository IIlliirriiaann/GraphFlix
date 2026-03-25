/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{svelte,js,ts}"],
	theme: {
		extend: {
			colors: {
				bg: {
					primary: "#0a0e17",
					secondary: "#141824",
					tertiary: "#1e2332",
				},
				accent: {
					primary: "#6366f1",
					secondary: "#7c3aed",
					tertiary: "#f59e0b",
				},
				text: {
					primary: "#f8fafc",
					secondary: "#94a3b8",
					tertiary: "#64748b",
				},
			},
			fontFamily: {
				mono: ["DM Mono", "monospace"],
				sans: ["Outfit", "sans-serif"],
			},
		},
	},
	plugins: [],
};
