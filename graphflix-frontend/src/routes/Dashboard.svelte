<script>
	import { onMount } from "svelte";
	import { push } from "svelte-spa-router";
	import { getRecommendations, getUserStats } from "../lib/api";
	import MovieCard from "../lib/MovieCard.svelte";

	let recommendations = [];
	let stats = null;
	let loading = true;
	const userId = 1; // Hardcoded for now TODO: Replace with actual user ID from auth context

	onMount(async () => {
		try {
			const [recRes, statsRes] = await Promise.all([
				getRecommendations(userId),
				getUserStats(userId),
			]);

			recommendations = recRes.data.recommendations;
			stats = statsRes.data.stats;
		} catch (error) {
			console.error("Error loading data:", error);
		} finally {
			loading = false;
		}
	});

	const handleMovieClick = (movieId) => {
		push(`/movie/${movieId}`);
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
				Your personalized movie recommendations
			</p>
		</div>

		<!-- Stats Card -->
		{#if stats}
			<div
				class="bg-gradient-to-br from-accent-primary/10 to-accent-secondary/5 border border-accent-primary/30 rounded-xl p-6 mb-12 backdrop-blur"
			>
				<h2 class="text-xl font-semibold mb-4">Hello, User {userId}!</h2>
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
					Recommendations for you
				</h2>
				<button class="text-accent-primary hover:underline text-sm">
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
