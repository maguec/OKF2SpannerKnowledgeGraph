import os
from typing import Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body, Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from okf_service import parse_and_validate_okf_content
from spanner_service import SpannerGraphService

# Load environment variables from .env if present
load_dotenv()

app = FastAPI(
    title="OKF v2 to Spanner Knowledge Graph API",
    description="FastAPI service for parsing valid OKF v2 files, populating Spanner Graph with HAS_TAGS, HAS_REFERENCE, and HAS_LINKS relationships, Full Text Search, and ScaNN Vector Search.",
    version="0.3.0",
)

spanner_service = SpannerGraphService()


class OKFDocumentPayload(BaseModel):
    content: str = Field(..., description="Raw OKF markdown document content")
    default_id: str | None = Field(None, description="Optional default concept ID if omitted in frontmatter")


class IngestResponse(BaseModel):
    success: bool
    nodes_inserted: int
    edges_inserted: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    findings: list[str]


@app.get("/")
def read_root():
    return {
        "service": "OKF v2 to Spanner Knowledge Graph API",
        "status": "running",
        "spanner_config": {
            "project_id": os.getenv("GOOGLE_PROJECT"),
            "instance_id": os.getenv("GOOGLE_SPANNER_INSTANCE"),
            "database_id": os.getenv("GOOGLE_SPANNER_DATABASE"),
            "region": os.getenv("GOOGLE_CLOUD_REGION"),
        },
        "indexes": {
            "fts_index": "GraphNodeSearchIndex",
            "vector_index": "GraphNodeVectorIndex (ScaNN)",
            "embedding_model": "text-embedding-004 (768-dim, vectorizes title + description + body)",
        },
        "graph_relationships": {
            "tags": "HAS_TAGS -> Tag",
            "references": "HAS_REFERENCE -> Source",
            "links": "HAS_LINKS -> Concept/Node",
        }
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "env_configured": bool(
            os.getenv("GOOGLE_PROJECT")
            and os.getenv("GOOGLE_SPANNER_INSTANCE")
            and os.getenv("GOOGLE_SPANNER_DATABASE")
        ),
    }


@app.post("/okf/validate")
def validate_okf(payload: OKFDocumentPayload):
    """
    Validate OKF v2 document syntax, schema, and links.
    """
    res = parse_and_validate_okf_content(payload.content, default_id=payload.default_id)
    return res


@app.post("/okf/ingest", response_model=IngestResponse)
def ingest_okf(payload: OKFDocumentPayload):
    """
    Parses a single OKF v2 document and populates Spanner GraphNode and GraphEdge with Gemini embeddings.
    """
    res = parse_and_validate_okf_content(payload.content, default_id=payload.default_id)
    if not res["valid"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid OKF v2 document",
                "findings": res["findings"],
                "error": res.get("error"),
            },
        )

    nodes = res.get("nodes", [res["node"]] if res["node"] else [])
    edges = res["edges"]

    try:
        spanner_res = spanner_service.upsert_graph(nodes=nodes, edges=edges)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to populate Spanner Graph: {str(e)}"
        )

    return IngestResponse(
        success=True,
        nodes_inserted=spanner_res["nodes_count"],
        edges_inserted=spanner_res["edges_count"],
        nodes=nodes,
        edges=edges,
        findings=res["findings"],
    )


@app.post("/okf/ingest-files", response_model=IngestResponse)
async def ingest_okf_files(files: list[UploadFile] = File(...)):
    """
    Upload multiple OKF v2 markdown files, parse, validate, and populate Spanner Graph.
    """
    all_nodes = []
    all_edges = []
    all_findings = []
    failed_files = []

    for file in files:
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8", errors="replace")
        default_id = file.filename.removesuffix(".md") if file.filename else None

        res = parse_and_validate_okf_content(content, default_id=default_id)
        if not res["valid"]:
            failed_files.append({"filename": file.filename, "findings": res["findings"]})
        else:
            if res.get("nodes"):
                all_nodes.extend(res["nodes"])
            elif res["node"]:
                all_nodes.append(res["node"])
            all_edges.extend(res["edges"])
            all_findings.extend(res["findings"])

    if failed_files:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "One or more uploaded OKF files were invalid",
                "failed_files": failed_files,
            },
        )

    try:
        spanner_res = spanner_service.upsert_graph(nodes=all_nodes, edges=all_edges)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to populate Spanner Graph: {str(e)}"
        )

    return IngestResponse(
        success=True,
        nodes_inserted=spanner_res["nodes_count"],
        edges_inserted=spanner_res["edges_count"],
        nodes=all_nodes,
        edges=all_edges,
        findings=all_findings,
    )


@app.get("/nodes")
@app.get("/graph/nodes")
def get_node_labels():
    """
    Fetch node labels with counts from Spanner GraphNode table.
    """
    try:
        return spanner_service.fetch_node_labels()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch node labels: {str(e)}")


@app.get("/edges")
@app.get("/graph/edges")
def get_edge_labels():
    """
    Fetch edge labels with counts from Spanner GraphEdge table.
    """
    try:
        return spanner_service.fetch_edge_labels()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch edge labels: {str(e)}")


@app.get("/search/fulltext")
def search_full_text(q: str = Query(..., description="Search keyword query"), limit: int = 10):
    """
    Perform Full Text Search on property body using Spanner GraphNodeSearchIndex.
    """
    try:
        results = spanner_service.search_full_text(query=q, limit=limit)
        return {"query": q, "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Full Text Search failed: {str(e)}")


@app.get("/search/vector")
def search_vector(q: str = Query(..., description="Query text for vector similarity search"), limit: int = 10):
    """
    Perform Vector Similarity Search using Gemini text-embedding-004 and Spanner ScaNN GraphNodeVectorIndex.
    """
    try:
        results = spanner_service.search_vector(query_text=q, limit=limit)
        return {"query": q, "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector Search failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
