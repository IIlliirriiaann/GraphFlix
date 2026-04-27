<script>
	import { onMount } from "svelte";
	import { getMoviePosterUrl } from "./api";

	export let movie;
	export let onClick = () => {};

	let posterUrl = null;

	onMount(async () => {
		posterUrl = await getMoviePosterUrl(movie.tmdbId);
	});
</script>

<button
	class="bg-bg-secondary border border-white/5 rounded-lg overflow-hidden cursor-pointer transition-all hover:border-accent-primary/30 hover:-translate-y-1 w-full text-left"
	on:click={onClick}
>
	<div
		class="aspect-[2/3] bg-gradient-to-br from-bg-tertiary to-bg-secondary relative"
	>
		{#if posterUrl}
			<img
				src={posterUrl}
				alt={`Poster of ${movie.title}`}
				class="absolute inset-0 w-full h-full object-cover"
				loading="lazy"
			/>
		{:else}
			<div
				class="absolute inset-0 flex items-center justify-center text-6xl opacity-20"
			>
				🎬
			</div>
		{/if}
	</div>

	<div class="p-4">
		<h3 class="font-semibold text-lg mb-1 truncate">{movie.title}</h3>

		{#if movie.avgRating}
			<div class="text-accent-tertiary font-semibold text-sm mb-2">
				Rating: {movie.avgRating.toFixed(1)}
			</div>
		{/if}

		{#if movie.score}
			<div class="h-1 bg-bg-tertiary rounded-full overflow-hidden mb-1">
				<div
					class="h-full bg-gradient-to-r from-accent-primary to-accent-secondary"
					style="width: {Math.min(movie.score * 10, 100)}%"
				></div>
			</div>
		{/if}
	</div>
</button>
