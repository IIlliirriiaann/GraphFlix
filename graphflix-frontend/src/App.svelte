<script>
	import Router from "svelte-spa-router";
	import Dashboard from "./routes/Dashboard.svelte";
	import MovieDetail from "./routes/MovieDetail.svelte";
	// @ts-ignore - Svelte language service intermittently misses newly added route files.
	import GraphExplorer from "./routes/GraphExplorer.svelte";

	const routes = {
		"/": Dashboard,
		"/movie/:id": MovieDetail,
		"/graph": GraphExplorer,
	};
</script>

<Router {routes} />
