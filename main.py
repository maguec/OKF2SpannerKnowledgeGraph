import json
import os
from typing import Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Body, Query
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from okf_service import parse_and_validate_okf_content, md5_to_uuid
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
    id: str | None = Field(None, description="Optional pre-generated UUID for the document (e.g. from file MD5)")
    content: str = Field(..., description="Raw OKF markdown document content")
    default_id: str | None = Field(None, description="Optional default concept ID if omitted in frontmatter")


class IngestResponse(BaseModel):
    success: bool
    nodes_inserted: int
    edges_inserted: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    findings: list[str]


class SearchRequest(BaseModel):
    search_string: str = Field(..., min_length=1, description="Search query string for both full text and vector search")
    label: str | None = Field(None, description="Optional node label filter (e.g. Architecture, Methodology, Concept, Tag, Source)")
    tag: str | None = Field(None, description="Optional single tag filter")
    tags: list[str] | str | None = Field(None, description="Optional tag or list of tags to filter by")
    limit: int = Field(10, description="Max results per search method", ge=1, le=100)

    def get_effective_tags(self) -> list[str]:
        result: list[str] = []
        if isinstance(self.tags, list):
            for t in self.tags:
                if t and str(t).strip():
                    result.append(str(t).strip())
        elif isinstance(self.tags, str) and self.tags.strip():
            for t in self.tags.split(","):
                if t.strip():
                    result.append(t.strip())
        if self.tag and self.tag.strip() and self.tag.strip() not in result:
            result.append(self.tag.strip())
        return result


class SearchNodeResult(BaseModel):
    id: str
    label: str
    concept_id: str = ""
    name: str = ""
    description: str = ""
    contributor: dict[str, Any] | str = Field(default_factory=dict)
    sources: list[Any] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    score: float = Field(..., description="Hybrid re-ranked relevance score (0.0 to 1.0)")
    rank: int = Field(..., description="Final 1-based re-ranked position")
    matched_by: list[str] = Field(default_factory=list, description="Search methods that matched ('vector', 'fulltext')")
    vector_distance: float | None = Field(None, description="Cosine distance from ScaNN vector search (lower is closer)")
    fts_score: float | None = Field(None, description="Full-text relevance score")


class SearchMethodResult(BaseModel):
    id: str
    label: str
    concept_id: str = ""
    name: str = ""
    description: str = ""
    contributor: dict[str, Any] | str = Field(default_factory=dict)
    sources: list[Any] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    distance: float | None = None
    fts_score: float | None = None


class SearchResponse(BaseModel):
    search_string: str
    label: str = ""
    tags: list[str] = Field(default_factory=list)
    total_results: int
    rerank_algorithm: str = "reciprocal_rank_fusion_hybrid"
    results: list[SearchNodeResult]


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
        },
        "search_endpoints": {
            "unified_search": "POST /search (JSON body: search_string, optional label, optional tags/tag, limit)",
            "fulltext_search": "GET /search/fulltext (Query params: q, optional label, optional tags/tag, limit)",
            "vector_search": "GET /search/vector (Query params: q, optional label, optional tags/tag, limit)",
        },
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
    node_id = payload.id or md5_to_uuid(payload.content)
    res = parse_and_validate_okf_content(payload.content, default_id=payload.default_id, node_id=node_id)
    return res


@app.post("/okf/ingest", response_model=IngestResponse)
def ingest_okf(payload: OKFDocumentPayload):
    """
    Parses a single OKF v2 document and populates Spanner GraphNode and GraphEdge with Gemini embeddings.
    Uses the provided UUID (from MD5 or caller) instead of creating one from concept ID.
    """
    node_id = payload.id or md5_to_uuid(payload.content)
    res = parse_and_validate_okf_content(payload.content, default_id=payload.default_id, node_id=node_id)
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
    Upload multiple OKF v2 JSON or markdown files, parse, validate, and populate Spanner Graph.
    Uses pre-generated file UUIDs on ingestion.
    """
    file_records = []
    failed_files = []
    concept_to_id_map: dict[str, str] = {}

    for file in files:
        content_bytes = await file.read()
        filename = file.filename or "doc"
        if filename.endswith(".json"):
            try:
                data = json.loads(content_bytes.decode("utf-8"))
                doc_content = data.get("content", "")
                doc_id = data.get("id") or md5_to_uuid(content_bytes)
                default_id = filename.removesuffix(".json")
            except Exception as e:
                failed_files.append({"filename": filename, "findings": [f"Invalid JSON: {str(e)}"]})
                continue
        else:
            doc_content = content_bytes.decode("utf-8", errors="replace")
            doc_id = md5_to_uuid(content_bytes)
            default_id = filename.removesuffix(".md")

        concept_to_id_map[default_id] = doc_id
        concept_to_id_map[default_id.replace("_", "/")] = doc_id

        file_records.append({
            "filename": filename,
            "content": doc_content,
            "default_id": default_id,
            "node_id": doc_id,
        })

    all_nodes = []
    all_edges = []
    all_findings = []

    for item in file_records:
        res = parse_and_validate_okf_content(
            content=item["content"],
            default_id=item["default_id"],
            node_id=item["node_id"],
            concept_to_id_map=concept_to_id_map,
        )
        if not res["valid"]:
            failed_files.append({"filename": item["filename"], "findings": res["findings"]})
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


@app.post("/search", response_model=SearchResponse)
def search_unified_endpoint(payload: SearchRequest):
    """
    Unified search endpoint that runs both Spanner Full-Text Search (SEARCH)
    and ScaNN Vector Search (COSINE_DISTANCE) across Gemini embeddings.
    Accepts JSON body with `search_string`, optional `label`, optional `tags` / `tag`, and optional `limit`.
    """
    try:
        effective_tags = payload.get_effective_tags()
        return spanner_service.search_unified(
            search_string=payload.search_string,
            label=payload.label,
            tags=effective_tags,
            limit=payload.limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/search/fulltext")
def search_full_text(
    q: str = Query(..., description="Search keyword query"),
    label: str | None = Query(None, description="Optional node label filter"),
    tag: str | None = Query(None, description="Optional single tag filter"),
    tags: list[str] | None = Query(None, description="Optional list of tags to filter by"),
    limit: int = 10,
):
    """
    Perform Full Text Search on property body using Spanner GraphNodeSearchIndex.
    """
    effective_tags: list[str] = []
    if tags:
        effective_tags.extend(tags)
    if tag and tag not in effective_tags:
        effective_tags.append(tag)

    try:
        results = spanner_service.search_full_text(query=q, label=label, tags=effective_tags, limit=limit)
        return {
            "query": q,
            "label": label or "",
            "tags": effective_tags,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Full Text Search failed: {str(e)}")


@app.get("/search/vector")
def search_vector(
    q: str = Query(..., description="Query text for vector similarity search"),
    label: str | None = Query(None, description="Optional node label filter"),
    tag: str | None = Query(None, description="Optional single tag filter"),
    tags: list[str] | None = Query(None, description="Optional list of tags to filter by"),
    limit: int = 10,
):
    """
    Perform Vector Similarity Search using Gemini text-embedding-004 and Spanner ScaNN GraphNodeVectorIndex.
    """
    effective_tags: list[str] = []
    if tags:
        effective_tags.extend(tags)
    if tag and tag not in effective_tags:
        effective_tags.append(tag)

    try:
        results = spanner_service.search_vector(query_text=q, label=label, tags=effective_tags, limit=limit)
        return {
            "query": q,
            "label": label or "",
            "tags": effective_tags,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector Search failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
