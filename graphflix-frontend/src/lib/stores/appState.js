import { writable } from "svelte/store";

const STORAGE_KEY = "graphflix_app_state_v1";

const DEFAULT_STATE = {
	activeSection: "recommendations",
	userInput: "",
	selectedUserId: null,
	recommendations: [],
	recommendationLimit: 10,
	selectedAlgorithm: "collaborative",
	collaborativeWeight: 0.6,
	contentWeight: 0.4,
	hybridPreset: "balanced",
	genreWeight: 0.25,
	actorWeight: 0.15,
	ratingWeight: 0.45,
	popularityWeight: 0.15,
	configurablePreset: "rating_focused",
	depth: 2,
	focusMovieId: null,
	focusScore: null,
	algorithm: "",
	recommendedMovieIds: [],
};

const isBrowser = typeof window !== "undefined";

const loadState = () => {
	if (!isBrowser) return DEFAULT_STATE;

	try {
		const raw = window.localStorage.getItem(STORAGE_KEY);
		if (!raw) return DEFAULT_STATE;
		const parsed = JSON.parse(raw);
		if (!parsed || typeof parsed !== "object") return DEFAULT_STATE;
		return { ...DEFAULT_STATE, ...parsed };
	} catch {
		return DEFAULT_STATE;
	}
};

const appState = writable(loadState());

if (isBrowser) {
	appState.subscribe((state) => {
		try {
			window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
		} catch {
			// Ignore storage errors (private mode, quota, etc.)
		}
	});
}

export const patchAppState = (patch) => {
	appState.update((state) => ({ ...state, ...patch }));
};

export const appStateStore = appState;
