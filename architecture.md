# Hybrid Graph Memory MCP Architecture

## Runtime

- Python: active local Python environment
- MCP SDK: `mcp[cli]==1.28.0`
- Server framework: `mcp.server.fastmcp.FastMCP`
- Transport: FastMCP streamable HTTP
- Host and port: `127.0.0.1:2618`
- MCP path: `/mcp`

## Modules

### `server.py`

Defines the FastMCP server and exposes the five tools from `plan.md`:

- `memory_record`
- `memory_link_candidates`
- `memory_create_link`
- `memory_graph_search`
- `memory_update`
- `memory_graph_app`
- `memory_query_graph_app`

The file also exposes local browser apps using FastMCP `custom_route`:

- `/apps/memory-graph`
- `/apps/memory-graph.json`
- `/apps/query-graph`
- `/apps/query-graph.json`

Most memory behavior delegates to `memory_store.py`; `server.py` owns the HTTP app shell.

### `memory_store.py`

Owns all memory behavior:

- file initialization
- JSONL reads and appends
- record IDs
- simple entity extraction
- deterministic token embeddings
- cosine similarity
- graph edge creation
- graph-expanded search
- full graph snapshots
- query graph snapshots
- update history
- event logging
- generated wiki summary

### `seed_syllabus_memory.py`

Parses `Syllabus - Model Context Protocol for AI Agents.docx`, creates a curated sample memory set, and adds verified graph links for the demo.

## Storage Model

Data is stored under `memory/` by default. Set `MEMORY_MCP_DIR` to use a different storage folder.

### `memory/records.jsonl`

Append-only memory records with:

- `id`
- `text`
- `type`
- `tags`
- `source`
- `created_at`

### `memory/entities.jsonl`

Simple concept nodes extracted from records.

### `memory/edges.jsonl`

Graph links between records and entities. Entity `mentions` edges are created automatically. Record-to-record edges are created through verified tools or updates.

### `memory/embeddings.json`

Deterministic token vectors keyed by record ID. This keeps the demo local and reproducible without an external embedding model.

### `memory/events.jsonl`

Audit log for record creation, link creation, updates, and graph searches.

### `memory/wiki/preferences.md`

Generated human-readable summary of active and superseded memories.

## Retrieval Flow

1. Tokenize and embed the query.
2. Rank records by deterministic vector similarity plus a small keyword-overlap bonus.
3. Use top records as search seeds.
4. Expand through verified record links and shared entity mentions up to `hops`.
5. Return evidence with provenance, timestamps, graph links, and active/superseded status.

## Graph App Flow

The complete graph app reads `graph_snapshot()` and lays out all record and entity nodes.

The query graph app reads `query_graph_snapshot(query, hops, top_k)`, highlights direct search matches, groups expanded records by hop level, includes mentioned entities, and shows evidence metadata in a side panel.

## Update Flow

`memory_update` never edits an old record in place.

1. Read the old record.
2. Create a new record with the new text.
3. Add a verified edge from the new record to the old record.
4. Use the requested update type, such as `supersedes` or `corrects`.
5. Mark old records as superseded during search and wiki summary generation.

## Package Notes

The only required package is the official MCP SDK:

```text
mcp[cli]==1.28.0
```

That package brings FastMCP plus its HTTP server dependencies, including Starlette and Uvicorn.
