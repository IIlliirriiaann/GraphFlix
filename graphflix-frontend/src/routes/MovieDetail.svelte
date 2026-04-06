<script>
	import { pop, push } from "svelte-spa-router";
	import {
		getMovieDetails,
		getMoviePosterUrl,
		getSimilarMovies,
	} from "../lib/api";

	export let params = {};

	let movie = null;
	let similar = [];
	let loading = true;
	let moviePosterUrl = null;
	let similarPosterUrls = {};
	let activeRequestId = 0;

	const loadMovie = async (movieId) => {
		const requestId = ++activeRequestId;

		loading = true;
		movie = null;
		similar = [];
		moviePosterUrl = null;
		similarPosterUrls = {};

		try {
			const [movieRes, similarRes] = await Promise.all([
				getMovieDetails(movieId),
				getSimilarMovies(movieId, 6),
			]);

			if (requestId !== activeRequestId) return;

			movie = movieRes.data;
			similar = similarRes.data.similar;

			moviePosterUrl = await getMoviePosterUrl(movie.tmdbId);

			const posters = await Promise.all(
				similar.map(async (similarMovie) => ({
					movieId: similarMovie.movieId,
					posterUrl: await getMoviePosterUrl(similarMovie.tmdbId),
				}))
			);

			if (requestId !== activeRequestId) return;

			similarPosterUrls = posters.reduce((acc, item) => {
				acc[item.movieId] = item.posterUrl;
				return acc;
			}, {});
		} catch (error) {
			if (requestId !== activeRequestId) return;
			console.error("Error loading movie:", error);
		} finally {
			if (requestId === activeRequestId) {
				loading = false;
			}
		}
	};

	const handleSimilarMovieClick = (movieId) => {
		push(`/movie/${movieId}`);
	};

	$: routeMovieId = Number.parseInt(params.id, 10);
	$: {
		if (Number.isInteger(routeMovieId) && routeMovieId > 0) {
			loadMovie(routeMovieId);
		} else {
			loading = false;
			movie = null;
			similar = [];
			moviePosterUrl = null;
			similarPosterUrls = {};
		}
	}
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
					{#if moviePosterUrl}
						<img
							src={moviePosterUrl}
							alt={`Poster of ${movie.title}`}
							class="absolute inset-0 w-full h-full object-cover"
						/>
					{:else}
						<div
							class="absolute inset-0 flex items-center justify-center text-text-tertiary text-sm uppercase tracking-wide"
						>
							No poster
						</div>
					{/if}
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
							<button
								type="button"
								on:click={() => handleSimilarMovieClick(similarMovie.movieId)}
								class="text-center w-full group"
							>
								<div class="aspect-[2/3] bg-bg-tertiary rounded-lg mb-2 relative overflow-hidden">
									{#if similarPosterUrls[similarMovie.movieId]}
										<img
											src={similarPosterUrls[similarMovie.movieId]}
											alt={`Poster of ${similarMovie.title}`}
											class="absolute inset-0 w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
											loading="lazy"
										/>
									{:else}
										<div class="absolute inset-0 flex items-center justify-center text-[10px] text-text-tertiary uppercase tracking-wide">
											No poster
										</div>
									{/if}
								</div>
								<p class="text-sm font-medium truncate group-hover:text-accent-primary transition-colors">
									{similarMovie.title}
								</p>
								<p class="text-xs text-text-tertiary">
									{similarMovie.genreCount} genres
								</p>
							</button>
						{/each}
					</div>
				</div>
			{/if}
		{:else}
			<div class="text-center py-12 text-text-secondary">Movie not found</div>
		{/if}
	</div>
</div>
