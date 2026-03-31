<script>
	import { onMount } from "svelte";
	import { push } from "svelte-spa-router";
	import { getRecommendations, getUserStats } from "../lib/api";
	import MovieCard from "../lib/MovieCard.svelte";

	let recommendations = [];
	let stats = null;
	let loading = false;
	let selectedUserId = null;
	let userInput = "";
	let errorMessage = "";

	onMount(() => {
		// Page ready, waiting for user input
	});

	const handleMovieClick = (movieId) => {
		push(`/movie/${movieId}`);
	};

	const parseUserId = (value) => {
		const parsed = Number.parseInt(value, 10);
		return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
	};

	const loadDashboardData = async (userId) => {
		loading = true;
		errorMessage = "";
		recommendations = [];
		stats = null;

		try {
			const [recRes, statsRes] = await Promise.all([
				getRecommendations(userId),
				getUserStats(userId),
			]);

			selectedUserId = userId;
			userInput = String(userId);
			recommendations = recRes.data.recommendations;
			stats = statsRes.data.stats;
		} catch (error) {
			if (error?.response?.status === 404) {
				errorMessage = `User ${userId} not found.`;
			} else {
				errorMessage = "Unable to load recommendations right now.";
			}
			console.error("Error loading data:", error);
		} finally {
			loading = false;
		}
	};

	const handleUserSubmit = async (event) => {
		event.preventDefault();
		const parsedUserId = parseUserId(userInput);

		if (!parsedUserId) {
			errorMessage = "Please enter a valid positive user ID.";
			recommendations = [];
			stats = null;
			return;
		}

		await loadDashboardData(parsedUserId);
	};
</script>

<div class="min-h-screen p-8">
	<div class="max-w-7xl mx-auto">
		<!-- Header -->
		<div class="mb-12">
			<h1 class="font-mono text-5xl font-bold mb-2">
				Graph<span
					class="bg-gradient-to-r from-accent-primary to-accent-secondary bg-clip-text text-transparent"
					>Flix</span
				>
			</h1>
			<p class="text-text-secondary text-lg">
				Movie recommendations engine fueled by graph databases.
			</p>

			<form class="mt-6 flex flex-col sm:flex-row gap-3" on:submit={handleUserSubmit}>
				<div class="flex-1">
					<label for="user-select" class="text-sm text-text-secondary block mb-2">
						Select a user to see personalized movie picks based on their tastes and preferences:
					</label>
					<input
						id="user-select"
						type="text"
						bind:value={userInput}
						placeholder="Type a user ID (ex: 1)"
						class="w-full bg-bg-secondary border border-white/10 rounded-lg px-4 py-3 focus:outline-none focus:border-accent-primary"
					/>
				</div>
				<div class="flex items-end">
					<button
						type="submit"
						class="bg-accent-primary text-white rounded-lg px-5 py-3 hover:opacity-90 transition-opacity"
					>
						Load user
					</button>
				</div>
			</form>

			{#if errorMessage}
				<p class="mt-3 text-sm text-red-400">{errorMessage}</p>
			{/if}
		</div>

		<!-- Stats Card -->
		{#if stats}
			<div
				class="bg-gradient-to-br from-accent-primary/10 to-accent-secondary/5 border border-accent-primary/30 rounded-xl p-6 mb-12 backdrop-blur"
			>
				<h2 class="text-xl font-semibold mb-4">Results for User {selectedUserId}:</h2>
				<p class="text-text-secondary">
					{stats.moviesRated} movies rated • {stats.numGenres} genres explored
					{#if stats.avgRating}
						• {stats.avgRating.toFixed(1)} avg rating
					{/if}
				</p>
			</div>
		{/if}

		<!-- Recommendations -->
		<div class="mb-8">
			<div class="flex items-center justify-between mb-6">
				<h2 class="font-mono text-2xl font-semibold uppercase tracking-wide">
					Recommendations
				</h2>
				<button
					class="text-accent-primary hover:underline text-sm"
					on:click={() => loadDashboardData(selectedUserId)}
				>
					Refresh
				</button>
			</div>

			{#if loading}
				<div class="text-center py-12 text-text-secondary">Loading...</div>
			{:else if recommendations.length === 0}
				<div class="text-center py-12 text-text-secondary">
					No recommendations available
				</div>
			{:else}
				<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-6">
					{#each recommendations as movie}
						<MovieCard
							{movie}
							onClick={() => handleMovieClick(movie.movieId)}
						/>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>
