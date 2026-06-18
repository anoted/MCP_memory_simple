# Hybrid Graph Memory MCP Usage

## Install

Use the appropriate Python environment for this folder


## Start the Server

```powershell
python server.py
```

The MCP endpoint is:

```text
http://localhost:2618/mcp
```

The server uses FastMCP's streamable HTTP transport.

The local graph apps are:

```text
http://localhost:2618/apps/memory-graph
http://localhost:2618/apps/query-graph
```

## Connect a Host App

Configure an MCP client that supports streamable HTTP with this server URL:

```json
{
  "mcpServers": {
    "hybrid-graph-memory": {
      "url": "http://localhost:2618/mcp"
    }
  }
}
```

## Tools

### `memory_record(text, source, tags=None)`

Creates a durable memory record, extracts simple entities, writes mention edges, stores a deterministic embedding, and returns candidate links.

Example:

```json
{
  "text": "I prefer 25-minute meetings.",
  "source": "conversation",
  "tags": ["calendar"]
}
```

### `memory_link_candidates(record_id, top_k=10)`

Returns similar records and matching entities for a record.

### `memory_create_link(from_id, to_id, link_type, reason, confidence)`

Creates a verified graph edge. Supported relationship types are:

```text
mentions
supersedes
contradicts
narrows_scope
broadens_scope
corrects
related_to
same_as
supports
```

### `memory_graph_search(query, hops=2, top_k=10)`

Runs token/vector search first, then expands through graph links and entity mentions.

### `memory_update(record_id, new_text, update_type, reason)`

Creates a new record and links it to the old record. Supported update types are:

```text
supersedes
contradicts
narrows_scope
broadens_scope
corrects
related_to
```

### `memory_graph_app()`

Returns the local URL for the full memory graph app and its JSON data endpoint.

### `memory_query_graph_app(query="MCP course learning outcomes", hops=2, top_k=10)`

Returns the local URL for the query-focused graph app and its JSON data endpoint.

## Seed Sample Memory

Seed the sample graph from `Syllabus - Model Context Protocol for AI Agents.docx`:

```powershell
python seed_syllabus_memory.py
```

The script adds curated syllabus records and verified links. It skips duplicate seeding if records from the same syllabus source already exist.

## Files Written

Data is stored under:

```text
memory/
  records.jsonl
  entities.jsonl
  edges.jsonl
  embeddings.json
  events.jsonl
  wiki/
    preferences.md
```

Delete the `memory/` directory if you want a fresh classroom demo run.

For tests or alternate runs, set `MEMORY_MCP_DIR` before starting the server:

```powershell
$env:MEMORY_MCP_DIR = "C:\path\to\scratch-memory"
python server.py
```
