import json
import os
from typing import Any
from google.cloud import spanner
from embedding_service import generate_text_embedding


# Disable Spanner built-in metrics exporter by default to avoid missing label errors in Cloud Monitoring
os.environ.setdefault("SPANNER_DISABLE_BUILTIN_METRICS", "true")


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

    def search_full_text(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Full Text Search using Spanner SEARCH(body_tokens, query) index.
        """
        db = self.get_database()
        sql = """
        SELECT id, label, JSON_VALUE(properties, '$.id') AS concept_id, JSON_VALUE(properties, '$.name') AS name
        FROM GraphNode
        WHERE SEARCH(body_tokens, @query)
        LIMIT @limit
        """
        params = {"query": query, "limit": limit}
        param_types = {
            "query": spanner.param_types.STRING,
            "limit": spanner.param_types.INT64,
        }
        results = []
        with db.snapshot() as snapshot:
            rows = snapshot.execute_sql(sql, params=params, param_types=param_types)
            for row in rows:
                results.append({
                    "id": row[0],
                    "label": row[1],
                    "concept_id": row[2],
                    "name": row[3],
                })
        return results

    def search_vector(self, query_text: str, limit: int = 10) -> list[dict[str, Any]]:
        """
        Vector Search using Spanner ScaNN Vector Index (GraphNodeVectorIndex) with Cosine Distance.
        """
        db = self.get_database()
        query_vec = generate_text_embedding(query_text)
        sql = """
        SELECT id, label, JSON_VALUE(properties, '$.id') AS concept_id, JSON_VALUE(properties, '$.name') AS name,
               COSINE_DISTANCE(embedding, @query_vec) AS distance
        FROM GraphNode
        WHERE embedding IS NOT NULL
        ORDER BY distance ASC
        LIMIT @limit
        """
        params = {"query_vec": query_vec, "limit": limit}
        param_types = {
            "query_vec": spanner.param_types.Array(spanner.param_types.FLOAT64),
            "limit": spanner.param_types.INT64,
        }
        results = []
        with db.snapshot() as snapshot:
            rows = snapshot.execute_sql(sql, params=params, param_types=param_types)
            for row in rows:
                results.append({
                    "id": row[0],
                    "label": row[1],
                    "concept_id": row[2],
                    "name": row[3],
                    "distance": row[4],
                })
        return results

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
