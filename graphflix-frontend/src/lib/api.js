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

/** @param {number|string} userId @param {number} [limit=10] */
export const getRecommendations = (userId, limit = 10) =>
	api.get(`/recommendations/${userId}`, { params: { limit } });

/** @param {number|string} userId @param {number} [limit=10] */
export const getContentRecommendations = (userId, limit = 10) =>
	api.get(`/recommendations/${userId}/content`, { params: { limit } });

/** @param {number|string} userId @param {{ genre: number, rating: number }} weights @param {number} [limit=10] */
export const getCustomRecommendations = (
	userId,
	weights,
	limit = 10,
) =>
	api.post(`/recommendations/custom/legacy`, {
		userId: String(userId),
		weights,
		limit,
	});

/** @param {number|string} userId @param {number} [depth=2] */
export const getUserGraph = (userId, depth = 2) =>
	api.get(`/graph/user/${userId}`, { params: { depth } });

/** @param {number|string} userId @param {number|string} movieId @param {{ minRating?: number, maxSimilarUsers?: number, maxSupportMovies?: number, maxBridgeMovies?: number }} [options={}] */
export const getRecommendationExplanationGraph = (userId, movieId, options = {}) =>
	api.get(`/graph/explain/user/${userId}/movie/${movieId}`, {
		params: {
			min_rating: options.minRating,
			max_similar_users: options.maxSimilarUsers,
			max_support_movies: options.maxSupportMovies,
			max_bridge_movies: options.maxBridgeMovies,
		},
	});

/** @param {number|string} userId @param {number} collaborativeWeight @param {number} contentWeight @param {number} [limit=10] */
export const getHybridRecommendations = (
	userId,
	collaborativeWeight = 0.6,
	contentWeight = 0.4,
	limit = 10,
) =>
	api.post(`/recommendations/hybrid`, {
		userId: String(userId),
		weights: {
			collaborativeWeight,
			contentWeight,
		},
		limit,
	});

/** @param {number|string} userId @param {number} genreWeight @param {number} actorWeight @param {number} ratingWeight @param {number} popularityWeight @param {number} [limit=10] */
export const getConfigurableRecommendations = (
	userId,
	genreWeight = 0.25,
	actorWeight = 0.15,
	ratingWeight = 0.45,
	popularityWeight = 0.15,
	limit = 10,
) =>
	api.post(`/recommendations/custom`, {
		userId: String(userId),
		weights: {
			genreWeight,
			actorWeight,
			ratingWeight,
			popularityWeight,
		},
		limit,
	});

/** @param {number|string} movieId */
export const getMovieDetails = (movieId) => api.get(`/movies/${movieId}`);

/** @param {number|string} movieId @param {number} [limit=10] */
export const getSimilarMovies = (movieId, limit = 10) =>
	api.get(`/movies/${movieId}/similar`, { params: { limit } });

/** @param {number|string} userId */
export const getUserStats = (userId) => api.get(`/users/${userId}/stats`);

/** @param {number} [limit=100] */
export const getUsers = (limit = 100) =>
	api.get(`/users`, { params: { limit } });

/** @param {string} genre @param {number} [limit=10] */
export const getTopMovies = (genre, limit = 10) =>
	api.get(`/movies/top`, { params: { genre, limit } });

/** @param {number|string|null|undefined} tmdbId */
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
