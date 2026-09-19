import re
import hashlib
import uuid
from typing import Any
import okf_core
from okf_core.documents import ConceptDocument
from okf_core.versions import is_supported_okf_version


def string_to_uuidv4(str_id: str) -> str:
    """
    Converts a string identifier to a deterministic valid UUIDv4 string (36 chars).
    """
    try:
        val = uuid.UUID(str_id)
        return str(val)
    except ValueError:
        pass

    h = hashlib.sha256(str_id.encode("utf-8")).digest()[:16]
    b = bytearray(h)
    b[6] = (b[6] & 0x0F) | 0x40  # Set Version 4
    b[8] = (b[8] & 0x3F) | 0x80  # Set Variant RFC 4122
    return str(uuid.UUID(bytes=bytes(b)))


def parse_and_validate_okf_content(
    content: str, default_id: str | None = None
) -> dict[str, Any]:
    """
    Parses OKF content, validates it, and extracts graph node and edge details with UUIDv4 primary keys.
    """
    try:
        doc: ConceptDocument = okf_core.parse_concept_document(content)
    except Exception as e:
        return {
            "valid": False,
            "error": f"Failed to parse OKF document: {str(e)}",
            "findings": [str(e)],
            "node": None,
            "edges": [],
        }

    findings = okf_core.validate_concept_document(doc)
    error_findings = [
        getattr(f, "message", str(f))
        for f in findings
        if getattr(f, "severity", "error") == "error"
    ]

    frontmatter = doc.frontmatter or {}

    # Check OKF version
    okf_ver = str(frontmatter.get("okf_version", frontmatter.get("version", "0.2")))
    if not (okf_ver == "0.2" or is_supported_okf_version(okf_ver) or okf_ver.startswith("2")):
        error_findings.append(
            f"Unsupported OKF version '{okf_ver}'. Expected OKF v2 / 0.2."
        )

    concept_id = str(frontmatter.get("id", default_id or "concept-unknown"))
    node_label = str(frontmatter.get("type", "Concept"))
    node_name = str(frontmatter.get("name", frontmatter.get("title", concept_id)))

    # Node UUIDv4 primary key
    uuidv4_node_id = string_to_uuidv4(concept_id)

    # Properties for Spanner GraphNode
    node_properties = {
        "id": concept_id,
        "name": node_name,
        "type": node_label,
        "frontmatter": frontmatter,
        "body": doc.body,
    }

    # Extract Markdown links using okf_core
    extracted_md_links = okf_core.extract_markdown_links(doc.body)

    # Extract Wiki-style links [[target]] or [[target|label]]
    wiki_link_pattern = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
    wiki_matches = wiki_link_pattern.findall(doc.body)

    edges = []
    edge_idx = 0

    # Process markdown links
    for md_link in extracted_md_links:
        target = md_link.target
        # Ignore external HTTP links
        if target.startswith("http://") or target.startswith("https://"):
            continue
        # Clean target path/extension if present
        target_id = target.removesuffix(".md").strip("/")
        dest_uuidv4_id = string_to_uuidv4(target_id)
        edge_idx += 1
        edge_uuidv4_id = string_to_uuidv4(f"{concept_id}->{target_id}:{edge_idx}")

        edges.append({
            "id": uuidv4_node_id,
            "dest_id": dest_uuidv4_id,
            "edge_id": edge_uuidv4_id,
            "label": "LINKS_TO",
            "properties": {
                "source_id": concept_id,
                "dest_id": target_id,
                "text": md_link.text or "",
                "type": "markdown_link",
            },
        })

    # Process wiki links
    for match in wiki_matches:
        target_id = match[0].strip().removesuffix(".md")
        link_label = match[1].strip() if match[1] else target_id
        dest_uuidv4_id = string_to_uuidv4(target_id)
        edge_idx += 1
        edge_uuidv4_id = string_to_uuidv4(f"{concept_id}->{target_id}:{edge_idx}")

        edges.append({
            "id": uuidv4_node_id,
            "dest_id": dest_uuidv4_id,
            "edge_id": edge_uuidv4_id,
            "label": "LINKS_TO",
            "properties": {
                "source_id": concept_id,
                "dest_id": target_id,
                "text": link_label,
                "type": "wiki_link",
            },
        })

    is_valid = len(error_findings) == 0

    return {
        "valid": is_valid,
        "findings": [getattr(f, "message", str(f)) for f in findings] + (
            [] if is_valid else error_findings
        ),
        "node": {
            "id": uuidv4_node_id,
            "label": node_label,
            "properties": node_properties,
        },
        "edges": edges,
    }
