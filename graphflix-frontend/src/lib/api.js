import axios from "axios";

const API_BASE = "http://localhost:8000/api/v1";
const TMDB_BASE = "https://api.themoviedb.org/3";
const TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500";
const TMDB_API_KEY = import.meta.env.VITE_TMDB_API_KEY;
const posterCache = new Map();

const api = axios.create({
	baseURL: API_BASE,
	headers: {
		"Content-Type": "application/json",
	},
});

export const getRecommendations = (userId, limit = 10) =>
	api.get(`/recommendations/${userId}`, { params: { limit } });

export const getMovieDetails = (movieId) => api.get(`/movies/${movieId}`);

export const getSimilarMovies = (movieId, limit = 10) =>
	api.get(`/movies/${movieId}/similar`, { params: { limit } });

export const getUserStats = (userId) => api.get(`/users/${userId}/stats`);

export const getUsers = (limit = 100) =>
	api.get(`/users`, { params: { limit } });

export const getTopMovies = (genre, limit = 10) =>
	api.get(`/movies/top`, { params: { genre, limit } });

export const getMoviePosterUrl = async (tmdbId) => {
	if (!tmdbId || !TMDB_API_KEY) return null;

	const key = String(tmdbId);
	if (posterCache.has(key)) {
		return posterCache.get(key);
	}

	try {
		const response = await axios.get(`${TMDB_BASE}/movie/${key}`, {
			params: {
				api_key: TMDB_API_KEY,
				language: "en-US",
			},
		});

		const posterPath = response.data?.poster_path;
		const posterUrl = posterPath ? `${TMDB_IMAGE_BASE}${posterPath}` : null;
		posterCache.set(key, posterUrl);
		return posterUrl;
	} catch (error) {
		console.warn(`Unable to load TMDB poster for ${key}:`, error);
		posterCache.set(key, null);
		return null;
	}
};
