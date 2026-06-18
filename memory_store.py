from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEMORY_DIR = Path(os.environ.get("MEMORY_MCP_DIR", Path(__file__).parent / "memory"))
RECORDS_PATH = MEMORY_DIR / "records.jsonl"
ENTITIES_PATH = MEMORY_DIR / "entities.jsonl"
EDGES_PATH = MEMORY_DIR / "edges.jsonl"
EMBEDDINGS_PATH = MEMORY_DIR / "embeddings.json"
EVENTS_PATH = MEMORY_DIR / "events.jsonl"
WIKI_DIR = MEMORY_DIR / "wiki"
PREFERENCES_PATH = WIKI_DIR / "preferences.md"

UPDATE_TYPES = {
    "supersedes",
    "contradicts",
    "narrows_scope",
    "broadens_scope",
    "corrects",
    "related_to",
}

EDGE_TYPES = UPDATE_TYPES | {"mentions", "same_as", "supports"}

STOPWORDS = {
    "a",
    "about",
    "actually",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "being",
    "but",
    "by",
    "can",
    "for",
    "from",
    "have",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "now",
    "of",
    "or",
    "should",
    "that",
    "the",
    "then",
    "to",
    "under",
    "user",
    "what",
    "when",
    "with",
}

DOMAIN_PHRASES = [
    "teaching prep",
    "project check-ins",
    "project checkins",
    "calendar changes",
    "default meetings",
    "scheduling preferences",
]

SYNONYMS = {
    "appointment": ["calendar", "meeting", "schedule"],
    "calendar": ["schedule", "scheduling"],
    "class": ["teaching", "workshop"],
    "current": ["active", "default", "now"],
    "meeting": ["appointment", "calendar", "schedule"],
    "preference": ["prefer"],
    "prefer": ["preference"],
    "scheduling": ["calendar", "meeting", "schedule"],
    "schedule": ["calendar", "meeting", "scheduling"],
    "teaching": ["class"],
    "workshop": ["class", "teaching"],
}


def initialize_store() -> None:
    MEMORY_DIR.mkdir(exist_ok=True)
    WIKI_DIR.mkdir(exist_ok=True)
    for path in (RECORDS_PATH, ENTITIES_PATH, EDGES_PATH, EVENTS_PATH):
        path.touch(exist_ok=True)
    if not EMBEDDINGS_PATH.exists():
        EMBEDDINGS_PATH.write_text("{}\n", encoding="utf-8")
    if not PREFERENCES_PATH.exists():
        PREFERENCES_PATH.write_text("# Memory Summary\n\nNo memories recorded yet.\n", encoding="utf-8")


def create_memory_record(text: str, source: str, tags: list[str] | None = None) -> dict[str, Any]:
    text = _clean_required(text, "text")
    source = _clean_required(source, "source")
    clean_tags = _clean_tags(tags)
    initialize_store()

    records = load_records()
    embeddings = load_embeddings()
    record_id = _next_id(records, "rec")
    vector = embed_text(text)
    similar = _similarity_candidates(record_id, vector, records, embeddings, top_k=10)

    record = {
        "id": record_id,
        "text": text,
        "type": infer_record_type(text, clean_tags),
        "tags": clean_tags,
        "source": source,
        "created_at": _now_iso(),
    }
    _append_jsonl(RECORDS_PATH, record)

    embeddings[record_id] = vector
    save_embeddings(embeddings)

    entities = upsert_entities(extract_entities(text, clean_tags))
    mention_edges = []
    for entity in entities:
        edge = {
            "from": record_id,
            "to": entity["id"],
            "type": "mentions",
            "reason": f"Extracted entity '{entity['name']}' from memory text.",
            "confidence": 0.9,
            "verified": True,
            "created_at": _now_iso(),
        }
        _append_jsonl(EDGES_PATH, edge)
        mention_edges.append(edge)

    candidates = [
        {
            "from": record_id,
            "to": candidate["id"],
            "type": suggest_link_type(text, candidate["text"]),
            "method": "vector_similarity",
            "similarity": candidate["similarity"],
            "verified": False,
            "reason": "Candidate relationship based on embedding/token similarity.",
        }
        for candidate in similar
    ]

    _log_event(
        "memory_recorded",
        {
            "record_id": record_id,
            "entity_ids": [entity["id"] for entity in entities],
            "candidate_count": len(candidates),
        },
    )
    refresh_wiki_summary()
    return {
        "record": record,
        "entities": entities,
        "mention_edges": mention_edges,
        "link_candidates": candidates,
    }


def link_candidates(record_id: str, top_k: int = 10) -> dict[str, Any]:
    initialize_store()
    top_k = _clamp_top_k(top_k)
    record = get_record(record_id)
    if record is None:
        raise ValueError(f"Unknown record_id: {record_id}")

    embeddings = load_embeddings()
    vector = embeddings.get(record_id) or embed_text(record["text"])
    records = [item for item in load_records() if item["id"] != record_id]
    record_candidates = _similarity_candidates(record_id, vector, records, embeddings, top_k)

    entity_hits = []
    record_tokens = set(tokenize(record["text"]))
    for entity in load_entities():
        aliases = set(entity.get("aliases", [])) | {entity["name"]}
        score = sum(1 for alias in aliases if record_tokens & set(tokenize(alias)))
        if score:
            entity_hits.append(
                {
                    "id": entity["id"],
                    "name": entity["name"],
                    "type": entity["type"],
                    "score": score,
                }
            )

    return {
        "record_id": record_id,
        "record_candidates": [
            {
                "id": candidate["id"],
                "text": candidate["text"],
                "similarity": candidate["similarity"],
                "suggested_type": suggest_link_type(record["text"], candidate["text"]),
                "source": candidate["source"],
                "created_at": candidate["created_at"],
            }
            for candidate in record_candidates
        ],
        "entity_candidates": sorted(entity_hits, key=lambda item: item["score"], reverse=True)[:top_k],
    }


def create_link(
    from_id: str,
    to_id: str,
    link_type: str,
    reason: str,
    confidence: float,
) -> dict[str, Any]:
    initialize_store()
    link_type = _clean_required(link_type, "link_type")
    reason = _clean_required(reason, "reason")
    if link_type not in EDGE_TYPES:
        raise ValueError(f"Unsupported link_type '{link_type}'. Use one of: {sorted(EDGE_TYPES)}")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if not node_exists(from_id):
        raise ValueError(f"Unknown from_id: {from_id}")
    if not node_exists(to_id):
        raise ValueError(f"Unknown to_id: {to_id}")

    edge = {
        "from": from_id,
        "to": to_id,
        "type": link_type,
        "reason": reason,
        "confidence": round(float(confidence), 4),
        "verified": True,
        "created_at": _now_iso(),
    }
    _append_jsonl(EDGES_PATH, edge)
    _log_event("memory_link_created", {"edge": edge})
    refresh_wiki_summary()
    return {"edge": edge}


def graph_search(query: str, hops: int = 2, top_k: int = 10) -> dict[str, Any]:
    initialize_store()
    query = _clean_required(query, "query")
    hops = max(0, min(int(hops), 4))
    top_k = _clamp_top_k(top_k)

    records = load_records()
    embeddings = load_embeddings()
    query_vector = embed_text(query)
    seeds = _similarity_candidates("query", query_vector, records, embeddings, top_k)
    seed_ids = {seed["id"] for seed in seeds}

    edges = load_edges()
    adjacency = _record_adjacency(edges)
    visited = set(seed_ids)
    queue = deque((record_id, 0) for record_id in seed_ids)
    while queue:
        current, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbor in adjacency.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    record_by_id = {record["id"]: record for record in records}
    superseded_by = _superseded_by(edges)
    seed_score = {seed["id"]: seed["similarity"] for seed in seeds}
    evidence = []
    for record_id in visited:
        record = record_by_id.get(record_id)
        if not record:
            continue
        connected_edges = [
            edge
            for edge in edges
            if edge.get("from") == record_id or edge.get("to") == record_id
        ]
        graph_bonus = 0.05 * len([edge for edge in connected_edges if edge.get("type") != "mentions"])
        evidence.append(
            {
                "record": record,
                "score": round(seed_score.get(record_id, 0.0) + graph_bonus, 4),
                "status": "superseded" if record_id in superseded_by else "active",
                "superseded_by": superseded_by.get(record_id),
                "links": connected_edges,
            }
        )

    evidence.sort(
        key=lambda item: (
            item["status"] != "active",
            -item["score"],
            item["record"]["created_at"],
        )
    )
    _log_event("memory_graph_searched", {"query": query, "seed_ids": list(seed_ids), "result_count": len(evidence)})
    return {
        "query": query,
        "seed_records": seeds,
        "hops": hops,
        "evidence": evidence[:top_k],
    }


def graph_snapshot() -> dict[str, Any]:
    initialize_store()
    records = load_records()
    entities = load_entities()
    edges = load_edges()
    superseded_by = _superseded_by(edges)
    degree = _degree_counts(edges)

    nodes = []
    for record in records:
        nodes.append(
            {
                "id": record["id"],
                "label": record["id"],
                "kind": "record",
                "type": record.get("type", "note"),
                "text": record.get("text", ""),
                "tags": record.get("tags", []),
                "source": record.get("source", ""),
                "created_at": record.get("created_at", ""),
                "status": "superseded" if record["id"] in superseded_by else "active",
                "superseded_by": superseded_by.get(record["id"]),
                "degree": degree.get(record["id"], 0),
            }
        )
    for entity in entities:
        nodes.append(
            {
                "id": entity["id"],
                "label": entity.get("name", entity["id"]),
                "kind": "entity",
                "type": entity.get("type", "concept"),
                "aliases": entity.get("aliases", []),
                "created_at": entity.get("created_at", ""),
                "degree": degree.get(entity["id"], 0),
            }
        )

    return {
        "nodes": nodes,
        "edges": _public_edges(edges),
        "stats": {
            "records": len(records),
            "entities": len(entities),
            "edges": len(edges),
            "active_records": len([node for node in nodes if node["kind"] == "record" and node["status"] == "active"]),
            "superseded_records": len([node for node in nodes if node["kind"] == "record" and node["status"] == "superseded"]),
        },
    }


def query_graph_snapshot(query: str, hops: int = 2, top_k: int = 10) -> dict[str, Any]:
    initialize_store()
    search = graph_search(query=query, hops=hops, top_k=top_k)
    records = load_records()
    entities = load_entities()
    edges = load_edges()
    record_by_id = {record["id"]: record for record in records}
    entity_by_id = {entity["id"]: entity for entity in entities}
    seed_ids = {record["id"] for record in search["seed_records"]}
    included_record_ids = {item["record"]["id"] for item in search["evidence"]}
    levels = _record_levels(seed_ids, max(0, min(int(hops), 4)), _record_adjacency(edges))
    evidence_by_id = {item["record"]["id"]: item for item in search["evidence"]}

    included_entity_ids = {
        edge["to"]
        for edge in edges
        if edge.get("type") == "mentions"
        and edge.get("from") in included_record_ids
        and str(edge.get("to", "")).startswith("ent_")
    }
    included_ids = included_record_ids | included_entity_ids

    nodes = []
    for record_id in sorted(included_record_ids):
        record = record_by_id[record_id]
        evidence = evidence_by_id.get(record_id, {})
        nodes.append(
            {
                "id": record_id,
                "label": record_id,
                "kind": "record",
                "type": record.get("type", "note"),
                "text": record.get("text", ""),
                "tags": record.get("tags", []),
                "source": record.get("source", ""),
                "created_at": record.get("created_at", ""),
                "status": evidence.get("status", "active"),
                "score": evidence.get("score", 0.0),
                "level": levels.get(record_id, 0 if record_id in seed_ids else None),
                "direct_match": record_id in seed_ids,
                "superseded_by": evidence.get("superseded_by"),
            }
        )
    for entity_id in sorted(included_entity_ids):
        entity = entity_by_id.get(entity_id)
        if entity:
            nodes.append(
                {
                    "id": entity_id,
                    "label": entity.get("name", entity_id),
                    "kind": "entity",
                    "type": entity.get("type", "concept"),
                    "aliases": entity.get("aliases", []),
                    "level": "entity",
                    "direct_match": False,
                }
            )

    graph_edges = [
        edge
        for edge in edges
        if edge.get("from") in included_ids and edge.get("to") in included_ids
    ]

    return {
        "query": query,
        "hops": search["hops"],
        "top_k": _clamp_top_k(top_k),
        "direct_records": [record["id"] for record in search["seed_records"]],
        "nodes": nodes,
        "edges": _public_edges(graph_edges),
        "evidence": search["evidence"],
        "stats": {
            "direct_records": len(seed_ids),
            "records_shown": len(included_record_ids),
            "entities_shown": len(included_entity_ids),
            "edges_shown": len(graph_edges),
        },
    }


def update_memory(record_id: str, new_text: str, update_type: str, reason: str) -> dict[str, Any]:
    initialize_store()
    if update_type not in UPDATE_TYPES:
        raise ValueError(f"Unsupported update_type '{update_type}'. Use one of: {sorted(UPDATE_TYPES)}")
    old_record = get_record(record_id)
    if old_record is None:
        raise ValueError(f"Unknown record_id: {record_id}")

    created = create_memory_record(new_text, source="memory_update", tags=old_record.get("tags", []))
    edge = create_link(
        from_id=created["record"]["id"],
        to_id=record_id,
        link_type=update_type,
        reason=reason,
        confidence=0.95,
    )["edge"]
    _log_event(
        "memory_updated",
        {
            "old_record_id": record_id,
            "new_record_id": created["record"]["id"],
            "update_type": update_type,
        },
    )
    refresh_wiki_summary()
    return {
        "old_record": old_record,
        "new_record": created["record"],
        "update_edge": edge,
        "link_candidates": created["link_candidates"],
    }


def load_records() -> list[dict[str, Any]]:
    return _read_jsonl(RECORDS_PATH)


def load_entities() -> list[dict[str, Any]]:
    return _read_jsonl(ENTITIES_PATH)


def load_edges() -> list[dict[str, Any]]:
    return _read_jsonl(EDGES_PATH)


def load_embeddings() -> dict[str, dict[str, float]]:
    initialize_store()
    try:
        return json.loads(EMBEDDINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_embeddings(embeddings: dict[str, dict[str, float]]) -> None:
    EMBEDDINGS_PATH.write_text(json.dumps(embeddings, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_record(record_id: str) -> dict[str, Any] | None:
    return next((record for record in load_records() if record.get("id") == record_id), None)


def node_exists(node_id: str) -> bool:
    if node_id.startswith("rec_"):
        return get_record(node_id) is not None
    if node_id.startswith("ent_"):
        return any(entity.get("id") == node_id for entity in load_entities())
    return False


def infer_record_type(text: str, tags: list[str]) -> str:
    lowered = text.lower()
    if "prefer" in lowered or "should" in lowered or "require" in lowered or "reserve" in lowered:
        return "preference"
    if "actually" in lowered or "correct" in lowered or "now" in lowered:
        return "update"
    if tags:
        return tags[0]
    return "note"


def extract_entities(text: str, tags: list[str]) -> list[str]:
    lowered = text.lower()
    entities = []
    for phrase in DOMAIN_PHRASES:
        if phrase in lowered:
            entities.append(phrase.replace("checkins", "check-ins"))

    tokens = tokenize(text)
    for token in tokens:
        if token not in STOPWORDS and len(token) >= 4:
            entities.append(_canonical_entity_name(token))
    for tag in tags:
        entities.append(_canonical_entity_name(tag))

    unique = []
    seen = set()
    for entity in entities:
        entity = entity.strip("- ")
        if entity and entity not in seen:
            unique.append(entity)
            seen.add(entity)
    return unique[:8]


def upsert_entities(names: list[str]) -> list[dict[str, Any]]:
    existing = {entity["id"]: entity for entity in load_entities()}
    created_or_reused = []
    for name in names:
        entity_id = f"ent_{_slugify(name)}"
        entity = existing.get(entity_id)
        if entity is None:
            entity = {
                "id": entity_id,
                "name": name,
                "type": "concept",
                "aliases": sorted(_entity_aliases(name)),
                "created_at": _now_iso(),
            }
            _append_jsonl(ENTITIES_PATH, entity)
            existing[entity_id] = entity
        created_or_reused.append(entity)
    return created_or_reused


def tokenize(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", text.lower())
    tokens = []
    for raw_token in raw_tokens:
        token = _canonical_token(raw_token)
        if not token or token in STOPWORDS:
            continue
        tokens.append(token)
        tokens.extend(SYNONYMS.get(token, []))
    return tokens


def embed_text(text: str) -> dict[str, float]:
    tokens = tokenize(text)
    if not tokens:
        return {}
    counts = Counter(tokens)
    length = math.sqrt(sum(count * count for count in counts.values())) or 1
    return {token: round(count / length, 6) for token, count in sorted(counts.items())}


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    return sum(left[token] * right[token] for token in common)


def suggest_link_type(new_text: str, existing_text: str) -> str:
    lowered_new = new_text.lower()
    lowered_existing = existing_text.lower()
    if any(word in lowered_new for word in ("actually", "now", "instead", "correct")):
        return "supersedes"
    specific_contexts = ("teaching prep", "workshop", "class", "project", "check-in")
    if any(term in lowered_new for term in specific_contexts) and _topic_overlap(lowered_new, lowered_existing):
        return "narrows_scope"
    return "related_to"


def refresh_wiki_summary() -> None:
    records = load_records()
    edges = load_edges()
    superseded_by = _superseded_by(edges)
    lines = [
        "# Memory Summary",
        "",
        "Generated from records, graph edges, timestamps, and provenance.",
        "",
        "## Active Records",
        "",
    ]
    active_records = [record for record in records if record["id"] not in superseded_by]
    if not active_records:
        lines.append("No active records.")
    else:
        for record in active_records:
            lines.append(f"- `{record['id']}` {record['text']} ({record['source']}, {record['created_at']})")

    lines.extend(["", "## Superseded Or Corrected Records", ""])
    old_records = [record for record in records if record["id"] in superseded_by]
    if not old_records:
        lines.append("No superseded or corrected records.")
    else:
        for record in old_records:
            lines.append(f"- `{record['id']}` {record['text']} -> replaced by `{superseded_by[record['id']]}`")

    PREFERENCES_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _similarity_candidates(
    record_id: str,
    vector: dict[str, float],
    records: list[dict[str, Any]],
    embeddings: dict[str, dict[str, float]],
    top_k: int,
) -> list[dict[str, Any]]:
    candidates = []
    for record in records:
        other_id = record["id"]
        if other_id == record_id:
            continue
        other_vector = embeddings.get(other_id) or embed_text(record["text"])
        similarity = cosine_similarity(vector, other_vector)
        keyword_bonus = _keyword_bonus(set(vector), set(other_vector))
        score = min(1.0, similarity + keyword_bonus)
        if score >= 0.12:
            candidate = dict(record)
            candidate["similarity"] = round(score, 4)
            candidates.append(candidate)
    return sorted(candidates, key=lambda item: item["similarity"], reverse=True)[:top_k]


def _keyword_bonus(left: set[str], right: set[str]) -> float:
    overlap = left & right
    if not overlap:
        return 0.0
    return min(0.15, len(overlap) * 0.03)


def _record_adjacency(edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if not source or not target:
            continue
        if source.startswith("rec_") and target.startswith("rec_"):
            adjacency.setdefault(source, []).append(target)
            adjacency.setdefault(target, []).append(source)
        elif source.startswith("rec_") and target.startswith("ent_"):
            for other in _records_mentioning(target, edges):
                if other != source:
                    adjacency.setdefault(source, []).append(other)
                    adjacency.setdefault(other, []).append(source)

    return {key: sorted(set(value)) for key, value in adjacency.items()}


def _record_levels(seed_ids: set[str], hops: int, adjacency: dict[str, list[str]]) -> dict[str, int]:
    levels = {record_id: 0 for record_id in seed_ids}
    queue = deque((record_id, 0) for record_id in seed_ids)
    while queue:
        current, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbor in adjacency.get(current, []):
            next_depth = depth + 1
            if neighbor not in levels or next_depth < levels[neighbor]:
                levels[neighbor] = next_depth
                queue.append((neighbor, next_depth))
    return levels


def _degree_counts(edges: list[dict[str, Any]]) -> dict[str, int]:
    degree: dict[str, int] = {}
    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if source:
            degree[source] = degree.get(source, 0) + 1
        if target:
            degree[target] = degree.get(target, 0) + 1
    return degree


def _public_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": edge.get("from"),
            "target": edge.get("to"),
            "type": edge.get("type"),
            "reason": edge.get("reason", ""),
            "confidence": edge.get("confidence"),
            "verified": edge.get("verified", False),
            "created_at": edge.get("created_at", ""),
        }
        for edge in edges
    ]


def _records_mentioning(entity_id: str, edges: list[dict[str, Any]]) -> list[str]:
    return [
        edge["from"]
        for edge in edges
        if edge.get("type") == "mentions" and edge.get("to") == entity_id and str(edge.get("from", "")).startswith("rec_")
    ]


def _superseded_by(edges: list[dict[str, Any]]) -> dict[str, str]:
    replacement_types = {"supersedes", "corrects"}
    return {
        edge["to"]: edge["from"]
        for edge in edges
        if edge.get("type") in replacement_types
        and edge.get("verified")
        and str(edge.get("from", "")).startswith("rec_")
        and str(edge.get("to", "")).startswith("rec_")
    }


def _topic_overlap(left: str, right: str) -> bool:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    return bool(left_tokens & right_tokens)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    initialize_store()
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _log_event(event_type: str, payload: dict[str, Any]) -> None:
    _append_jsonl(
        EVENTS_PATH,
        {
            "type": event_type,
            "payload": payload,
            "created_at": _now_iso(),
        },
    )


def _next_id(records: list[dict[str, Any]], prefix: str) -> str:
    numbers = []
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    for record in records:
        match = pattern.match(record.get("id", ""))
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}_{max(numbers, default=0) + 1:03d}"


def _clean_required(value: str, name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{name} is required")
    return cleaned


def _clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    return sorted({str(tag).strip().lower() for tag in tags if str(tag).strip()})


def _clamp_top_k(top_k: int) -> int:
    return max(1, min(int(top_k), 50))


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _canonical_token(token: str) -> str:
    token = token.strip("'-").lower()
    if token.endswith("'s"):
        token = token[:-2]
    if token.endswith("ies") and len(token) > 4:
        token = token[:-3] + "y"
    elif token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
        token = token[:-1]
    return token


def _canonical_entity_name(name: str) -> str:
    name = " ".join(_canonical_token(token) for token in re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", name.lower()))
    return name.strip()


def _entity_aliases(name: str) -> set[str]:
    aliases = {name}
    if name.endswith("y"):
        aliases.add(name[:-1] + "ies")
    elif not name.endswith("s"):
        aliases.add(name + "s")
    return aliases


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "unknown"
