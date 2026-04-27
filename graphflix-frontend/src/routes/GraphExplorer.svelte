<script>
	import { onDestroy, onMount, tick } from "svelte";
	import { get } from "svelte/store";
	import { push } from "svelte-spa-router";
	import cytoscape from "cytoscape";
	// @ts-ignore - Module is available at runtime but has no bundled type declarations.
	import cytoscapeCola from "cytoscape-cola";
	// @ts-ignore - Module is available at runtime but has no bundled type declarations.
	import cytoscapeDagre from "cytoscape-dagre";
	import { getRecommendationExplanationGraph, getUserGraph } from "../lib/api";
	import { appStateStore, patchAppState } from "../lib/stores/appState";

	export let embedded = false;

	cytoscape.use(cytoscapeCola);
	cytoscape.use(cytoscapeDagre);

	const NODE_COLORS = {
		Movie: "#6366f1",
		User: "#ec4899",
		Genre: "#22c55e",
		Actor: "#f59e0b",
	};

	const LAYOUT_OPTIONS = [
		{
			value: "cola",
			label: "Cola",
			hint: "Force-directed with strong overlap avoidance and wider spacing.",
		},
		{
			value: "dagre",
			label: "Dagre",
			hint: "Hierarchical seed plus force relaxation to avoid straight-line stacking.",
		},
		{
			value: "concentric",
			label: "Concentric",
			hint: "Node rings by type, with users centered and metadata outside.",
		},
		{
			value: "breadthfirst",
			label: "Breadth-first",
			hint: "Radial tree expansion from user roots.",
		},
	];

	const TYPE_PRIORITY = {
		User: 4,
		Movie: 3,
		Genre: 2,
		Actor: 1,
	};

	const EXPLANATION_ROLE_LABELS = {
		focus_movie: "Focused recommendation",
		target_user: "Target user",
		similar_user: "Similar user signal",
		bridge_movie: "Bridge movie",
		support_movie: "Support movie",
		shared_genre: "Shared genre evidence",
		shared_actor: "Shared actor evidence",
		context: "Context node",
	};

	let cy = null;
	let cyContainer;

	let loading = false;
	let errorMessage = "";
	let userInput = "";
	let currentUserId = null;
	let focusMovieId = null;
	let focusRecommendationScore = null;
	let graphMode = "generic";
	let sourceAlgorithm = "";
	let depth = 2;
	let selectedLayout = "cola";

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
		roleLabel: "",
		connections: 0,
		scoreMetrics: [],
		evidenceMetrics: [],
		relationshipMetrics: [],
	};

	$: selectedLayoutHint =
		LAYOUT_OPTIONS.find((layout) => layout.value === selectedLayout)?.hint || "";

	const parseUserId = (value) => {
		const parsed = Number.parseInt(value, 10);
		return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
	};

	const parseDepth = (value) => {
		const parsed = Number.parseInt(String(value), 10);
		if (!Number.isInteger(parsed)) return 2;
		return Math.min(3, Math.max(1, parsed));
	};

	const parseMovieId = (value) => {
		const parsed = Number.parseInt(String(value), 10);
		return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
	};

	const parseGraphMode = (value) => (value === "explain" ? "explain" : "generic");

	const parseOptionalScore = (value) => {
		if (value === null || value === undefined || value === "") return null;
		const parsed = Number.parseFloat(String(value));
		return Number.isFinite(parsed) ? parsed : null;
	};

	const formatMetricNumber = (value, decimals = 2) => {
		const parsed = Number(value);
		if (!Number.isFinite(parsed)) return null;
		return Number(parsed.toFixed(decimals)).toString();
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
		if (edgeType === "RECOMMENDED") return 0.95;
		if (edgeType === "SIMILAR_USER") return 0.85;
		if (edgeType === "ACTED_IN") return 0.45;
		if (edgeType === "DIRECTED") return 0.4;
		return 0.35;
	};

	const mapGraphToElements = (graphData) => {
		const rawNodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];
		const rawEdges = Array.isArray(graphData?.edges) ? graphData.edges : [];
		const rootUserId = currentUserId ? String(currentUserId) : null;

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
			const baseProperties = node.properties || {};
			const nodeMovieId = parseMovieId(baseProperties.movieId);
			const role = String(node.properties?.explanationRole || "");
			const isRootUser =
				type === "User" &&
				rootUserId &&
				(String(baseProperties.userId) === rootUserId || id === rootUserId);
			const isFocusMovie =
				type === "Movie" &&
				focusMovieId !== null &&
				nodeMovieId !== null &&
				nodeMovieId === focusMovieId;
			const isSupportMovie = type === "Movie" && role === "support_movie";
			const isBridgeMovie = type === "Movie" && role === "bridge_movie";
			const isSimilarUser = type === "User" && role === "similar_user";
			const properties = {
				...baseProperties,
			};
			if (isFocusMovie && focusRecommendationScore !== null) {
				properties.recommendationScore = focusRecommendationScore;
			}
			if (isFocusMovie && sourceAlgorithm) {
				properties.recommendationAlgorithm = sourceAlgorithm;
			}
			return {
				group: "nodes",
				data: {
					id,
					label: getNodeLabel(node),
					type,
					properties,
					explanationRole: role,
					degree,
					size: Math.min(68, 24 + degree * 4),
					rootUser: isRootUser,
					focusMovie: isFocusMovie,
				},
				classes: [
					isRootUser ? "root-user" : "",
					isFocusMovie ? "focus-movie" : "",
					isSupportMovie ? "support-movie" : "",
					isBridgeMovie ? "bridge-movie" : "",
					isSimilarUser ? "similar-user" : "",
				]
					.filter(Boolean)
					.join(" "),
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

	const buildTooltipDetails = (node) => {
		const nodeData = node.data();
		const properties = nodeData.properties || {};
		const role = String(nodeData.explanationRole || properties.explanationRole || "");
		const roleLabel = EXPLANATION_ROLE_LABELS[role] || "";

		const scoreMetrics = [];
		const pushScoreMetric = (label, value, decimals = 3) => {
			const formatted = formatMetricNumber(value, decimals);
			if (formatted === null || formatted === "0") return;
			scoreMetrics.push({ label, value: formatted });
		};

		pushScoreMetric("Recommendation score", properties.recommendationScore);
		pushScoreMetric("Collaborative score", properties.score);
		pushScoreMetric("Hybrid score", properties.hybridScore);
		pushScoreMetric("Composite score", properties.compositeScore);
		pushScoreMetric("Content score", properties.totalScore);
		pushScoreMetric("Weighted score", properties.weightedScore);
		pushScoreMetric("Predicted rating", properties.predictedRating, 2);
		pushScoreMetric("Average rating", properties.avgRating, 2);
		pushScoreMetric("Similar user rating on focus", properties.focusMovieRating, 2);
		pushScoreMetric("Best support rating", properties.bestUserRating, 2);

		const evidenceMetrics = [];
		const pushEvidenceMetric = (label, value, decimals = 0) => {
			const formatted = formatMetricNumber(value, decimals);
			if (formatted === null || formatted === "0") return;
			evidenceMetrics.push({ label, value: formatted });
		};

		pushEvidenceMetric("Overlap with target user", properties.overlapCount);
		pushEvidenceMetric("Common bridge movies", properties.commonBridgeMoviesCount);
		pushEvidenceMetric("Supporting similar users", properties.supportingSimilarUsers);
		pushEvidenceMetric("Genre support matches", properties.supportGenreMatches);
		pushEvidenceMetric("Actor support matches", properties.supportActorMatches);
		pushEvidenceMetric("Matched support movies", properties.matchedSupportMovieCount);
		pushEvidenceMetric("Similar users linked", properties.similarUserCount);
		pushEvidenceMetric("Bridge movies linked", properties.bridgeMovieCount);
		pushEvidenceMetric("Support movies linked", properties.supportMovieCount);
		pushEvidenceMetric("Shared genres linked", properties.sharedGenreCount);
		pushEvidenceMetric("Shared actors linked", properties.sharedActorCount);

		const neighborTypeCounts = {
			Movie: 0,
			User: 0,
			Genre: 0,
			Actor: 0,
		};
		node
			.neighborhood("node")
			.forEach((neighbor) => {
				const neighborType = getNodeType(neighbor.data("type"));
				if (neighborTypeCounts[neighborType] !== undefined) {
					neighborTypeCounts[neighborType] += 1;
				}
			});

		if (neighborTypeCounts.Movie > 0) {
			evidenceMetrics.push({ label: "Neighbor movies", value: String(neighborTypeCounts.Movie) });
		}
		if (neighborTypeCounts.User > 0) {
			evidenceMetrics.push({ label: "Neighbor users", value: String(neighborTypeCounts.User) });
		}
		if (neighborTypeCounts.Genre > 0) {
			evidenceMetrics.push({ label: "Neighbor genres", value: String(neighborTypeCounts.Genre) });
		}
		if (neighborTypeCounts.Actor > 0) {
			evidenceMetrics.push({ label: "Neighbor actors", value: String(neighborTypeCounts.Actor) });
		}

		const edgeTypeCounts = {};
		const ratedWeights = [];
		node.connectedEdges().forEach((edge) => {
			const edgeType = String(edge.data("type") || "LINK");
			edgeTypeCounts[edgeType] = (edgeTypeCounts[edgeType] || 0) + 1;
			if (edgeType === "RATED") {
				const edgeWeight = Number(edge.data("weight"));
				if (Number.isFinite(edgeWeight)) {
					ratedWeights.push(edgeWeight);
				}
			}
		});

		const relationshipMetrics = [];
		const importantEdgeTypes = [
			"RECOMMENDED",
			"SIMILAR_USER",
			"RATED",
			"IN_GENRE",
			"ACTED_IN",
			"DIRECTED",
		];
		for (const edgeType of importantEdgeTypes) {
			if (!edgeTypeCounts[edgeType]) continue;
			relationshipMetrics.push({
				label: `${edgeType} edges`,
				value: String(edgeTypeCounts[edgeType]),
			});
		}

		if (ratedWeights.length > 0) {
			const averageRatedWeight =
				ratedWeights.reduce((sum, value) => sum + value, 0) / ratedWeights.length;
			relationshipMetrics.push({
				label: "Average RATED weight",
				value: formatMetricNumber(averageRatedWeight, 2) || "-",
			});
		}

		return {
			label: nodeData.label,
			type: nodeData.type,
			roleLabel,
			connections: nodeData.degree || node.connectedEdges().length || 0,
			scoreMetrics,
			evidenceMetrics,
			relationshipMetrics,
		};
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
		cy.elements().removeClass("faded focused selected path-highlight");
	};

	const highlightRootPath = (node) => {
		if (!cy) return;
		const rootNode = cy.nodes(".root-user").first();
		if (!rootNode.length) return;

		if (node.id() === rootNode.id()) {
			node.addClass("path-highlight");
			return;
		}

		const dijkstra = cy.elements().dijkstra({
			root: node,
			weight: () => 1,
			directed: false,
		});
		const path = dijkstra.pathTo(rootNode[0]);
		if (!path || !path.length) return;

		path.addClass("path-highlight");
		path.nodes().removeClass("faded").addClass("focused");
		path.edges().removeClass("faded");
	};

	const highlightNeighborhood = (node) => {
		if (!cy) return;
		clearHighlight();
		cy.elements().addClass("faded");
		node.removeClass("faded").addClass("selected focused");
		node.neighborhood().removeClass("faded").addClass("focused");
		node.connectedEdges().removeClass("faded");
		highlightRootPath(node);
	};

	const runLayout = () => {
		if (!cy) return;
		cy.resize();

		const visibleNodes = cy.nodes(":visible");
		if (!visibleNodes.length) return;

		const commonOptions = {
			animate: true,
			animationDuration: 450,
			fit: true,
			padding: 50,
		};

		if (selectedLayout === "cola") {
			cy.layout({
				name: "cola",
				...commonOptions,
				refresh: 2,
				maxSimulationTime: 2600,
				randomize: true,
				avoidOverlap: true,
				handleDisconnected: true,
				nodeDimensionsIncludeLabels: true,
				nodeSpacing: (node) => 28 + (node.data("size") || 24) * 0.6,
				edgeLength: (edge) => (edge.data("type") === "RATED" ? 125 : 110),
				convergenceThreshold: 0.01,
			}).run();
			return;
		}

		if (selectedLayout === "dagre") {
			const dagreLayout = cy.layout({
				name: "dagre",
				animate: false,
				fit: false,
				rankDir: "TB",
				nodeSep: 45,
				rankSep: 90,
				edgeSep: 20,
				ranker: "network-simplex",
			});

			dagreLayout.one("layoutstop", () => {
				if (!cy) return;
				cy.layout({
					name: "cola",
					...commonOptions,
					refresh: 2,
					maxSimulationTime: 1200,
					randomize: false,
					avoidOverlap: true,
					handleDisconnected: true,
					nodeDimensionsIncludeLabels: true,
					flow: { axis: "y", minSeparation: 70 },
					nodeSpacing: (node) => 20 + (node.data("size") || 24) * 0.45,
					edgeLength: (edge) => (edge.data("type") === "RATED" ? 105 : 95),
					convergenceThreshold: 0.02,
				}).run();
			});

			dagreLayout.run();
			return;
		}

		if (selectedLayout === "concentric") {
			cy.layout({
				name: "concentric",
				...commonOptions,
				startAngle: (-Math.PI * 2) / 4,
				clockwise: true,
				avoidOverlap: true,
				nodeDimensionsIncludeLabels: true,
				minNodeSpacing: 26,
				spacingFactor: 1.22,
				concentric: (node) => {
					const typeScore = TYPE_PRIORITY[node.data("type")] || 0;
					return typeScore * 100 + (node.data("degree") || 0);
				},
				levelWidth: () => 100,
			}).run();
			return;
		}

		const userRoots = cy.nodes('[type = "User"]');
		cy.layout({
			name: "breadthfirst",
			...commonOptions,
			roots: userRoots.length ? userRoots : undefined,
			directed: true,
			circle: true,
			spacingFactor: 1.65,
			avoidOverlap: true,
			nodeDimensionsIncludeLabels: true,
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
			const details = buildTooltipDetails(node);
			const mouseEvent = event.originalEvent;
			let x = tooltip.x;
			let y = tooltip.y;
			if (mouseEvent?.clientX && mouseEvent?.clientY && cyContainer) {
				const rect = cyContainer.getBoundingClientRect();
				x = mouseEvent.clientX - rect.left + 12;
				y = mouseEvent.clientY - rect.top + 12;
			}
			tooltip = {
				...tooltip,
				visible: true,
				x,
				y,
				...details,
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
						selector: 'edge[type = "DIRECTED"]',
						style: { "line-color": "#e879f9" },
					},
					{
						selector: 'edge[type = "SIMILAR_USER"]',
						style: {
							"line-color": "#38bdf8",
							"line-style": "dashed",
							width: 2.4,
						},
					},
					{
						selector: 'edge[type = "RECOMMENDED"]',
						style: {
							"line-color": "#f59e0b",
							"line-style": "dotted",
							width: 3.1,
						},
					},
					{
						selector: "node.root-user",
						style: {
							"border-color": "#fef08a",
							"border-width": 3,
							shape: "star",
						},
					},
					{
						selector: "node.focus-movie",
						style: {
							"border-width": 4,
							"border-color": "#fbbf24",
							"background-color": "#8b5cf6",
						},
					},
					{
						selector: "node.support-movie",
						style: {
							"border-width": 2.5,
							"border-color": "#22c55e",
						},
					},
					{
						selector: "node.bridge-movie",
						style: {
							"border-width": 2.5,
							"border-color": "#38bdf8",
						},
					},
					{
						selector: "node.similar-user",
						style: {
							shape: "diamond",
							"border-width": 2.5,
							"border-color": "#38bdf8",
						},
					},
					{
						selector: "node.path-highlight",
						style: {
							"border-width": 4,
							"border-color": "#fbbf24",
							opacity: 1,
							"text-opacity": 1,
						},
					},
					{
						selector: "edge.path-highlight",
						style: {
							width: 4,
							"line-color": "#fbbf24",
							opacity: 0.95,
						},
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

		const focusNode = cy.nodes(".focus-movie").first();
		const hasFocusNode = focusNode.length > 0;
		if (hasFocusNode) {
			highlightNeighborhood(focusNode[0]);
			selectedNode = focusNode.data();
		}

		graphRendered = true;

		requestAnimationFrame(() => {
			if (!cy) return;
			cy.resize();
			if (hasFocusNode) {
				cy.fit(focusNode, 160);
				return;
			}
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
			const shouldExplain = graphMode === "explain" && focusMovieId !== null;
			const response = shouldExplain
				? await getRecommendationExplanationGraph(parsedUserId, focusMovieId)
				: await getUserGraph(parsedUserId, depth);
			currentUserId = parsedUserId;
			patchAppState({
				userInput: String(parsedUserId),
				selectedUserId: parsedUserId,
				depth,
				focusMovieId,
				focusScore: focusRecommendationScore,
				algorithm: sourceAlgorithm,
			});
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

	const getRouteQueryParams = () => {
		const searchQuery = window.location.search?.startsWith("?")
			? window.location.search.slice(1)
			: "";
		if (searchQuery) {
			return new URLSearchParams(searchQuery);
		}

		const hash = window.location.hash || "";
		const queryIndex = hash.indexOf("?");
		if (queryIndex === -1) {
			return new URLSearchParams();
		}

		return new URLSearchParams(hash.slice(queryIndex + 1));
	};

	onMount(() => {
		const persisted = get(appStateStore);
		if (persisted.selectedUserId) {
			userInput = String(persisted.selectedUserId);
		} else if (persisted.userInput) {
			userInput = String(persisted.userInput);
		}
		depth = parseDepth(persisted.depth ?? depth);
		focusMovieId = parseMovieId(persisted.focusMovieId);
		focusRecommendationScore = parseOptionalScore(persisted.focusScore);
		sourceAlgorithm = String(persisted.algorithm || "");
		if (focusMovieId) {
			graphMode = "explain";
		}

		const query = getRouteQueryParams();
		const queryUserId = parseUserId(query.get("userId"));
		if (queryUserId) {
			userInput = String(queryUserId);
		}

		const queryDepth = parseDepth(query.get("depth") ?? depth);
		depth = queryDepth;

		focusMovieId = parseMovieId(query.get("focusMovieId"));
		focusRecommendationScore = parseOptionalScore(query.get("focusScore"));
		graphMode = parseGraphMode(query.get("mode"));
		sourceAlgorithm = String(query.get("algorithm") || "");
		if (focusMovieId && graphMode === "generic") {
			graphMode = "explain";
		}

		patchAppState({
			userInput,
			selectedUserId: parseUserId(userInput),
			depth,
			focusMovieId,
			focusScore: focusRecommendationScore,
			algorithm: sourceAlgorithm,
		});

		window.addEventListener("resize", handleWindowResize);

		if (parseUserId(userInput)) {
			generateGraph();
		}
	});

	onDestroy(() => {
		window.removeEventListener("resize", handleWindowResize);
		destroyGraph();
	});

	$: if (cy) {
		applyNodeTypeFilters();
	}

	$: if (embedded && $appStateStore.activeSection === "graph") {
		const persistedUserId = parseUserId($appStateStore.selectedUserId || $appStateStore.userInput);
		const persistedDepth = parseDepth($appStateStore.depth ?? depth);
		const persistedFocusMovieId = parseMovieId($appStateStore.focusMovieId);
		const persistedFocusScore = parseOptionalScore($appStateStore.focusScore);
		const persistedAlgorithm = String($appStateStore.algorithm || "");

		const shouldReload =
			persistedUserId &&
			(!graphRendered ||
				persistedUserId !== currentUserId ||
				persistedDepth !== depth ||
				persistedFocusMovieId !== focusMovieId);

		userInput = persistedUserId ? String(persistedUserId) : userInput;
		depth = persistedDepth;
		focusMovieId = persistedFocusMovieId;
		focusRecommendationScore = persistedFocusScore;
		sourceAlgorithm = persistedAlgorithm;
		graphMode = focusMovieId ? "explain" : "generic";

		if (shouldReload && !loading) {
			generateGraph();
		}
	}
</script>

<div class="p-4 lg:p-8" class:min-h-screen={!embedded}>
	<div class="max-w-[1500px] mx-auto">
		{#if !embedded}
			<div class="mb-5 flex flex-wrap items-center justify-between gap-3">
				<div>
					<h1 class="font-mono text-3xl lg:text-4xl font-semibold uppercase tracking-wide">
						Graph Explorer
					</h1>
					{#if graphMode === "explain" && focusMovieId}
						<p class="text-text-secondary text-sm mt-1">
							Recommendation explanation mode for user {userInput} around movie {focusMovieId}
							{#if sourceAlgorithm}
								({sourceAlgorithm}).
							{:else}
								.
							{/if}
						</p>
					{:else}
						<p class="text-text-secondary text-sm mt-1">
							Interactive recommendation graph for users, movies, genres, and actors.
						</p>
					{/if}
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
		{/if}

		<div class={`grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-4 lg:gap-5 min-h-[680px] ${
			embedded ? "" : "h-[calc(100vh-9rem)]"
		}`}>
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
							disabled={graphMode === "explain"}
							class="w-full accent-accent-primary"
						/>
						<p class="text-xs text-text-tertiary mt-2">
							{#if graphMode === "explain"}
								Explanation mode uses a focused graph around the selected recommendation.
							{:else}
								Higher depth expands the graph but may become denser.
							{/if}
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
						<div>
							<label for="layout-algorithm" class="text-sm text-text-secondary block mb-2">
								Layout algorithm
							</label>
							<select
								id="layout-algorithm"
								bind:value={selectedLayout}
								on:change={rerunLayout}
								class="w-full bg-bg-primary border border-white/10 rounded-lg px-3 py-2 focus:outline-none focus:border-accent-primary"
							>
								{#each LAYOUT_OPTIONS as layout}
									<option value={layout.value}>{layout.label}</option>
								{/each}
							</select>
							<p class="text-xs text-text-tertiary mt-2">{selectedLayoutHint}</p>
						</div>
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
						{#if graphMode === "explain"}
							<div class="flex items-center gap-2">
								<span class="inline-block w-3 h-3 rounded-full border-2 border-[#fbbf24]" style="background: #8b5cf6;"></span>
								<span>Focused recommendation</span>
							</div>
							<div class="flex items-center gap-2">
								<span class="inline-block w-3 h-3 rounded-full border-2 border-[#22c55e]" style={`background: ${NODE_COLORS.Movie};`}></span>
								<span>User liked support movie</span>
							</div>
							<div class="flex items-center gap-2">
								<span class="inline-block w-3 h-3 rounded-full border-2 border-[#38bdf8]" style={`background: ${NODE_COLORS.Movie};`}></span>
								<span>Bridge movie with similar users</span>
							</div>
						{/if}
						<div class="flex items-center gap-2">
							<span class="inline-block w-3 h-3 rounded-full" style={`background: ${NODE_COLORS.User};`}></span>
							<span>User</span>
						</div>
						{#if graphMode === "explain"}
							<div class="flex items-center gap-2">
								<span class="inline-block w-3 h-3 rotate-45 border border-[#38bdf8]" style={`background: ${NODE_COLORS.User};`}></span>
								<span>Similar user</span>
							</div>
						{/if}
						<div class="flex items-center gap-2">
							<span class="inline-block w-3 h-3 rounded-full" style={`background: ${NODE_COLORS.Genre};`}></span>
							<span>Genre</span>
						</div>
						<div class="flex items-center gap-2">
							<span class="inline-block w-3 h-3 rounded-full" style={`background: ${NODE_COLORS.Actor};`}></span>
							<span>Actor</span>
						</div>
						{#if graphMode === "explain"}
							<div class="pt-1 text-xs text-text-tertiary">
								Dashed blue edge: similar user signal • Dotted amber edge: recommendation target
							</div>
						{/if}
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
						class="absolute z-30 pointer-events-none bg-bg-primary/95 border border-white/10 rounded-md px-3 py-2 text-xs max-w-80"
						style={`left: ${tooltip.x}px; top: ${tooltip.y}px;`}
					>
						<p class="font-semibold break-words">{tooltip.label}</p>
						<p class="text-text-secondary">{tooltip.type}</p>
						{#if tooltip.roleLabel}
							<p class="text-accent-secondary">{tooltip.roleLabel}</p>
						{/if}
						<p class="text-text-tertiary">Connections: {tooltip.connections}</p>
						{#if sourceAlgorithm && tooltip.scoreMetrics.length > 0}
							<p class="text-text-tertiary">Algorithm: {sourceAlgorithm}</p>
						{/if}

						{#if tooltip.scoreMetrics.length > 0}
							<div class="border-t border-white/10 mt-2 pt-2">
								<p class="text-[11px] uppercase tracking-wide text-text-tertiary mb-1">Scores</p>
								{#each tooltip.scoreMetrics as metric}
									<p class="flex items-center justify-between gap-3">
										<span class="text-text-secondary">{metric.label}</span>
										<span class="text-text-primary">{metric.value}</span>
									</p>
								{/each}
							</div>
						{/if}

						{#if tooltip.evidenceMetrics.length > 0}
							<div class="border-t border-white/10 mt-2 pt-2">
								<p class="text-[11px] uppercase tracking-wide text-text-tertiary mb-1">Evidence</p>
								{#each tooltip.evidenceMetrics as metric}
									<p class="flex items-center justify-between gap-3">
										<span class="text-text-secondary">{metric.label}</span>
										<span class="text-text-primary">{metric.value}</span>
									</p>
								{/each}
							</div>
						{/if}

						{#if tooltip.relationshipMetrics.length > 0}
							<div class="border-t border-white/10 mt-2 pt-2">
								<p class="text-[11px] uppercase tracking-wide text-text-tertiary mb-1">Relationships</p>
								{#each tooltip.relationshipMetrics as metric}
									<p class="flex items-center justify-between gap-3">
										<span class="text-text-secondary">{metric.label}</span>
										<span class="text-text-primary">{metric.value}</span>
									</p>
								{/each}
							</div>
						{/if}
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