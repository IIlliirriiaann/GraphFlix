<script>
	import { onDestroy, onMount, tick } from "svelte";
	import { push } from "svelte-spa-router";
	import cytoscape from "cytoscape";
	import { getUserGraph } from "../lib/api";

	const NODE_COLORS = {
		Movie: "#6366f1",
		User: "#ec4899",
		Genre: "#22c55e",
		Actor: "#f59e0b",
	};

	let cy = null;
	let cyContainer;

	let loading = false;
	let errorMessage = "";
	let userInput = "1";
	let currentUserId = null;
	let depth = 2;

	let selectedNode = null;
	let graphStats = { nodeCount: 0, edgeCount: 0 };
	let graphRendered = false;

	let showMovies = true;
	let showGenres = true;
	let showActors = true;

	let tooltip = {
		visible: false,
		x: 0,
		y: 0,
		label: "",
		type: "",
		connections: 0,
	};

	const parseUserId = (value) => {
		const parsed = Number.parseInt(value, 10);
		return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
	};

	const parseDepth = (value) => {
		const parsed = Number.parseInt(String(value), 10);
		if (!Number.isInteger(parsed)) return 2;
		return Math.min(3, Math.max(1, parsed));
	};

	const getNodeType = (type) => {
		if (type === "Movie" || type === "User" || type === "Genre" || type === "Actor") {
			return type;
		}
		return "Actor";
	};

	const getNodeLabel = (node) => {
		const nodeType = getNodeType(node.type);
		if (node.label) return String(node.label);
		if (nodeType === "Movie") return String(node.properties?.title ?? `Movie ${node.id}`);
		if (nodeType === "Genre") return String(node.properties?.name ?? "Genre");
		if (nodeType === "User") return `User ${node.properties?.userId ?? node.id}`;
		return String(node.properties?.name ?? node.properties?.fullName ?? `Actor ${node.id}`);
	};

	const normalizeEdgeOpacity = (edgeType, weight) => {
		if (edgeType === "RATED") {
			const normalized = Number.isFinite(weight) ? weight / 5 : 0.2;
			return Math.max(0.2, Math.min(1, normalized));
		}
		if (edgeType === "ACTED_IN") return 0.45;
		return 0.35;
	};

	const mapGraphToElements = (graphData) => {
		const rawNodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];
		const rawEdges = Array.isArray(graphData?.edges) ? graphData.edges : [];

		const degreeById = {};
		for (const edge of rawEdges) {
			const sourceId = String(edge.source);
			const targetId = String(edge.target);
			degreeById[sourceId] = (degreeById[sourceId] || 0) + 1;
			degreeById[targetId] = (degreeById[targetId] || 0) + 1;
		}

		const nodes = rawNodes.map((node) => {
			const id = String(node.id);
			const type = getNodeType(node.type);
			const degree = degreeById[id] || 0;
			return {
				group: "nodes",
				data: {
					id,
					label: getNodeLabel(node),
					type,
					properties: node.properties || {},
					degree,
					size: Math.min(68, 24 + degree * 4),
				},
			};
		});

		const nodeIds = new Set(nodes.map((node) => node.data.id));

		const edges = rawEdges
			.map((edge, index) => {
				const source = String(edge.source);
				const target = String(edge.target);
				const edgeType = String(edge.type || "LINK");
				const weight = Number(edge.weight);
				const opacity = normalizeEdgeOpacity(edgeType, weight);
				const strengthClass =
					opacity >= 0.75 ? "edge-strong" : opacity >= 0.45 ? "edge-medium" : "edge-weak";
				return {
					group: "edges",
					classes: strengthClass,
					data: {
						id: `${source}-${target}-${edgeType}-${index}`,
						source,
						target,
						type: edgeType,
						weight: Number.isFinite(weight) ? weight : 1,
						opacity,
					},
				};
			})
			.filter((edge) => nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target));

		graphStats = {
			nodeCount: nodes.length,
			edgeCount: edges.length,
		};

		return [...nodes, ...edges];
	};

	const getNodeVisibility = (type) => {
		if (type === "Movie") return showMovies;
		if (type === "Genre") return showGenres;
		if (type === "Actor") return showActors;
		return true;
	};

	const applyNodeTypeFilters = () => {
		if (!cy) return;

		cy.nodes().forEach((node) => {
			const hidden = !getNodeVisibility(node.data("type"));
			node.toggleClass("hidden-type", hidden);
		});

		cy.edges().forEach((edge) => {
			const hidden = edge.source().hasClass("hidden-type") || edge.target().hasClass("hidden-type");
			edge.toggleClass("hidden-type", hidden);
		});
	};

	const clearHighlight = () => {
		if (!cy) return;
		cy.elements().removeClass("faded focused selected");
	};

	const highlightNeighborhood = (node) => {
		if (!cy) return;
		clearHighlight();
		cy.elements().addClass("faded");
		node.removeClass("faded").addClass("selected focused");
		node.neighborhood().removeClass("faded").addClass("focused");
		node.connectedEdges().removeClass("faded");
	};

	const runLayout = () => {
		if (!cy) return;
		cy.resize();
		cy.layout({
			name: "cose",
			animate: true,
			animationDuration: 450,
			fit: true,
			padding: 40,
			nodeRepulsion: 9000,
			edgeElasticity: 120,
			idealEdgeLength: 120,
			gravity: 0.9,
			numIter: 550,
			randomize: true,
		}).run();
	};

	const ensureContainerReady = async () => {
		await tick();
		if (!cyContainer) {
			await new Promise((resolve) => requestAnimationFrame(resolve));
		}
		if (!cyContainer) return false;

		const rect = cyContainer.getBoundingClientRect();
		if (rect.width < 16 || rect.height < 16) {
			await new Promise((resolve) => requestAnimationFrame(resolve));
		}

		const nextRect = cyContainer.getBoundingClientRect();
		return nextRect.width >= 16 && nextRect.height >= 16;
	};

	const bindGraphEvents = () => {
		if (!cy) return;

		cy.on("tap", "node", (event) => {
			const node = event.target;
			highlightNeighborhood(node);
			selectedNode = node.data();
		});

		cy.on("tap", (event) => {
			if (event.target === cy) {
				selectedNode = null;
				clearHighlight();
			}
		});

		cy.on("mouseover", "node", (event) => {
			const node = event.target;
			tooltip = {
				...tooltip,
				visible: true,
				label: node.data("label"),
				type: node.data("type"),
				connections: node.data("degree") || 0,
			};
		});

		cy.on("mousemove", "node", (event) => {
			if (!tooltip.visible || !cyContainer) return;
			const mouseEvent = event.originalEvent;
			if (!mouseEvent?.clientX || !mouseEvent?.clientY) return;
			const rect = cyContainer.getBoundingClientRect();
			tooltip = {
				...tooltip,
				x: mouseEvent.clientX - rect.left + 12,
				y: mouseEvent.clientY - rect.top + 12,
			};
		});

		cy.on("mouseout", "node", () => {
			tooltip = { ...tooltip, visible: false };
		});
	};

	const initializeGraph = async (graphData) => {
		const containerReady = await ensureContainerReady();
		if (!containerReady) {
			errorMessage = "Graph container is not ready yet. Please click Generate again.";
			graphRendered = false;
			return;
		}

		const elements = mapGraphToElements(graphData);

		if (!cy) {
			cy = cytoscape({
				container: cyContainer,
				elements,
				minZoom: 0.2,
				maxZoom: 2.8,
				wheelSensitivity: 0.2,
				style: [
					{
						selector: "node",
						style: {
							label: "data(label)",
							width: "data(size)",
							height: "data(size)",
							"font-size": 10,
							"text-wrap": "wrap",
							"text-max-width": "120px",
							"text-valign": "bottom",
							"text-margin-y": 8,
							color: "#f8fafc",
							"overlay-opacity": 0,
							"border-width": 1,
							"border-color": "#334155",
						},
					},
					{
						selector: 'node[type = "Movie"]',
						style: { "background-color": NODE_COLORS.Movie },
					},
					{
						selector: 'node[type = "User"]',
						style: { "background-color": NODE_COLORS.User },
					},
					{
						selector: 'node[type = "Genre"]',
						style: { "background-color": NODE_COLORS.Genre },
					},
					{
						selector: 'node[type = "Actor"]',
						style: { "background-color": NODE_COLORS.Actor },
					},
					{
						selector: "edge",
						style: {
							"curve-style": "bezier",
							"line-color": "#94a3b8",
							width: 1.4,
							opacity: 0.35,
							"overlay-opacity": 0,
						},
					},
					{
						selector: "edge.edge-weak",
						style: { opacity: 0.25 },
					},
					{
						selector: "edge.edge-medium",
						style: { opacity: 0.5 },
					},
					{
						selector: "edge.edge-strong",
						style: { opacity: 0.9 },
					},
					{
						selector: 'edge[type = "RATED"]',
						style: { "line-color": "#fbbf24" },
					},
					{
						selector: 'edge[type = "IN_GENRE"]',
						style: { "line-color": "#22c55e" },
					},
					{
						selector: 'edge[type = "ACTED_IN"]',
						style: { "line-color": "#fb923c" },
					},
					{
						selector: "node.faded",
						style: {
							opacity: 0.15,
							"text-opacity": 0.2,
						},
					},
					{
						selector: "edge.faded",
						style: {
							opacity: 0.05,
						},
					},
					{
						selector: "node.focused",
						style: {
							opacity: 1,
							"text-opacity": 1,
						},
					},
					{
						selector: "node.selected",
						style: {
							"border-width": 3,
							"border-color": "#f8fafc",
						},
					},
					{
						selector: ".hidden-type",
						style: {
							display: "none",
						},
					},
				],
			});

			bindGraphEvents();
		} else {
			cy.elements().remove();
			cy.add(elements);
		}

		cy.resize();
		selectedNode = null;
		tooltip = { ...tooltip, visible: false };
		clearHighlight();
		applyNodeTypeFilters();
		runLayout();
		graphRendered = true;

		requestAnimationFrame(() => {
			if (!cy) return;
			cy.resize();
			const visible = cy.elements(":visible");
			if (visible.length > 0) {
				cy.fit(visible, 40);
			}
		});
	};

	const destroyGraph = () => {
		if (cy) {
			cy.destroy();
			cy = null;
		}
	};

	const generateGraph = async () => {
		const parsedUserId = parseUserId(userInput);
		if (!parsedUserId) {
			errorMessage = "Please enter a valid positive user ID.";
			graphRendered = false;
			return;
		}

		loading = true;
		errorMessage = "";
		graphRendered = false;
		depth = parseDepth(depth);

		try {
			const response = await getUserGraph(parsedUserId, depth);
			currentUserId = parsedUserId;
			await initializeGraph(response.data);
		} catch (error) {
			if (error?.response?.status === 404) {
				errorMessage = `User ${parsedUserId} not found.`;
			} else if (error?.response?.status === 422) {
				errorMessage = "Depth must be between 1 and 3.";
			} else {
				errorMessage = "Unable to load graph data right now.";
			}
			console.error("Graph loading error:", error);
		} finally {
			loading = false;
		}
	};

	const zoomBy = (factor) => {
		if (!cy) return;
		const nextZoom = Math.max(cy.minZoom(), Math.min(cy.maxZoom(), cy.zoom() * factor));
		cy.zoom({
			level: nextZoom,
			renderedPosition: {
				x: cy.width() / 2,
				y: cy.height() / 2,
			},
		});
	};

	const panBy = (x, y) => {
		if (!cy) return;
		cy.panBy({ x, y });
	};

	const resetView = () => {
		if (!cy) return;
		const visible = cy.elements(":visible");
		if (visible.length > 0) {
			cy.fit(visible, 40);
		} else {
			cy.fit(cy.elements(), 40);
		}
	};

	const rerunLayout = () => {
		runLayout();
	};

	const handleWindowResize = () => {
		if (!cy) return;
		cy.resize();
	};

	const getPropertyEntries = (properties) => {
		if (!properties || typeof properties !== "object") return [];
		return Object.entries(properties)
			.filter(([, value]) => value !== null && value !== undefined && value !== "")
			.slice(0, 10);
	};

	const formatPropertyValue = (value) => {
		if (Array.isArray(value)) {
			return value.length ? value.join(", ") : "-";
		}
		if (value && typeof value === "object") {
			return JSON.stringify(value);
		}
		return String(value);
	};

	onMount(() => {
		window.addEventListener("resize", handleWindowResize);
		generateGraph();
	});

	onDestroy(() => {
		window.removeEventListener("resize", handleWindowResize);
		destroyGraph();
	});

	$: if (cy) {
		applyNodeTypeFilters();
	}
</script>

<div class="min-h-screen p-4 lg:p-8">
	<div class="max-w-[1500px] mx-auto">
		<div class="mb-5 flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="font-mono text-3xl lg:text-4xl font-semibold uppercase tracking-wide">
					Graph Explorer
				</h1>
				<p class="text-text-secondary text-sm mt-1">
					Interactive recommendation graph for users, movies, genres, and actors.
				</p>
			</div>
			<div class="inline-flex rounded-xl border border-white/10 bg-bg-secondary/70 p-1">
				<button
					type="button"
					on:click={() => push("/")}
					class="px-4 py-2 rounded-lg text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-bg-primary transition-colors"
				>
					Recommendations
				</button>
				<button
					type="button"
					class="px-4 py-2 rounded-lg text-sm font-medium bg-accent-primary text-white"
					aria-current="page"
				>
					Graph
				</button>
			</div>
		</div>

		<div class="grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-4 lg:gap-5 h-[calc(100vh-9rem)] min-h-[680px]">
			<aside class="bg-bg-secondary/80 border border-white/10 rounded-xl p-4 lg:p-5 overflow-y-auto backdrop-blur">
				<form
					class="space-y-4"
					on:submit|preventDefault={generateGraph}
				>
					<div>
						<label for="graph-user-id" class="text-sm text-text-secondary block mb-2">
							User ID
						</label>
						<input
							id="graph-user-id"
							type="text"
							bind:value={userInput}
							placeholder="Ex: 1"
							class="w-full bg-bg-primary border border-white/10 rounded-lg px-4 py-2.5 focus:outline-none focus:border-accent-primary"
						/>
					</div>

					<div>
						<label for="graph-depth" class="text-sm text-text-secondary block mb-2">
							Depth: {depth}
						</label>
						<input
							id="graph-depth"
							type="range"
							min="1"
							max="3"
							step="1"
							bind:value={depth}
							class="w-full accent-accent-primary"
						/>
						<p class="text-xs text-text-tertiary mt-2">
							Higher depth expands the graph but may become denser.
						</p>
					</div>

					<div class="border-t border-white/10 pt-4">
						<p class="text-sm text-text-secondary mb-2">Node visibility</p>
						<div class="space-y-2 text-sm">
							<label class="flex items-center gap-2 cursor-pointer select-none">
								<input type="checkbox" bind:checked={showMovies} class="accent-accent-primary" />
								<span>Movies</span>
							</label>
							<label class="flex items-center gap-2 cursor-pointer select-none">
								<input type="checkbox" bind:checked={showGenres} class="accent-accent-primary" />
								<span>Genres</span>
							</label>
							<label class="flex items-center gap-2 cursor-pointer select-none">
								<input type="checkbox" bind:checked={showActors} class="accent-accent-primary" />
								<span>Actors</span>
							</label>
						</div>
					</div>

					<div class="border-t border-white/10 pt-4 space-y-3">
						<p class="text-sm text-text-secondary">Layout controls</p>
						<div class="grid grid-cols-3 gap-2">
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={() => zoomBy(1.2)}>
								Zoom +
							</button>
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={() => zoomBy(0.82)}>
								Zoom -
							</button>
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={resetView}>
								Reset
							</button>
						</div>
						<div class="grid grid-cols-3 gap-2">
							<div></div>
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={() => panBy(0, -80)}>
								Pan Up
							</button>
							<div></div>
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={() => panBy(-80, 0)}>
								Pan Left
							</button>
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={rerunLayout}>
								Relayout
							</button>
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={() => panBy(80, 0)}>
								Pan Right
							</button>
							<div></div>
							<button type="button" class="bg-bg-primary border border-white/10 rounded-lg py-2 hover:border-accent-primary" on:click={() => panBy(0, 80)}>
								Pan Down
							</button>
							<div></div>
						</div>
						<p class="text-xs text-text-tertiary">Tip: drag on the graph to pan naturally.</p>
					</div>

					<button
						type="submit"
						class="w-full bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-semibold rounded-lg py-2.5 hover:opacity-90 transition-opacity disabled:opacity-60"
						disabled={loading}
					>
						{#if loading}Generating...{:else}Generate{/if}
					</button>

					{#if errorMessage}
						<p class="text-sm text-red-400">{errorMessage}</p>
					{/if}
				</form>

				<div class="border-t border-white/10 mt-4 pt-4">
					<p class="text-sm text-text-secondary mb-3">Legend</p>
					<div class="space-y-2 text-sm">
						<div class="flex items-center gap-2">
							<span class="inline-block w-3 h-3 rounded-full" style={`background: ${NODE_COLORS.Movie};`}></span>
							<span>Movie</span>
						</div>
						<div class="flex items-center gap-2">
							<span class="inline-block w-3 h-3 rounded-full" style={`background: ${NODE_COLORS.User};`}></span>
							<span>User</span>
						</div>
						<div class="flex items-center gap-2">
							<span class="inline-block w-3 h-3 rounded-full" style={`background: ${NODE_COLORS.Genre};`}></span>
							<span>Genre</span>
						</div>
						<div class="flex items-center gap-2">
							<span class="inline-block w-3 h-3 rounded-full" style={`background: ${NODE_COLORS.Actor};`}></span>
							<span>Actor</span>
						</div>
					</div>
				</div>

				<div class="border-t border-white/10 mt-4 pt-4">
					<p class="text-xs text-text-tertiary">
						{#if currentUserId}
							User {currentUserId} | {graphStats.nodeCount} nodes | {graphStats.edgeCount} edges
						{:else}
							No graph loaded yet.
						{/if}
					</p>
				</div>

				{#if selectedNode}
					<div class="bg-bg-primary border border-white/10 rounded-xl p-4 mt-4">
						<p class="text-xs uppercase tracking-wide text-text-tertiary">Selected node</p>
						<h3 class="text-lg font-semibold mt-1 break-words">{selectedNode.label}</h3>
						<div class="text-sm text-text-secondary mt-2 space-y-1">
							<p>Type: {selectedNode.type}</p>
							<p>Connections: {selectedNode.degree || 0}</p>
						</div>

						<div class="border-t border-white/10 mt-3 pt-3 space-y-1 max-h-48 overflow-y-auto">
							{#if getPropertyEntries(selectedNode.properties).length > 0}
								{#each getPropertyEntries(selectedNode.properties) as [key, value]}
									<p class="text-xs">
										<span class="text-text-tertiary">{key}:</span>
										<span class="text-text-primary ml-1 break-words">{formatPropertyValue(value)}</span>
									</p>
								{/each}
							{:else}
								<p class="text-xs text-text-tertiary">No extra properties.</p>
							{/if}
						</div>
					</div>
				{/if}
			</aside>

			<section class="relative h-full min-h-[560px] bg-bg-secondary border border-white/10 rounded-xl overflow-hidden">
				<div bind:this={cyContainer} class="w-full h-full min-h-[560px]"></div>

				{#if loading}
					<div class="absolute inset-0 z-20 bg-bg-primary/65 backdrop-blur-sm flex items-center justify-center text-text-secondary">
						Loading graph...
					</div>
				{/if}

				{#if tooltip.visible}
					<div
						class="absolute z-30 pointer-events-none bg-bg-primary/95 border border-white/10 rounded-md px-3 py-2 text-xs max-w-56"
						style={`left: ${tooltip.x}px; top: ${tooltip.y}px;`}
					>
						<p class="font-semibold break-words">{tooltip.label}</p>
						<p class="text-text-secondary">{tooltip.type}</p>
						<p class="text-text-tertiary">Connections: {tooltip.connections}</p>
					</div>
				{/if}

				{#if !loading && !errorMessage && !graphRendered}
					<div class="absolute inset-0 z-10 flex items-center justify-center text-sm text-text-secondary">
						Graph not rendered yet. Click Generate to draw the network.
					</div>
				{/if}
			</section>
		</div>
	</div>
</div>