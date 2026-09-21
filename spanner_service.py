import json
import os
from typing import Any
from google.cloud import spanner
from embedding_service import generate_text_embedding


# Disable Spanner built-in metrics exporter by default to avoid missing label errors in Cloud Monitoring
os.environ.setdefault("SPANNER_DISABLE_BUILTIN_METRICS", "true")


def normalize_search_tags(tags: list[str] | str | None) -> list[str]:
    if not tags:
        return []
    if isinstance(tags, str):
        raw_list = [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, (list, tuple, set)):
        raw_list = [str(t).strip() for t in tags if t and str(t).strip()]
    else:
        raw_list = []
    seen = set()
    cleaned = []
    for t in raw_list:
        low = t.lower()
        if low and low not in seen:
            seen.add(low)
            cleaned.append(low)
    return cleaned


def rerank_hybrid_results(
    fulltext_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    limit: int = 10,
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Re-ranks hybrid search results using an enhanced Reciprocal Rank Fusion (RRF)
    algorithm integrated with dense vector similarity, full-text score normalization,
    and cross-modal consensus boosting.

    Mathematical Formulation:
      RRF_raw(d) = 1/(k + rank_vec(d)) + 1/(k + rank_fts(d))
      RRF_norm(d) = RRF_raw(d) / (2 / (k + 1))  # Normalized to [0.0, 1.0]
      Sim_vec(d) = max(0.0, 1.0 - distance(d))   # Normalized to [0.0, 1.0]
      Sim_fts(d) = fts_score(d) / max(fts_scores) # Normalized to [0.0, 1.0]
      Base_Score(d) = 0.50 * RRF_norm(d) + 0.30 * Sim_vec(d) + 0.20 * Sim_fts(d)
      If d matches both modalities: Score(d) = min(1.0, Base_Score(d) * 1.15)
    """
    candidates: dict[str, dict[str, Any]] = {}
    max_possible_rrf = (1.0 / (k + 1)) + (1.0 / (k + 1))

    # Determine max FTS score for normalization
    max_fts = 0.0
    for r in fulltext_results:
        f_score = r.get("fts_score")
        if f_score is not None and isinstance(f_score, (int, float)) and f_score > max_fts:
            max_fts = float(f_score)

    # 1. Process Vector Search candidates
    for rank_idx, vr in enumerate(vector_results, start=1):
        node_id = vr["id"]
        dist = vr.get("distance", 1.0)
        vec_sim = max(0.0, min(1.0, 1.0 - dist))
        rrf_vec = 1.0 / (k + rank_idx)

        candidates[node_id] = {
            "id": node_id,
            "label": vr.get("label", ""),
            "concept_id": vr.get("concept_id") or "",
            "name": vr.get("name") or "",
            "description": vr.get("description") or "",
            "contributor": vr.get("contributor") or {},
            "sources": vr.get("sources") or [],
            "tags": vr.get("tags") or [],
            "vector_distance": dist,
            "fts_score": None,
            "vector_rank": rank_idx,
            "fulltext_rank": None,
            "matched_by": ["vector"],
            "rrf_vec": rrf_vec,
            "rrf_fts": 0.0,
            "vec_sim": vec_sim,
            "fts_sim": 0.0,
        }

    # 2. Process Full Text Search candidates
    for rank_idx, ftr in enumerate(fulltext_results, start=1):
        node_id = ftr["id"]
        raw_fts = ftr.get("fts_score")
        if max_fts > 0 and raw_fts is not None:
            fts_sim = min(1.0, float(raw_fts) / max_fts)
        else:
            fts_sim = 1.0 / (1.0 + 0.1 * (rank_idx - 1))

        rrf_fts = 1.0 / (k + rank_idx)

        if node_id in candidates:
            # Overlapping match: confirmed by BOTH vector and FTS
            c = candidates[node_id]
            c["matched_by"].append("fulltext")
            c["fulltext_rank"] = rank_idx
            c["fts_score"] = raw_fts
            c["rrf_fts"] = rrf_fts
            c["fts_sim"] = fts_sim
            if not c.get("description") and ftr.get("description"):
                c["description"] = ftr.get("description")
            if not c.get("contributor") and ftr.get("contributor"):
                c["contributor"] = ftr.get("contributor")
            if not c.get("sources") and ftr.get("sources"):
                c["sources"] = ftr.get("sources")
            if not c.get("tags") and ftr.get("tags"):
                c["tags"] = ftr.get("tags")
        else:
            candidates[node_id] = {
                "id": node_id,
                "label": ftr.get("label", ""),
                "concept_id": ftr.get("concept_id") or "",
                "name": ftr.get("name") or "",
                "description": ftr.get("description") or "",
                "contributor": ftr.get("contributor") or {},
                "sources": ftr.get("sources") or [],
                "tags": ftr.get("tags") or [],
                "vector_distance": None,
                "fts_score": raw_fts,
                "vector_rank": None,
                "fulltext_rank": rank_idx,
                "matched_by": ["fulltext"],
                "rrf_vec": 0.0,
                "rrf_fts": rrf_fts,
                "vec_sim": 0.0,
                "fts_sim": fts_sim,
            }

    # 3. Compute hybrid score
    scored_items: list[dict[str, Any]] = []
    for c in candidates.values():
        total_rrf = c["rrf_vec"] + c["rrf_fts"]
        norm_rrf = total_rrf / max_possible_rrf

        # Blend: 50% normalized RRF, 30% vector similarity, 20% text similarity
        base_score = (0.50 * norm_rrf) + (0.30 * c["vec_sim"]) + (0.20 * c["fts_sim"])

        # Consensus boost: 15% bonus for items confirmed by BOTH search modalities
        if len(c["matched_by"]) > 1:
            final_score = min(1.0, base_score * 1.15)
        else:
            final_score = min(1.0, base_score)

        c["score"] = round(final_score, 4)
        scored_items.append(c)

    # 4. Sort descending by score; break ties using match count and vector distance
    def _sort_key(item: dict[str, Any]):
        score = item["score"]
        match_count = len(item["matched_by"])
        dist = item["vector_distance"] if item["vector_distance"] is not None else 999.0
        return (score, match_count, -dist)

    sorted_items = sorted(scored_items, key=_sort_key, reverse=True)

    # 5. Format final clean results with 1-based rank
    final_results: list[dict[str, Any]] = []
    for rank_idx, item in enumerate(sorted_items[:limit], start=1):
        final_results.append({
            "id": item["id"],
            "label": item["label"],
            "concept_id": item.get("concept_id") or "",
            "name": item.get("name") or "",
            "description": item.get("description") or "",
            "contributor": item.get("contributor") or {},
            "sources": item.get("sources") or [],
            "tags": item.get("tags") or [],
            "score": item["score"],
            "rank": rank_idx,
            "matched_by": item["matched_by"],
            "vector_distance": item["vector_distance"],
            "fts_score": item["fts_score"],
        })

    return final_results


class SpannerGraphService:
    def __init__(
        self,
        project_id: str | None = None,
        instance_id: str | None = None,
        database_id: str | None = None,
    ):
        self.project_id = project_id or os.getenv("GOOGLE_PROJECT")
        self.instance_id = instance_id or os.getenv("GOOGLE_SPANNER_INSTANCE")
        self.database_id = database_id or os.getenv("GOOGLE_SPANNER_DATABASE")

        self._client = None
        self._database = None

    def get_database(self):
        if self._database is None:
            if not all([self.project_id, self.instance_id, self.database_id]):
                raise ValueError(
                    "Missing Spanner environment configuration (GOOGLE_PROJECT, GOOGLE_SPANNER_INSTANCE, GOOGLE_SPANNER_DATABASE)"
                )
            disable_metrics = os.getenv("SPANNER_DISABLE_BUILTIN_METRICS", "true").lower() in ("true", "1")
            self._client = spanner.Client(
                project=self.project_id,
                disable_builtin_metrics=disable_metrics,
            )
            instance = self._client.instance(self.instance_id)
            self._database = instance.database(self.database_id)
        return self._database

    def upsert_graph(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> dict[str, int]:
        """
        Upserts nodes and edges into GraphNode and GraphEdge tables in Spanner.
        Generates and writes 768-dimensional Gemini vector embeddings for each node.
        Ensures nodes and edges are deduplicated and removes any invalid/null Tag nodes.
        """
        db = self.get_database()

        # Deduplicate nodes by unique id
        unique_nodes: dict[str, dict[str, Any]] = {}
        for n in nodes:
            if n and n.get("id"):
                unique_nodes[n["id"]] = n
        deduped_nodes = list(unique_nodes.values())

        # Deduplicate edges by (id, dest_id, edge_id)
        unique_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
        for e in edges:
            if e and e.get("id") and e.get("dest_id") and e.get("edge_id"):
                unique_edges[(e["id"], e["dest_id"], e["edge_id"])] = e
        deduped_edges = list(unique_edges.values())

        def _transaction_work(transaction):
            # Clean up any previously stored null/invalid Tag nodes or edges
            try:
                transaction.execute_update(
                    "DELETE FROM GraphEdge WHERE dest_id IN "
                    "(SELECT id FROM GraphNode WHERE label = 'Tag' AND "
                    "(JSON_VALUE(properties, '$.tag') IS NULL OR JSON_VALUE(properties, '$.tag') = 'null' OR JSON_VALUE(properties, '$.tag') = '' OR JSON_VALUE(properties, '$.tag') = 'none'))"
                )
                transaction.execute_update(
                    "DELETE FROM GraphNode WHERE label = 'Tag' AND "
                    "(JSON_VALUE(properties, '$.tag') IS NULL OR JSON_VALUE(properties, '$.tag') = 'null' OR JSON_VALUE(properties, '$.tag') = '' OR JSON_VALUE(properties, '$.tag') = 'none')"
                )
            except Exception:
                pass

            # Upsert nodes first (since edges interleave in GraphNode)
            node_columns = ["id", "label", "properties", "embedding"]
            node_values = []
            for n in deduped_nodes:
                props_dict = n["properties"] if isinstance(n["properties"], dict) else {}
                props_val = json.dumps(props_dict) if isinstance(n["properties"], dict) else n["properties"]
                
                # Extract title, description, and body text for Gemini embedding generation
                title_text = props_dict.get("name", "") or props_dict.get("title", "")
                desc_text = props_dict.get("description", "")
                body_text = props_dict.get("body", "")

                text_to_embed = f"{title_text}\n{desc_text}\n{body_text}".strip() or str(n["id"])
                embedding_vec = generate_text_embedding(text_to_embed)


                node_values.append([n["id"], n["label"], props_val, embedding_vec])

            if node_values:
                transaction.insert_or_update(
                    table="GraphNode",
                    columns=node_columns,
                    values=node_values,
                )

            # Upsert edges
            edge_columns = ["id", "dest_id", "edge_id", "label", "properties"]
            edge_values = []
            for e in edges:
                props_val = json.dumps(e["properties"]) if isinstance(e["properties"], dict) else e["properties"]
                edge_values.append([
                    e["id"],
                    e["dest_id"],
                    e["edge_id"],
                    e["label"],
                    props_val,
                ])

            if edge_values:
                transaction.insert_or_update(
                    table="GraphEdge",
                    columns=edge_columns,
                    values=edge_values,
                )

        db.run_in_transaction(_transaction_work)
        return {"nodes_count": len(deduped_nodes), "edges_count": len(deduped_edges)}

    def search_full_text(
        self,
        query: str,
        label: str | None = None,
        tags: list[str] | str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Full Text Search using Spanner SEARCH(body_tokens, query) index.
        Optionally filters by node label and tags.
        """
        db = self.get_database()
        where_clauses = ["SEARCH(body_tokens, @query)"]
        params: dict[str, Any] = {"query": query, "limit": limit}
        param_types: dict[str, Any] = {
            "query": spanner.param_types.STRING,
            "limit": spanner.param_types.INT64,
        }
        if label:
            where_clauses.append("label = @label")
            params["label"] = label
            param_types["label"] = spanner.param_types.STRING

        clean_tags = normalize_search_tags(tags)
        if clean_tags:
            tag_clause = """(
                EXISTS (
                    SELECT 1 FROM UNNEST(JSON_VALUE_ARRAY(properties, '$.tags')) AS t
                    JOIN UNNEST(@tags) AS search_tag
                    ON LOWER(t) = search_tag OR LOWER(t) LIKE CONCAT('%', search_tag)
                )
                OR EXISTS (
                    SELECT 1 FROM UNNEST(@tags) AS search_tag
                    WHERE LOWER(JSON_VALUE(properties, '$.tag')) = search_tag
                       OR LOWER(JSON_VALUE(properties, '$.tag')) LIKE CONCAT('%', search_tag)
                )
            )"""
            where_clauses.append(tag_clause)
            params["tags"] = clean_tags
            param_types["tags"] = spanner.param_types.Array(spanner.param_types.STRING)

        where_sql = " AND ".join(where_clauses)
        sql = f"""
        SELECT id, label, properties,
               JSON_VALUE_ARRAY(properties, '$.tags') AS tags
        FROM GraphNode
        WHERE {where_sql}
        LIMIT @limit
        """
        results = []
        with db.snapshot() as snapshot:
            rows = snapshot.execute_sql(sql, params=params, param_types=param_types)
            for row in rows:
                props = {}
                if len(row) > 2 and isinstance(row[2], dict):
                    props = row[2]
                elif len(row) > 2 and isinstance(row[2], str) and row[2].strip().startswith("{"):
                    try:
                        props = json.loads(row[2])
                    except Exception:
                        props = {}

                if props:
                    concept_id = props.get("id") or ""
                    name = props.get("name") or props.get("title") or ""
                    description = props.get("description") or ""
                    tags_list = props.get("tags") or ([props.get("tag")] if props.get("tag") else [])
                    contributor = props.get("contributor") or (props.get("frontmatter") or {}).get("contributor") or {}
                    sources = props.get("sources") or (props.get("frontmatter") or {}).get("sources") or []
                    fts_val = float(row[3]) if len(row) > 3 and isinstance(row[3], (int, float)) else None
                else:
                    concept_id = str(row[2]) if len(row) > 2 and row[2] else ""
                    name = str(row[3]) if len(row) > 3 and row[3] else ""
                    raw_tags = row[4] if len(row) > 4 else []
                    tags_list = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
                    description = ""
                    contributor = {}
                    sources = []
                    fts_val = float(row[5]) if len(row) > 5 and isinstance(row[5], (int, float)) else None

                results.append({
                    "id": row[0],
                    "label": row[1],
                    "concept_id": concept_id,
                    "name": name,
                    "description": description,
                    "contributor": contributor,
                    "sources": sources,
                    "tags": tags_list,
                    "fts_score": fts_val,
                })
        return results

    def search_vector(
        self,
        query_text: str,
        label: str | None = None,
        tags: list[str] | str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Vector Search using Spanner ScaNN Vector Index (GraphNodeVectorIndex) with Cosine Distance.
        Optionally filters by node label and tags.
        """
        db = self.get_database()
        query_vec = generate_text_embedding(query_text)
        where_clauses = ["embedding IS NOT NULL"]
        params: dict[str, Any] = {"query_vec": query_vec, "limit": limit}
        param_types: dict[str, Any] = {
            "query_vec": spanner.param_types.Array(spanner.param_types.FLOAT64),
            "limit": spanner.param_types.INT64,
        }
        if label:
            where_clauses.append("label = @label")
            params["label"] = label
            param_types["label"] = spanner.param_types.STRING

        clean_tags = normalize_search_tags(tags)
        if clean_tags:
            tag_clause = """(
                EXISTS (
                    SELECT 1 FROM UNNEST(JSON_VALUE_ARRAY(properties, '$.tags')) AS t
                    JOIN UNNEST(@tags) AS search_tag
                    ON LOWER(t) = search_tag OR LOWER(t) LIKE CONCAT('%', search_tag)
                )
                OR EXISTS (
                    SELECT 1 FROM UNNEST(@tags) AS search_tag
                    WHERE LOWER(JSON_VALUE(properties, '$.tag')) = search_tag
                       OR LOWER(JSON_VALUE(properties, '$.tag')) LIKE CONCAT('%', search_tag)
                )
            )"""
            where_clauses.append(tag_clause)
            params["tags"] = clean_tags
            param_types["tags"] = spanner.param_types.Array(spanner.param_types.STRING)

        where_sql = " AND ".join(where_clauses)
        sql = f"""
        SELECT id, label, properties,
               JSON_VALUE_ARRAY(properties, '$.tags') AS tags,
               COSINE_DISTANCE(embedding, @query_vec) AS distance
        FROM GraphNode
        WHERE {where_sql}
        ORDER BY distance ASC
        LIMIT @limit
        """
        results = []
        with db.snapshot() as snapshot:
            rows = snapshot.execute_sql(sql, params=params, param_types=param_types)
            for row in rows:
                props = {}
                if len(row) > 2 and isinstance(row[2], dict):
                    props = row[2]
                elif len(row) > 2 and isinstance(row[2], str) and row[2].strip().startswith("{"):
                    try:
                        props = json.loads(row[2])
                    except Exception:
                        props = {}

                if props:
                    concept_id = props.get("id") or ""
                    name = props.get("name") or props.get("title") or ""
                    description = props.get("description") or ""
                    tags_list = props.get("tags") or ([props.get("tag")] if props.get("tag") else [])
                    contributor = props.get("contributor") or (props.get("frontmatter") or {}).get("contributor") or {}
                    sources = props.get("sources") or (props.get("frontmatter") or {}).get("sources") or []
                    dist_val = float(row[4]) if len(row) > 4 and isinstance(row[4], (int, float)) else (
                        float(row[3]) if len(row) > 3 and isinstance(row[3], (int, float)) else 0.0
                    )
                else:
                    concept_id = str(row[2]) if len(row) > 2 and row[2] else ""
                    name = str(row[3]) if len(row) > 3 and row[3] else ""
                    raw_tags = row[4] if len(row) > 4 else []
                    tags_list = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
                    description = ""
                    contributor = {}
                    sources = []
                    dist_val = float(row[5]) if len(row) > 5 and isinstance(row[5], (int, float)) else (
                        float(row[4]) if len(row) > 4 and isinstance(row[4], (int, float)) else 0.0
                    )

                results.append({
                    "id": row[0],
                    "label": row[1],
                    "concept_id": concept_id,
                    "name": name,
                    "description": description,
                    "contributor": contributor,
                    "sources": sources,
                    "tags": tags_list,
                    "distance": dist_val,
                })
        return results

    def search_unified(
        self,
        search_string: str,
        label: str | None = None,
        tags: list[str] | str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Unified hybrid search combining Spanner Full Text Search and ScaNN Vector Search.
        Applies Reciprocal Rank Fusion (RRF) with semantic cosine similarity and
        cross-modal consensus boosting to return a single, re-ranked result list.
        """
        clean_tags = normalize_search_tags(tags)
        candidate_limit = max(limit * 3, 20)

        fulltext_results = self.search_full_text(
            query=search_string, label=label, tags=clean_tags, limit=candidate_limit
        )
        vector_results = self.search_vector(
            query_text=search_string, label=label, tags=clean_tags, limit=candidate_limit
        )

        reranked_results = rerank_hybrid_results(
            fulltext_results=fulltext_results,
            vector_results=vector_results,
            limit=limit,
        )

        return {
            "search_string": search_string,
            "label": label or "",
            "tags": clean_tags,
            "total_results": len(reranked_results),
            "rerank_algorithm": "reciprocal_rank_fusion_hybrid",
            "results": reranked_results,
        }


    def fetch_node_labels(self) -> dict[str, Any]:
        """
        Returns label count summary for GraphNode table.
        """
        db = self.get_database()
        query = "SELECT label, COUNT(*) FROM GraphNode GROUP BY label ORDER BY COUNT(*) DESC"
        labels = []
        total_nodes = 0
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(query)
            for row in results:
                lbl = row[0]
                cnt = row[1]
                labels.append({"label": lbl, "count": cnt})
                total_nodes += cnt
        return {"total_nodes": total_nodes, "labels": labels}

    def fetch_edge_labels(self) -> dict[str, Any]:
        """
        Returns label count summary for GraphEdge table.
        """
        db = self.get_database()
        query = "SELECT label, COUNT(*) FROM GraphEdge GROUP BY label ORDER BY COUNT(*) DESC"
        labels = []
        total_edges = 0
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(query)
            for row in results:
                lbl = row[0]
                cnt = row[1]
                labels.append({"label": lbl, "count": cnt})
                total_edges += cnt
        return {"total_edges": total_edges, "labels": labels}

    def fetch_nodes(self, limit: int = 100) -> list[dict[str, Any]]:
        db = self.get_database()
        query = f"SELECT id, label, properties FROM GraphNode LIMIT {limit}"
        nodes = []
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(query)
            for row in results:
                props = row[2]
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except Exception:
                        pass
                nodes.append({
                    "id": row[0],
                    "label": row[1],
                    "properties": props,
                })
        return nodes

    def fetch_edges(self, limit: int = 100) -> list[dict[str, Any]]:
        db = self.get_database()
        query = f"SELECT id, dest_id, edge_id, label, properties FROM GraphEdge LIMIT {limit}"
        edges = []
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(query)
            for row in results:
                props = row[4]
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except Exception:
                        pass
                edges.append({
                    "id": row[0],
                    "dest_id": row[1],
                    "edge_id": row[2],
                    "label": row[3],
                    "properties": props,
                })
        return edges
