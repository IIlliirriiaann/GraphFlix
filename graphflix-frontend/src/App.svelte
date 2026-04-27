<script>
	import Router from "svelte-spa-router";
	import Dashboard from "./routes/Dashboard.svelte";
	import MovieDetail from "./routes/MovieDetail.svelte";

	const routes = {
		"/": Dashboard,
		"/movie/:id": MovieDetail,
		"/graph": Dashboard,
	};
</script>

<Router {routes} />
