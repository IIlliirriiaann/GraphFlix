<script>
	import { onMount } from "svelte";
	import { pop } from "svelte-spa-router";
	import { getMovieDetails, getSimilarMovies } from "../lib/api";

	export let params = {};

	let movie = null;
	let similar = [];
	let loading = true;

	onMount(async () => {
		const movieId = parseInt(params.id);

		try {
			const [movieRes, similarRes] = await Promise.all([
				getMovieDetails(movieId),
				getSimilarMovies(movieId, 6),
			]);

			movie = movieRes.data;
			similar = similarRes.data.similar;
		} catch (error) {
			console.error("Error loading movie:", error);
		} finally {
			loading = false;
		}
	});
</script>

<div class="min-h-screen p-8">
	<div class="max-w-6xl mx-auto">
		<button
			on:click={pop}
			class="text-text-secondary hover:text-accent-primary mb-8 transition-colors"
		>
			← Back
		</button>

		{#if loading}
			<div class="text-center py-12">Loading...</div>
		{:else if movie}
			<!-- Movie Header -->
			<div class="grid md:grid-cols-[300px_1fr] gap-8 mb-12">
				<div class="aspect-[2/3] bg-gradient-to-br from-bg-tertiary to-bg-secondary rounded-lg relative overflow-hidden">
				</div>

				<div class="flex flex-col justify-center">
					<h1 class="text-5xl font-bold mb-4">{movie.title}</h1>

					{#if movie.genres && movie.genres.length > 0}
						<div class="flex gap-2 mb-4 flex-wrap">
							{#each movie.genres as genre}
								<span
									class="px-3 py-1 bg-bg-tertiary rounded-full text-sm text-text-secondary"
								>
									{genre}
								</span>
							{/each}
						</div>
					{/if}

					{#if movie.avgRating}
						<div class="text-2xl mb-6">
							<span class="text-accent-tertiary font-semibold"
								>Rating: {movie.avgRating.toFixed(1)}</span
							>
							<span class="text-text-tertiary text-lg ml-2">
								({movie.numRatings} ratings)
							</span>
						</div>
					{/if}
				</div>
			</div>

			<!-- Similar Movies -->
			{#if similar.length > 0}
				<div class="bg-bg-secondary border border-white/5 rounded-xl p-6">
					<h2
						class="font-mono text-xl font-semibold uppercase tracking-wide mb-6"
					>
						Similar Movies
					</h2>

					<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
						{#each similar as similarMovie}
							<div class="text-center">
								<div class="aspect-[2/3] bg-bg-tertiary rounded-lg mb-2"></div>
								<p class="text-sm font-medium truncate">{similarMovie.title}</p>
								<p class="text-xs text-text-tertiary">
									{similarMovie.genreCount} genres
								</p>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		{:else}
			<div class="text-center py-12 text-text-secondary">Movie not found</div>
		{/if}
	</div>
</div>
