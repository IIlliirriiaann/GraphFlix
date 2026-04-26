/// <reference types="svelte" />

declare module "*.svelte" {
	import type { SvelteComponent } from "svelte";

	export default class Component extends SvelteComponent {}
}

declare module "cytoscape-cola" {
	const extension: (cytoscape: typeof import("cytoscape")) => void;
	export default extension;
}

declare module "cytoscape-dagre" {
	const extension: (cytoscape: typeof import("cytoscape")) => void;
	export default extension;
}