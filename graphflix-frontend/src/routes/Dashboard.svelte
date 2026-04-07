<script>
	import { onDestroy, onMount } from "svelte";
	import { push } from "svelte-spa-router";
	import { getCustomRecommendations, getUserStats } from "../lib/api";
	import MovieCard from "../lib/MovieCard.svelte";

	let recommendations = [];
	let stats = null;
	let loading = false;
	let selectedUserId = null;
	let userInput = "";
	let errorMessage = "";
	let recommendationLimit = 10;
	let genreWeight = 0.6;
	let ratingWeight = 0.4;
	let selectedPreset = "balanced";
	let autoReloadTimeout = null;

	const WEIGHT_PRESETS = {
		balanced: { genre: 0.5, rating: 0.5 },
		genre_first: { genre: 0.7, rating: 0.3 },
		rating_first: { genre: 0.3, rating: 0.7 },
	};

	onMount(() => {
		// Page ready, waiting for user input
	});

	onDestroy(() => {
		if (autoReloadTimeout) {
			clearTimeout(autoReloadTimeout);
		}
	});

	const handleMovieClick = (movieId) => {
		push(`/movie/${movieId}`);
	};

	const parseUserId = (value) => {
		const parsed = Number.parseInt(value, 10);
		return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
	};

	const parseLimit = (value) => {
		const parsed = Number.parseInt(value, 10);
		if (!Number.isInteger(parsed)) return 10;
		return Math.min(50, Math.max(1, parsed));
	};

	const syncGenreWeight = (value) => {
		const parsed = Number.parseFloat(value);
		const clamped = Number.isFinite(parsed)
			? Math.min(1, Math.max(0, parsed))
			: 0.5;
		genreWeight = Number(clamped.toFixed(2));
		ratingWeight = Number((1 - clamped).toFixed(2));
		selectedPreset = "custom";
		triggerAutoReload();
	};

	const syncRatingWeight = (value) => {
		const parsed = Number.parseFloat(value);
		const clamped = Number.isFinite(parsed)
			? Math.min(1, Math.max(0, parsed))
			: 0.5;
		ratingWeight = Number(clamped.toFixed(2));
		genreWeight = Number((1 - clamped).toFixed(2));
		selectedPreset = "custom";
		triggerAutoReload();
	};

	const triggerAutoReload = () => {
		if (!selectedUserId) return;

		if (autoReloadTimeout) {
			clearTimeout(autoReloadTimeout);
		}

		autoReloadTimeout = setTimeout(() => {
			loadDashboardData(selectedUserId);
		}, 500);
	};

	const handleLimitInput = (value) => {
		recommendationLimit = value;
		triggerAutoReload();
	};

	const applyPreset = (presetKey) => {
		selectedPreset = presetKey;
		const preset = WEIGHT_PRESETS[presetKey];
		if (!preset) return;
		genreWeight = preset.genre;
		ratingWeight = preset.rating;
		triggerAutoReload();
	};

	const loadDashboardData = async (userId) => {
		if (autoReloadTimeout) {
			clearTimeout(autoReloadTimeout);
		}

		loading = true;
		errorMessage = "";
		recommendations = [];
		stats = null;
		const parsedLimit = parseLimit(recommendationLimit);
		recommendationLimit = parsedLimit;

		try {
			const [recRes, statsRes] = await Promise.all([
				getCustomRecommendations(
					userId,
					{
						genre: genreWeight,
						rating: ratingWeight,
					},
					parsedLimit,
				),
				getUserStats(userId),
			]);

			selectedUserId = userId;
			recommendations = recRes.data.recommendations;
			stats = statsRes.data.stats;
		} catch (error) {
			if (error?.response?.status === 404) {
				errorMessage = `User ${userId} not found.`;
			} else if (error?.response?.status === 400) {
				errorMessage = "Please set recommendation weights greater than 0.";
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

		userInput = String(parsedUserId);
		selectedUserId = parsedUserId;

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
						Load picks
					</button>
				</div>
			</form>

			<div class="mt-6 bg-bg-secondary/70 border border-white/10 rounded-xl p-4 sm:p-5">
				<div class="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
					<div>
						<label for="weight-preset" class="text-sm text-text-secondary block mb-2">
							Weight preset
						</label>
						<select
							id="weight-preset"
							value={selectedPreset}
							on:change={(event) => applyPreset(event.currentTarget.value)}
							class="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-accent-primary"
						>
							<option value="balanced">Balanced (50/50)</option>
							<option value="genre_first">Genre-first (70/30)</option>
							<option value="rating_first">Rating-first (30/70)</option>
							<option value="custom">Custom</option>
						</select>
					</div>

					<div>
						<label for="genre-weight" class="text-sm text-text-secondary block mb-2">
							Genre weight: {(genreWeight * 100).toFixed(0)}%
						</label>
						<input
							id="genre-weight"
							type="range"
							min="0"
							max="1"
							step="0.05"
							value={genreWeight}
							on:input={(event) => syncGenreWeight(event.currentTarget.value)}
							class="w-full accent-accent-primary"
						/>
					</div>

					<div>
						<label for="rating-weight" class="text-sm text-text-secondary block mb-2">
							Rating weight: {(ratingWeight * 100).toFixed(0)}%
						</label>
						<input
							id="rating-weight"
							type="range"
							min="0"
							max="1"
							step="0.05"
							value={ratingWeight}
							on:input={(event) => syncRatingWeight(event.currentTarget.value)}
							class="w-full accent-accent-secondary"
						/>
					</div>

					<div>
						<label for="recommendation-limit" class="text-sm text-text-secondary block mb-2">
							Recommendation count
						</label>
						<input
							id="recommendation-limit"
							type="number"
							min="1"
							max="50"
							value={recommendationLimit}
							on:input={(event) => handleLimitInput(event.currentTarget.value)}
							class="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-accent-primary"
						/>
					</div>
				</div>
				<p class="mt-3 text-xs text-text-secondary">
					Weighted mode enabled: recommendations are blended from genre and rating signals.
				</p>
			</div>

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
					disabled={!selectedUserId || loading}
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
