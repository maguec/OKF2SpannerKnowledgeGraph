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
