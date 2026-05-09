# GraphFlix

**Graph Database-Powered Movie Recommendation System with Interactive Visualization**

A transparent, explainable movie recommendation engine built on Neo4j, demonstrating how graph databases enable both powerful algorithms and visual explanation of recommendation engines.

---

## Key Features

- **4 Recommendation Algorithms**: Collaborative filtering, content-based, hybrid, and fully configurable
- **Interactive Graph Visualization**: See *why* movies are recommended through network graphs
- **Real-time Algorithm Control**: Adjust weights (genre, actors, ratings) and see results instantly
- **Dual-Channel Score Normalization**: Production-grade Jaccard similarity with min-max + z-score normalization
- **Full Transparency**: Every recommendation shows its reasoning

---

## What Makes It Different

Unlike Netflix, GraphFlix shows you:
- Which similar users influenced the recommendation
- What genres/actors/directors connect you to the movie
- Exact paths through the graph from your profile to the suggestion

Perfect for understanding recommendation systems, graph databases, or building portfolio-worthy projects.

---

## Tech Stack

**Backend:**
- Python 3.10+ with FastAPI (async)
- Neo4j 5.x graph database
- Cypher query language
- Pydantic v2 for validation

**Frontend:**
- Svelte 5 + Vite
- Tailwind CSS 4
- Cytoscape.js for graph visualization
- Axios for API calls

**Data:**
- MovieLens ml-latest-small (9,742 movies, 610 users, 100k+ ratings)

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Neo4j Desktop 5.x (or Neo4j Server)

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/graphflix.git
cd graphflix
```

### 2. Setup Neo4j Database

**Option A: Use Pre-configured Database (Recommended)**

The `DB/` folder contains a ready-to-use Neo4j database with MovieLens data already imported.

1. Open Neo4j Desktop
2. Create a new project: "GraphFlix"
3. Click "Add" → "File" → Select the `DB/` folder
4. Start the database
5. Note your password (you'll need it in step 3)

**Option B: Import Data Manually**

You can create your own Neo4j database from **MovieLens** (included in this repo) or any other dataset. The recommendation algorithms in `graphflix-api/` assume a small **schema contract** — if your graph matches this structure, the API will work.

**Required graph structure (minimum contract)**

- Nodes:
  - `(:User {userId: <int>})`
  - `(:Movie {movieId: <int>, title: <string>, ...})`
  - `(:Genre {name: <string>})`
- Relationships:
  - `(u:User)-[:RATED {rating: <float>}]->(m:Movie)`
  - `(m:Movie)-[:IN_GENRE]->(g:Genre)`

**Rating scale note**

The Cypher queries are tuned for the MovieLens-style rating scale (0.5–5.0). If you import another dataset (e.g., 1–10, thumbs up/down, etc.), you should normalize ratings to ~0–5 or adjust the query constants (e.g., the “liked” threshold `>= 4.0`, the alignment tolerance `<= 1.0`, and the normalization `(predictedRating - 0.5) / 4.5`).

**Optional (enables richer explanations / better content signals)**

- Actors: connect movies to actor/person nodes via one of `:ACTED_IN` (preferred for the graph UI), `:HAS_ACTOR`, or `:FEATURES_ACTOR`.
  - Actor/person nodes should have a `name` property for nicer labels in the UI.
- Directors: connect movies to director/person nodes via one of `:DIRECTED` (preferred), `:DIRECTED_BY`, or `:HAS_DIRECTOR`.
- Recency boost: set `Movie.year` or `Movie.releaseYear` (used by the hybrid algorithm; if missing, it gracefully falls back).

If you use a different dataset, just map your data into these labels, relationship types, and properties.

**MovieLens import (ml-latest-small) via Cypher `LOAD CSV`**

1. Create a new empty database in Neo4j Desktop.
2. Copy the repo folder `ml-latest-small/` into Neo4j's `import/` directory.
   - If Neo4j cannot access local CSVs, verify `dbms.security.allow_csv_import_from_file_urls=true` and that the files are inside the configured import directory.
3. Open Neo4j Browser and run the following statements:

```cypher
// Constraints (recommended)
CREATE CONSTRAINT user_userId IF NOT EXISTS
FOR (u:User) REQUIRE u.userId IS UNIQUE;

CREATE CONSTRAINT movie_movieId IF NOT EXISTS
FOR (m:Movie) REQUIRE m.movieId IS UNIQUE;

CREATE CONSTRAINT genre_name IF NOT EXISTS
FOR (g:Genre) REQUIRE g.name IS UNIQUE;

// Movies + genres
LOAD CSV WITH HEADERS FROM 'file:///ml-latest-small/movies.csv' AS row
WITH row, trim(row.title) AS title
WITH row, title,
     CASE
       WHEN title =~ '.*\\(\\d{4}\\)$' THEN toInteger(substring(title, size(title) - 5, 4))
       ELSE null
     END AS year
MERGE (m:Movie {movieId: toInteger(row.movieId)})
SET m.title = title,
    m.year = year
WITH m, row
UNWIND split(coalesce(row.genres, ''), '|') AS genreName
WITH m, trim(genreName) AS genreName
WHERE genreName <> '' AND genreName <> '(no genres listed)'
MERGE (g:Genre {name: genreName})
MERGE (m)-[:IN_GENRE]->(g);

// Optional: IMDb/TMDB ids (useful for posters)
LOAD CSV WITH HEADERS FROM 'file:///ml-latest-small/links.csv' AS row
MATCH (m:Movie {movieId: toInteger(row.movieId)})
SET m.imdbId = row.imdbId,
    m.tmdbId = CASE
      WHEN row.tmdbId IS NULL OR row.tmdbId = '' THEN null
      ELSE toInteger(row.tmdbId)
    END;

// Users + ratings
LOAD CSV WITH HEADERS FROM 'file:///ml-latest-small/ratings.csv' AS row
MATCH (m:Movie {movieId: toInteger(row.movieId)})
MERGE (u:User {userId: toInteger(row.userId)})
MERGE (u)-[r:RATED]->(m)
SET r.rating = toFloat(row.rating),
    r.timestamp = toInteger(row.timestamp);
```

### 3. Configure Backend

```bash
cd graphflix-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your Neo4j credentials:
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your_password
```

### 4. Configure Frontend

```bash
cd ../graphflix-frontend

# Install dependencies
npm install

# Setup environment (optional - for TMDB posters)
cp .env.example .env
# Edit .env:
# VITE_API_URL=http://localhost:8000
# VITE_TMDB_API_KEY=your_tmdb_key  # Optional
```

### 5. Run Application

**Terminal 1 - Backend:**
```bash
cd graphflix-api
source venv/bin/activate  # Windows: venv\Scripts\activate
uvicorn app.main:app --reload
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

**Terminal 2 - Frontend:**
```bash
cd graphflix-frontend
npm run dev
```

Frontend runs at: http://localhost:5173

### 6. Access Application

1. Open http://localhost:5173
2. Enter a user ID (1-610)
3. Choose an algorithm
4. Explore recommendations and graph visualization!

---

## API Endpoints

Base URL: `http://localhost:8000/api/v1`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/recommendations/{user_id}` | GET | Collaborative filtering recommendations |
| `/recommendations/{user_id}/content` | GET | Content-based recommendations |
| `/recommendations/hybrid` | POST | Hybrid algorithm with weights |
| `/recommendations/custom` | POST | Configurable 4-component scoring |
| `/movies/{movie_id}` | GET | Movie details |
| `/movies/{movie_id}/similar` | GET | Similar movies |
| `/users/{user_id}/stats` | GET | User statistics |
| `/graph/user/{user_id}` | GET | User graph neighborhood |
| `/graph/explain/user/{user_id}/movie/{movie_id}` | GET | Recommendation explanation graph |

Full API documentation: http://localhost:8000/docs

---

## Screenshots

*Screenshots coming soon*

---

## Project Structure

graphflix/
├── graphflix-api/           # FastAPI backend
│   ├── app/
│   │   ├── main.py         # Application entry point
│   │   ├── config.py       # Environment configuration
│   │   ├── database.py     # Neo4j connection
│   │   ├── routers/        # API endpoints
│   │   ├── services/       # Business logic
│   │   ├── queries/        # Cypher queries
│   │   └── models/         # Pydantic schemas
│   ├── requirements.txt
│   └── .env.example
│
├── graphflix-frontend/      # Svelte frontend
│   ├── src/
│   │   ├── App.svelte      # Root component
│   │   ├── routes/         # Page components
│   │   └── lib/            # Shared utilities
│   ├── package.json
│   └── vite.config.js
│
├── DB/                      # Pre-configured Neo4j database
└── README.md

---

## Testing

**Backend:**
```bash
cd graphflix-api
./validate.sh  # Runs syntax checks and query validation
```

**Manual API Testing:**
```bash
# Collaborative recommendations
curl http://localhost:8000/api/v1/recommendations/1?limit=10

# Hybrid with custom weights
curl -X POST http://localhost:8000/api/v1/recommendations/hybrid \
  -H "Content-Type: application/json" \
  -d '{"userId": "1", "weights": {"collaborativeWeight": 0.7, "contentWeight": 0.3}, "limit": 10}'
```

---

## Academic Context

This project was developed as a 10-week individual course project for COMP460 - Capstone Project, demonstrating:
- Advanced graph database modeling and querying
- Production-grade recommendation algorithms (Jaccard similarity, hybrid fusion)
- Full-stack web development with modern frameworks
- Data visualization for explainable AI

---

## Acknowledgments

- **MovieLens Dataset**: GroupLens Research (University of Minnesota)
- **TMDB API**: The Movie Database for poster images
- **Neo4j**: For excellent graph database documentation
- **FastAPI & Svelte Communities**: For comprehensive documentation and examples

---

## Known Issues

None currently. Report issues on GitHub Issues page.

---

## Tips for Running

1. **Performance**: First query may be slow (cold start). Subsequent queries are faster.
2. **User IDs**: Valid range is 1-610 (MovieLens dataset users)
3. **TMDB Posters**: Optional - app works without TMDB API key (shows placeholder)
4. **Neo4j Memory**: Recommended 4GB heap size for smooth performance

---

**Star ⭐ this repo if you found it useful!**

Built with ❤️.