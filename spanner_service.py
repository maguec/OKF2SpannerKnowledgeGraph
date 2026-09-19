import json
import os
from typing import Any
from google.cloud import spanner


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
        """
        db = self.get_database()

        def _transaction_work(transaction):
            # Upsert nodes first (since edges interleave in GraphNode)
            node_columns = ["id", "label", "properties"]
            node_values = []
            for n in nodes:
                props_val = json.dumps(n["properties"]) if isinstance(n["properties"], dict) else n["properties"]
                node_values.append([n["id"], n["label"], props_val])

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
