<script>
	import { onDestroy, onMount } from "svelte";
	import { push } from "svelte-spa-router";
	import { 
		getRecommendations,
		getContentRecommendations,
		getHybridRecommendations, 
		getConfigurableRecommendations,
		getUserStats 
	} from "../lib/api";
	import MovieCard from "../lib/MovieCard.svelte";

	let recommendations = [];
	let stats = null;
	let loading = false;
	let selectedUserId = null;
	let userInput = "";
	let errorMessage = "";
	let recommendationLimit = 10;
	let selectedAlgorithm = "collaborative";
	let autoReloadTimeout = null;

	// Hybrid algorithm weights
	let collaborativeWeight = 0.6;
	let contentWeight = 0.4;
	let hybridPreset = "balanced";

	// Configurable algorithm weights
	let genreWeight = 0.25;
	let actorWeight = 0.15;
	let ratingWeight = 0.45;
	let popularityWeight = 0.15;
	let configurablePreset = "rating_focused";

	const HYBRID_PRESETS = {
		balanced: { collaborative: 0.5, content: 0.5 },
		collaborative_first: { collaborative: 0.7, content: 0.3 },
		content_first: { collaborative: 0.3, content: 0.7 },
	};

	const CONFIGURABLE_PRESETS = {
		genre_focused: { genre: 0.4, actor: 0.3, rating: 0.2, popularity: 0.1 },
		rating_focused: { genre: 0.25, actor: 0.15, rating: 0.45, popularity: 0.15 },
		popularity_focused: { genre: 0.1, actor: 0.1, rating: 0.3, popularity: 0.5 },
		balanced: { genre: 0.25, actor: 0.25, rating: 0.25, popularity: 0.25 },
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

	const parseMovieId = (value) => {
		const parsed = Number.parseInt(String(value), 10);
		return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
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

	const clampWeight = (value) => {
		const parsed = Number.parseFloat(value);
		return Number.isFinite(parsed)
			? Number(Math.min(1, Math.max(0, parsed)).toFixed(2))
			: 0;
	};

	const syncHybridWeights = (which, value) => {
		const clamped = clampWeight(value);
		if (which === "collaborative") {
			collaborativeWeight = clamped;
			contentWeight = Number((1 - clamped).toFixed(2));
		} else {
			contentWeight = clamped;
			collaborativeWeight = Number((1 - clamped).toFixed(2));
		}
		hybridPreset = "custom";
		triggerAutoReload();
	};

	const syncConfigurableWeights = () => {
		configurablePreset = "custom";
		triggerAutoReload();
	};

	const updateConfigurableWeight = (which, value) => {
		const clamped = clampWeight(value);
		if (which === "genre") genreWeight = clamped;
		if (which === "actor") actorWeight = clamped;
		if (which === "rating") ratingWeight = clamped;
		if (which === "popularity") popularityWeight = clamped;
		syncConfigurableWeights();
	};

	const applyHybridPreset = (presetKey) => {
		hybridPreset = presetKey;
		const preset = HYBRID_PRESETS[presetKey];
		if (!preset) return;
		collaborativeWeight = preset.collaborative;
		contentWeight = preset.content;
		triggerAutoReload();
	};

	const applyConfigurablePreset = (presetKey) => {
		configurablePreset = presetKey;
		const preset = CONFIGURABLE_PRESETS[presetKey];
		if (!preset) return;
		genreWeight = preset.genre;
		actorWeight = preset.actor;
		ratingWeight = preset.rating;
		popularityWeight = preset.popularity;
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

	const handleAlgorithmChange = (algo) => {
		selectedAlgorithm = algo;
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
			let recRes;

			if (selectedAlgorithm === "collaborative") {
				recRes = await getRecommendations(userId, parsedLimit);
			} else if (selectedAlgorithm === "content_based") {
				recRes = await getContentRecommendations(userId, parsedLimit);
			} else if (selectedAlgorithm === "hybrid") {
				// Hybrid with custom weights
				recRes = await getHybridRecommendations(
					userId,
					collaborativeWeight,
					contentWeight,
					parsedLimit,
				);
			} else if (selectedAlgorithm === "configurable") {
				// Configurable with 4 weights
				recRes = await getConfigurableRecommendations(
					userId,
					genreWeight,
					actorWeight,
					ratingWeight,
					popularityWeight,
					parsedLimit,
				);
			}

			const [statsRes] = await Promise.all([getUserStats(userId)]);

			selectedUserId = userId;
			recommendations = recRes.data.recommendations;
			stats = statsRes.data.stats;
		} catch (error) {
			if (error?.response?.status === 404) {
				errorMessage = `User ${userId} not found.`;
			} else if (error?.response?.status === 400 || error?.response?.status === 422) {
				errorMessage = "Invalid parameters. Please check your weights.";
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

	const openGraphExplorer = () => {
		const query = new URLSearchParams();
		if (selectedUserId) {
			query.set("userId", String(selectedUserId));
		}
		const queryString = query.toString();
		push(queryString ? `/graph?${queryString}` : "/graph");
	};

	const openMovieInGraph = (movieId) => {
		const parsedUserId = selectedUserId || parseUserId(userInput);
		const parsedMovieId = parseMovieId(movieId);

		if (!parsedUserId || !parsedMovieId) {
			return;
		}

		const query = new URLSearchParams();
		query.set("mode", "explain");
		query.set("userId", String(parsedUserId));
		query.set("focusMovieId", String(parsedMovieId));
		query.set("algorithm", selectedAlgorithm);
		push(`/graph?${query.toString()}`);
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

			<div class="mt-6 inline-flex rounded-xl border border-white/10 bg-bg-secondary/70 p-1">
				<button
					type="button"
					class="px-4 py-2 rounded-lg text-sm font-medium bg-accent-primary text-white"
					aria-current="page"
				>
					Recommendations
				</button>
				<button
					type="button"
					on:click={openGraphExplorer}
					class="px-4 py-2 rounded-lg text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-bg-primary transition-colors"
				>
					Graph
				</button>
			</div>

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

			<!-- Algorithm Selection -->
			<div class="mt-6 bg-bg-secondary/70 border border-white/10 rounded-xl p-4 sm:p-5">
				<p class="text-sm text-text-secondary block mb-3">
					Select recommendation algorithm
				</p>
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
					<button
						class={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
							selectedAlgorithm === "collaborative"
								? "bg-accent-primary text-white"
								: "bg-bg-primary border border-white/10 text-text-secondary hover:border-accent-primary"
						}`}
						on:click={() => handleAlgorithmChange("collaborative")}
					>
						Collaborative
					</button>
					<button
						class={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
							selectedAlgorithm === "content_based"
								? "bg-accent-primary text-white"
								: "bg-bg-primary border border-white/10 text-text-secondary hover:border-accent-primary"
						}`}
						on:click={() => handleAlgorithmChange("content_based")}
					>
						Content-based
					</button>
					<button
						class={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
							selectedAlgorithm === "hybrid"
								? "bg-accent-primary text-white"
								: "bg-bg-primary border border-white/10 text-text-secondary hover:border-accent-primary"
						}`}
						on:click={() => handleAlgorithmChange("hybrid")}
					>
						Hybrid
					</button>
					<button
						class={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
							selectedAlgorithm === "configurable"
								? "bg-accent-primary text-white"
								: "bg-bg-primary border border-white/10 text-text-secondary hover:border-accent-primary"
						}`}
						on:click={() => handleAlgorithmChange("configurable")}
					>
						Configurable
					</button>
				</div>

				<!-- Hybrid Algorithm Controls -->
				{#if selectedAlgorithm === "hybrid"}
					<div class="border-t border-white/10 pt-4 mt-4">
						<p class="text-xs text-text-secondary block mb-3">
							Hybrid weights (combine collaborative & content-based)
						</p>
						<div class="mb-3">
							<select
								value={hybridPreset}
								on:change={(event) => applyHybridPreset(event.currentTarget.value)}
								class="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-accent-primary text-sm"
							>
								<option value="balanced">Balanced (50/50)</option>
								<option value="collaborative_first">Collaborative-first (70/30)</option>
								<option value="content_first">Content-first (30/70)</option>
								<option value="custom">Custom</option>
							</select>
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div>
								<label for="collab-weight" class="text-sm text-text-secondary block mb-2">
									Collaborative weight: {(collaborativeWeight * 100).toFixed(0)}%
								</label>
								<input
									id="collab-weight"
									type="range"
									min="0"
									max="1"
									step="0.05"
									value={collaborativeWeight}
									on:input={(event) => syncHybridWeights("collaborative", event.currentTarget.value)}
									class="w-full accent-accent-primary"
								/>
							</div>
							<div>
								<label for="content-weight" class="text-sm text-text-secondary block mb-2">
									Content-based weight: {(contentWeight * 100).toFixed(0)}%
								</label>
								<input
									id="content-weight"
									type="range"
									min="0"
									max="1"
									step="0.05"
									value={contentWeight}
									on:input={(event) => syncHybridWeights("content", event.currentTarget.value)}
									class="w-full accent-accent-secondary"
								/>
							</div>
						</div>
					</div>
				{/if}

				<!-- Configurable Algorithm Controls -->
				{#if selectedAlgorithm === "configurable"}
					<div class="border-t border-white/10 pt-4 mt-4">
						<p class="text-xs text-text-secondary block mb-3">
							Weighted scoring (all 4 components)
						</p>
						<div class="mb-3">
							<select
								value={configurablePreset}
								on:change={(event) => applyConfigurablePreset(event.currentTarget.value)}
								class="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-accent-primary text-sm"
							>
								<option value="rating_focused">Rating-focused (45% rating)</option>
								<option value="genre_focused">Genre-focused (40% genre)</option>
								<option value="popularity_focused">Popularity-focused (50% popularity)</option>
								<option value="balanced">Balanced (25% each)</option>
								<option value="custom">Custom</option>
							</select>
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
							<div>
								<label for="genre-weight" class="text-sm text-text-secondary block mb-2">
									Genre: {(genreWeight * 100).toFixed(0)}%
								</label>
								<input
									id="genre-weight"
									type="range"
									min="0"
									max="1"
									step="0.05"
									value={genreWeight}
									on:input={(event) => updateConfigurableWeight("genre", event.currentTarget.value)}
									class="w-full accent-accent-primary"
								/>
							</div>
							<div>
								<label for="actor-weight" class="text-sm text-text-secondary block mb-2">
									Actor: {(actorWeight * 100).toFixed(0)}%
								</label>
								<input
									id="actor-weight"
									type="range"
									min="0"
									max="1"
									step="0.05"
									value={actorWeight}
									on:input={(event) => updateConfigurableWeight("actor", event.currentTarget.value)}
									class="w-full accent-accent-secondary"
								/>
							</div>
							<div>
								<label for="rating-weight" class="text-sm text-text-secondary block mb-2">
									Rating: {(ratingWeight * 100).toFixed(0)}%
								</label>
								<input
									id="rating-weight"
									type="range"
									min="0"
									max="1"
									step="0.05"
									value={ratingWeight}
									on:input={(event) => updateConfigurableWeight("rating", event.currentTarget.value)}
									class="w-full accent-accent-primary"
								/>
							</div>
							<div>
								<label for="popularity-weight" class="text-sm text-text-secondary block mb-2">
									Popularity: {(popularityWeight * 100).toFixed(0)}%
								</label>
								<input
									id="popularity-weight"
									type="range"
									min="0"
									max="1"
									step="0.05"
									value={popularityWeight}
									on:input={(event) => updateConfigurableWeight("popularity", event.currentTarget.value)}
									class="w-full accent-accent-secondary"
								/>
							</div>
						</div>
						<p class="mt-2 text-xs text-text-secondary">
							Total: {((genreWeight + actorWeight + ratingWeight + popularityWeight) * 100).toFixed(0)}%
						</p>
					</div>
				{/if}

				<!-- Common Controls -->
				<div class="border-t border-white/10 pt-4 mt-4">
					<label for="recommendation-limit" class="text-sm text-text-secondary block mb-2">
						Number of recommendations
					</label>
					<input
						id="recommendation-limit"
						type="number"
						min="1"
						max="50"
						value={recommendationLimit}
						on:input={(event) => handleLimitInput(event.currentTarget.value)}
						class="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-accent-primary text-sm"
					/>
				</div>

				<p class="mt-3 text-xs text-text-secondary">
					{#if selectedAlgorithm === "collaborative"}
						Using user-to-user similarity (Jaccard-based)
					{:else if selectedAlgorithm === "content_based"}
						Recommending based on movie content (genres, actors, directors)
					{:else if selectedAlgorithm === "hybrid"}
						Blending collaborative & content signals dynamically
					{:else if selectedAlgorithm === "configurable"}
						Using custom weighted scoring across all factors
					{/if}
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
						<div class="space-y-2">
							<MovieCard
								{movie}
								onClick={() => handleMovieClick(movie.movieId)}
							/>
							<button
								type="button"
								on:click={() => openMovieInGraph(movie.movieId)}
								class="w-full bg-bg-secondary border border-white/10 rounded-lg px-3 py-2 text-xs text-text-secondary hover:text-text-primary hover:border-accent-primary transition-colors"
							>
								View in graph
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>
