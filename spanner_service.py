import json
import os
from typing import Any
from google.cloud import spanner
from embedding_service import generate_text_embedding


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
            self._client = spanner.Client(project=self.project_id)
            instance = self._client.instance(self.instance_id)
            self._database = instance.database(self.database_id)
        return self._database

    def upsert_graph(
        self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
    ) -> dict[str, int]:
        """
        Upserts nodes and edges into GraphNode and GraphEdge tables in Spanner.
        Generates and writes 768-dimensional Gemini vector embeddings for each node.
        """
        db = self.get_database()

        def _transaction_work(transaction):
            # Upsert nodes first (since edges interleave in GraphNode)
            node_columns = ["id", "label", "properties", "embedding"]
            node_values = []
            for n in nodes:
                props_dict = n["properties"] if isinstance(n["properties"], dict) else {}
                props_val = json.dumps(props_dict) if isinstance(n["properties"], dict) else n["properties"]
                
                # Extract text for Gemini embedding generation
                body_text = props_dict.get("body", "") or props_dict.get("name", "") or str(n["id"])
                embedding_vec = generate_text_embedding(body_text)

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
        return {"nodes_count": len(nodes), "edges_count": len(edges)}

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
