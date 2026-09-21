import hashlib
import json
import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from okf_service import parse_and_validate_okf_content, string_to_uuidv4, md5_to_uuid

client = TestClient(app)

SAMPLE_VALID_OKF_1 = """---
id: concept-ai
type: Concept
name: Artificial Intelligence
okf_version: '0.2'
---
# Artificial Intelligence
AI is a field of computer science.
It connects to [[concept-ml|Machine Learning]] and [Deep Learning](concept-dl).
"""

SAMPLE_VALID_OKF_2 = """---
id: concept-ml
type: Concept
name: Machine Learning
okf_version: '0.2'
---
# Machine Learning
ML is a subfield of AI.
"""

SAMPLE_INVALID_OKF = """---
name: Missing ID and Type
okf_version: '0.2'
---
# Invalid Concept
"""


def test_string_to_uuidv4():
    id1 = string_to_uuidv4("concept-ai")
    id2 = string_to_uuidv4("concept-ai")
    id3 = string_to_uuidv4("concept-ml")

    assert isinstance(id1, str)
    assert len(id1) == 36
    val = uuid.UUID(id1)
    assert val.version == 4
    assert id1 == id2  # Deterministic match
    assert id1 != id3


def test_md5_to_uuid():
    sample = "test content for md5"
    u = md5_to_uuid(sample)
    assert len(u) == 36
    parsed = uuid.UUID(u)
    assert parsed.hex == hashlib.md5(sample.encode("utf-8")).hexdigest()
    # Deterministic
    assert md5_to_uuid(sample) == u


def test_parse_and_validate_okf_content_with_custom_uuid():
    custom_uuid = "1aecf31e-3a61-280c-0ae0-e5d38ebc51dd"
    res = parse_and_validate_okf_content(SAMPLE_VALID_OKF_1, node_id=custom_uuid)
    assert res["valid"] is True
    assert res["node"]["id"] == custom_uuid
    assert res["node"]["properties"]["id"] == "concept-ai"
    # Source edge should also carry this source uuid
    for e in res["edges"]:
        assert e["id"] == custom_uuid


def test_parse_and_validate_okf_content_valid():
    res = parse_and_validate_okf_content(SAMPLE_VALID_OKF_1)
    assert res["valid"] is True
    assert res["node"]["properties"]["id"] == "concept-ai"
    assert res["node"]["properties"]["name"] == "Artificial Intelligence"
    assert uuid.UUID(res["node"]["id"]).version == 4
    assert len(res["edges"]) == 2


def test_parse_and_validate_okf_content_invalid():
    res = parse_and_validate_okf_content(SAMPLE_INVALID_OKF)
    assert res["valid"] is False
    assert len(res["findings"]) > 0


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "running"
    assert "spanner_config" in json_data


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_validate_endpoint():
    response = client.post("/okf/validate", json={"content": SAMPLE_VALID_OKF_1})
    assert response.status_code == 200
    assert response.json()["valid"] is True


@patch("main.spanner_service.upsert_graph")
def test_ingest_endpoint(mock_upsert):
    mock_upsert.return_value = {"nodes_count": 1, "edges_count": 2}

    response = client.post("/okf/ingest", json={"content": SAMPLE_VALID_OKF_1})
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["nodes_inserted"] == 1
    assert json_data["edges_inserted"] == 2


@patch("main.spanner_service.upsert_graph")
def test_ingest_files_endpoint(mock_upsert):
    mock_upsert.return_value = {"nodes_count": 2, "edges_count": 2}

    files = [
        ("files", ("ai.md", SAMPLE_VALID_OKF_1, "text/markdown")),
        ("files", ("ml.md", SAMPLE_VALID_OKF_2, "text/markdown")),
    ]
    response = client.post("/okf/ingest-files", files=files)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["nodes_inserted"] == 2


@patch("main.spanner_service.upsert_graph")
def test_ingest_endpoint_with_custom_uuid(mock_upsert):
    mock_upsert.return_value = {"nodes_count": 1, "edges_count": 2}
    custom_uuid = "1aecf31e-3a61-280c-0ae0-e5d38ebc51dd"

    response = client.post(
        "/okf/ingest",
        json={"id": custom_uuid, "content": SAMPLE_VALID_OKF_1},
    )
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["nodes"][0]["id"] == custom_uuid


@patch("main.spanner_service.upsert_graph")
def test_ingest_files_endpoint_with_json(mock_upsert):
    mock_upsert.return_value = {"nodes_count": 1, "edges_count": 2}
    custom_uuid = "2c8d486a-e964-864d-aaae-2cfe564ba3c3"
    json_doc = json.dumps({"id": custom_uuid, "content": SAMPLE_VALID_OKF_1})

    files = [
        ("files", ("concept_ai.json", json_doc, "application/json")),
    ]
    response = client.post("/okf/ingest-files", files=files)
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["nodes"][0]["id"] == custom_uuid


@patch("main.spanner_service.fetch_node_labels")
def test_get_node_labels(mock_fetch):
    mock_fetch.return_value = {
        "total_nodes": 22,
        "labels": [
            {"label": "Concept", "count": 12},
            {"label": "Architecture", "count": 6},
            {"label": "Specification", "count": 4},
        ],
    }
    response = client.get("/nodes")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["total_nodes"] == 22
    assert len(json_data["labels"]) == 3

    response_alias = client.get("/graph/nodes")
    assert response_alias.status_code == 200
    assert response_alias.json()["total_nodes"] == 22


@patch("main.spanner_service.fetch_edge_labels")
def test_get_edge_labels(mock_fetch):
    mock_fetch.return_value = {
        "total_edges": 45,
        "labels": [{"label": "LINKS_TO", "count": 45}],
    }
    response = client.get("/edges")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["total_edges"] == 45
    assert json_data["labels"][0]["label"] == "LINKS_TO"

    response_alias = client.get("/graph/edges")
    assert response_alias.status_code == 200
    assert response_alias.json()["total_edges"] == 45


@patch("main.spanner_service.search_unified")
def test_post_search_unified_success(mock_search):
    mock_search.return_value = {
        "search_string": "spanner database",
        "label": "",
        "tags": [],
        "total_results": 1,
        "rerank_algorithm": "reciprocal_rank_fusion_hybrid",
        "results": [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "label": "Concept",
                "concept_id": "concept-spanner",
                "name": "Cloud Spanner",
                "description": "Cloud Spanner is a fully managed relational database.",
                "contributor": {"name": "Architecture Team", "email": "arch@example.com"},
                "sources": ["https://cloud.google.com/spanner"],
                "tags": ["spanner"],
                "score": 0.95,
                "rank": 1,
                "matched_by": ["vector", "fulltext"],
                "vector_distance": 0.05,
                "fts_score": 1.5,
            }
        ],
    }

    response = client.post("/search", json={"search_string": "spanner database"})
    assert response.status_code == 200
    data = response.json()
    assert data["search_string"] == "spanner database"
    assert data["total_results"] == 1
    assert data["rerank_algorithm"] == "reciprocal_rank_fusion_hybrid"
    assert "fulltext_results" not in data
    assert "vector_results" not in data
    first_res = data["results"][0]
    assert first_res["matched_by"] == ["vector", "fulltext"]
    assert first_res["score"] == 0.95
    assert first_res["rank"] == 1
    assert first_res["description"] == "Cloud Spanner is a fully managed relational database."
    assert first_res["contributor"] == {"name": "Architecture Team", "email": "arch@example.com"}
    assert first_res["sources"] == ["https://cloud.google.com/spanner"]
    mock_search.assert_called_once_with(
        search_string="spanner database", label=None, tags=[], limit=10
    )


@patch("main.spanner_service.search_unified")
def test_post_search_unified_with_label_and_limit(mock_search):
    mock_search.return_value = {
        "search_string": "memorystore",
        "label": "Methodology",
        "tags": [],
        "total_results": 1,
        "rerank_algorithm": "reciprocal_rank_fusion_hybrid",
        "results": [
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "label": "Methodology",
                "concept_id": "methodologies/how_to_use_memorystore",
                "name": "How to Use Memorystore",
                "description": "How to configure and use Memorystore.",
                "contributor": {"name": "DevOps"},
                "sources": [],
                "tags": ["caching"],
                "score": 0.88,
                "rank": 1,
                "matched_by": ["vector"],
                "vector_distance": 0.12,
                "fts_score": None,
            }
        ],
    }

    response = client.post(
        "/search",
        json={"search_string": "memorystore", "label": "Methodology", "limit": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["label"] == "Methodology"
    assert data["total_results"] == 1
    assert data["results"][0]["description"] == "How to configure and use Memorystore."
    assert data["results"][0]["contributor"] == {"name": "DevOps"}
    assert data["results"][0]["sources"] == []
    mock_search.assert_called_once_with(
        search_string="memorystore", label="Methodology", tags=[], limit=5
    )


@patch("main.spanner_service.search_unified")
def test_post_search_unified_with_tags(mock_search):
    mock_search.return_value = {
        "search_string": "alloydb",
        "label": "Architecture",
        "tags": ["caching", "alloydb"],
        "total_results": 1,
        "rerank_algorithm": "reciprocal_rank_fusion_hybrid",
        "results": [
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "label": "Architecture",
                "concept_id": "architectures/alloydb_caching_layer",
                "name": "AlloyDB Caching",
                "description": "AlloyDB caching pattern architecture.",
                "contributor": "Cloud Architect",
                "sources": ["https://cloud.google.com/alloydb"],
                "tags": ["caching", "alloydb"],
                "score": 0.94,
                "rank": 1,
                "matched_by": ["vector", "fulltext"],
                "vector_distance": 0.04,
                "fts_score": 1.8,
            }
        ],
    }

    response = client.post(
        "/search",
        json={
            "search_string": "alloydb",
            "label": "Architecture",
            "tags": ["caching", "alloydb"],
            "limit": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["caching", "alloydb"]
    assert data["total_results"] == 1
    assert data["results"][0]["description"] == "AlloyDB caching pattern architecture."
    assert data["results"][0]["contributor"] == "Cloud Architect"
    assert data["results"][0]["sources"] == ["https://cloud.google.com/alloydb"]
    mock_search.assert_called_once_with(
        search_string="alloydb", label="Architecture", tags=["caching", "alloydb"], limit=10
    )


def test_post_search_validation_error():
    # Missing search_string
    response = client.post("/search", json={})
    assert response.status_code == 422

    # Invalid limit (0 or negative)
    response = client.post("/search", json={"search_string": "test", "limit": 0})
    assert response.status_code == 422


@patch("main.spanner_service.search_full_text")
def test_get_search_fulltext(mock_fts):
    mock_fts.return_value = [
        {"id": "111", "label": "Architecture", "concept_id": "c1", "name": "Arch 1", "tags": ["arch"]}
    ]
    response = client.get("/search/fulltext?q=architecture&label=Architecture&tag=arch&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "architecture"
    assert data["label"] == "Architecture"
    assert data["tags"] == ["arch"]
    assert data["count"] == 1
    mock_fts.assert_called_once_with(query="architecture", label="Architecture", tags=["arch"], limit=5)


@patch("main.spanner_service.search_vector")
def test_get_search_vector(mock_vec):
    mock_vec.return_value = [
        {"id": "222", "label": "Concept", "concept_id": "c2", "name": "Concept 2", "tags": ["ml"], "distance": 0.08}
    ]
    response = client.get("/search/vector?q=similarity&label=Concept&tag=ml&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "similarity"
    assert data["label"] == "Concept"
    assert data["tags"] == ["ml"]
    assert data["count"] == 1
    mock_vec.assert_called_once_with(query_text="similarity", label="Concept", tags=["ml"], limit=3)


def test_spanner_service_search_unified_merging():
    from spanner_service import SpannerGraphService
    svc = SpannerGraphService()

    # Mock search_full_text and search_vector directly on the instance
    svc.search_full_text = MagicMock(return_value=[
        {
            "id": "node-A", "label": "Concept", "concept_id": "c-a", "name": "Concept A",
            "description": "Desc A", "contributor": {"name": "Author A"}, "sources": ["https://a.com"],
            "tags": ["t1"], "fts_score": 1.0,
        },
        {
            "id": "node-B", "label": "Concept", "concept_id": "c-b", "name": "Concept B",
            "description": "Desc B", "contributor": {"name": "Author B"}, "sources": ["https://b.com"],
            "tags": ["t2"], "fts_score": 1.5,
        },
    ])
    svc.search_vector = MagicMock(return_value=[
        {
            "id": "node-B", "label": "Concept", "concept_id": "c-b", "name": "Concept B",
            "description": "Desc B", "contributor": {"name": "Author B"}, "sources": ["https://b.com"],
            "tags": ["t2"], "distance": 0.08,
        },
        {
            "id": "node-C", "label": "Concept", "concept_id": "c-c", "name": "Concept C",
            "description": "Desc C", "contributor": {}, "sources": [],
            "tags": ["t3"], "distance": 0.05,
        },
    ])

    res = svc.search_unified(search_string="test query", label="Concept", tags=["t2"], limit=10)

    assert res["search_string"] == "test query"
    assert res["label"] == "Concept"
    assert res["tags"] == ["t2"]
    assert res["total_results"] == 3
    assert res["rerank_algorithm"] == "reciprocal_rank_fusion_hybrid"

    # node-B is matched in both (high vector similarity and top FTS score), so it ranks #1 with consensus boost
    results = res["results"]
    assert results[0]["id"] == "node-B"
    assert "fulltext" in results[0]["matched_by"]
    assert "vector" in results[0]["matched_by"]
    assert results[0]["rank"] == 1
    assert results[0]["score"] > 0.8
    assert results[0]["vector_distance"] == 0.08
    assert results[0]["tags"] == ["t2"]
    assert results[0]["description"] == "Desc B"
    assert results[0]["contributor"] == {"name": "Author B"}
    assert results[0]["sources"] == ["https://b.com"]

    # All items have rank 1, 2, 3
    ranks = [r["rank"] for r in results]
    assert ranks == [1, 2, 3]

    # Scores must be in descending order
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_rerank_hybrid_results_algorithm():
    from spanner_service import rerank_hybrid_results

    ft_candidates = [
        {
            "id": "doc-1", "label": "Architecture", "concept_id": "a1", "name": "Doc 1",
            "description": "Doc 1 description", "contributor": {"author": "Arch"}, "sources": ["s1"],
            "tags": ["t1"], "fts_score": 3.0,
        },
        {
            "id": "doc-2", "label": "Methodology", "concept_id": "m1", "name": "Doc 2",
            "description": "Doc 2 description", "contributor": {"author": "Meth"}, "sources": ["s2"],
            "tags": ["t2"], "fts_score": 1.5,
        },
    ]
    vec_candidates = [
        {
            "id": "doc-2", "label": "Methodology", "concept_id": "m1", "name": "Doc 2",
            "description": "Doc 2 description", "contributor": {"author": "Meth"}, "sources": ["s2"],
            "tags": ["t2"], "distance": 0.05,
        },
        {
            "id": "doc-3", "label": "Concept", "concept_id": "c1", "name": "Doc 3",
            "description": "", "contributor": {}, "sources": [],
            "tags": ["t3"], "distance": 0.10,
        },
    ]

    reranked = rerank_hybrid_results(ft_candidates, vec_candidates, limit=3, k=60)
    assert len(reranked) == 3

    # doc-2 matched BOTH modalities (rank 1 in vec, rank 2 in FTS)
    assert reranked[0]["id"] == "doc-2"
    assert reranked[0]["rank"] == 1
    assert reranked[0]["matched_by"] == ["vector", "fulltext"]
    assert 0.0 <= reranked[0]["score"] <= 1.0
    assert reranked[0]["description"] == "Doc 2 description"
    assert reranked[0]["contributor"] == {"author": "Meth"}
    assert reranked[0]["sources"] == ["s2"]

    # doc-1 and doc-3
    assert reranked[1]["rank"] == 2
    assert reranked[2]["rank"] == 3
    assert reranked[0]["score"] >= reranked[1]["score"] >= reranked[2]["score"]

    doc_map = {r["id"]: r for r in reranked}
    assert doc_map["doc-1"]["description"] == "Doc 1 description"
    assert doc_map["doc-1"]["contributor"] == {"author": "Arch"}
    assert doc_map["doc-1"]["sources"] == ["s1"]
    assert doc_map["doc-3"]["description"] == ""
    assert doc_map["doc-3"]["contributor"] == {}
    assert doc_map["doc-3"]["sources"] == []


def test_spanner_service_search_sql_generation():
    from spanner_service import SpannerGraphService
    svc = SpannerGraphService()

    mock_db = MagicMock()
    mock_snapshot = MagicMock()
    mock_db.snapshot.return_value.__enter__.return_value = mock_snapshot
    mock_snapshot.execute_sql.return_value = [
        ("id-1", "Concept", "c-1", "Concept One", ["caching"])
    ]
    svc.get_database = MagicMock(return_value=mock_db)

    # 1. Full text without label or tags
    svc.search_full_text(query="test", limit=5)
    call_args = mock_snapshot.execute_sql.call_args
    sql = call_args[0][0]
    params = call_args[1]["params"]
    assert "SEARCH(body_tokens, @query)" in sql
    assert "label = @label" not in sql
    assert "JSON_VALUE_ARRAY(properties, '$.tags')" in sql
    assert params["query"] == "test"
    assert params["limit"] == 5

    # 2. Full text with label and tags
    mock_snapshot.reset_mock()
    svc.search_full_text(query="test", label="Architecture", tags=["caching", "alloydb"], limit=10)
    call_args = mock_snapshot.execute_sql.call_args
    sql = call_args[0][0]
    params = call_args[1]["params"]
    assert "SEARCH(body_tokens, @query)" in sql
    assert "label = @label" in sql
    assert "@tags" in sql
    assert params["query"] == "test"
    assert params["label"] == "Architecture"
    assert params["tags"] == ["caching", "alloydb"]

    # 3. Vector search without label or tags
    mock_snapshot.reset_mock()
    mock_snapshot.execute_sql.return_value = [
        ("id-1", "Concept", "c-1", "Concept One", ["database"], 0.05)
    ]
    svc.search_vector(query_text="vector query", limit=5)
    call_args = mock_snapshot.execute_sql.call_args
    sql = call_args[0][0]
    params = call_args[1]["params"]
    assert "COSINE_DISTANCE(embedding, @query_vec)" in sql
    assert "label = @label" not in sql
    assert "@tags" not in sql
    assert "query_vec" in params
    assert params["limit"] == 5

    # 4. Vector search with label and tags
    mock_snapshot.reset_mock()
    svc.search_vector(query_text="vector query", label="Methodology", tags="memorystore", limit=10)
    call_args = mock_snapshot.execute_sql.call_args
    sql = call_args[0][0]
    params = call_args[1]["params"]
    assert "COSINE_DISTANCE(embedding, @query_vec)" in sql
    assert "label = @label" in sql
    assert "@tags" in sql
    assert params["label"] == "Methodology"
    assert params["tags"] == ["memorystore"]



