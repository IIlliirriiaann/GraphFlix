import axios from "axios";

const API_BASE = "http://localhost:8000/api/v1";

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

export const getTopMovies = (genre, limit = 10) =>
	api.get(`/movies/top`, { params: { genre, limit } });
