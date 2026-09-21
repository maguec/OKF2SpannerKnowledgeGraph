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
    Parses OKF content, validates it, and extracts graph node and edge details.
    Includes Tag nodes (HAS_TAGS), Source nodes (HAS_REFERENCE), and Markdown links (HAS_LINKS).
    """
    try:
        doc: ConceptDocument = okf_core.parse_concept_document(content)
    except Exception as e:
        return {
            "valid": False,
            "error": f"Failed to parse OKF document: {str(e)}",
            "findings": [str(e)],
            "node": None,
            "nodes": [],
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

    concept_id = str(
        frontmatter.get("concept_id", frontmatter.get("id", default_id or "concept-unknown"))
    )
    node_label = str(frontmatter.get("label", frontmatter.get("type", "Concept")))
    node_name = str(frontmatter.get("title", frontmatter.get("name", concept_id)))
    description = str(frontmatter.get("description", ""))

    # Primary concept node UUIDv4
    uuidv4_node_id = string_to_uuidv4(concept_id)

    # Properties for Spanner GraphNode
    node_properties = {
        "id": concept_id,
        "name": node_name,
        "type": node_label,
        "description": description,
        "frontmatter": frontmatter,
        "body": doc.body,
    }

    concept_node = {
        "id": uuidv4_node_id,
        "label": node_label,
        "properties": node_properties,
    }

    all_nodes = [concept_node]
    edges = []

    # Process Tags (HAS_TAGS relationship)
    raw_tags = frontmatter.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]

    for tag_val in raw_tags:
        if not tag_val or not isinstance(tag_val, str):
            continue
        tag_name = tag_val.strip()
        tag_concept_id = f"tag:{tag_name}"
        tag_uuid = string_to_uuidv4(tag_concept_id)

        all_nodes.append({
            "id": tag_uuid,
            "label": "Tag",
            "properties": {
                "id": tag_concept_id,
                "name": tag_name,
                "type": "Tag",
                "tag": tag_name,
            },
        })

        edges.append({
            "id": uuidv4_node_id,
            "dest_id": tag_uuid,
            "edge_id": string_to_uuidv4(f"{concept_id}->tag:{tag_name}"),
            "label": "HAS_TAGS",
            "properties": {
                "source_id": concept_id,
                "dest_id": tag_concept_id,
                "tag": tag_name,
            },
        })

    # Process Sources (HAS_REFERENCE relationship)
    raw_sources = frontmatter.get("sources", [])
    if isinstance(raw_sources, list):
        for idx, src_obj in enumerate(raw_sources):
            if not isinstance(src_obj, dict):
                continue
            src_raw_id = str(src_obj.get("id") or src_obj.get("title") or f"src-{idx+1}")
            src_concept_id = f"source:{src_raw_id}"
            src_uuid = string_to_uuidv4(src_concept_id)
            src_title = str(src_obj.get("title") or src_raw_id)
            src_author = str(src_obj.get("author") or "")
            src_url = str(src_obj.get("drive_url") or "")

            all_nodes.append({
                "id": src_uuid,
                "label": "Source",
                "properties": {
                    "id": src_concept_id,
                    "name": src_title,
                    "type": "Source",
                    "author": src_author,
                    "drive_url": src_url,
                },
            })

            edges.append({
                "id": uuidv4_node_id,
                "dest_id": src_uuid,
                "edge_id": string_to_uuidv4(f"{concept_id}->source:{src_raw_id}"),
                "label": "HAS_REFERENCE",
                "properties": {
                    "source_id": concept_id,
                    "dest_id": src_concept_id,
                    "title": src_title,
                    "author": src_author,
                    "drive_url": src_url,
                },
            })

    # Extract Markdown links using okf_core
    extracted_md_links = okf_core.extract_markdown_links(doc.body)

    # Extract Wiki-style links [[target]] or [[target|label]]
    wiki_link_pattern = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
    wiki_matches = wiki_link_pattern.findall(doc.body)

    edge_idx = 0

    # Process markdown links (HAS_LINKS relationship)
    for md_link in extracted_md_links:
        target = md_link.target
        # Ignore external HTTP links for concept edges
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
            "label": "HAS_LINKS",
            "properties": {
                "source_id": concept_id,
                "dest_id": target_id,
                "text": md_link.text or "",
                "type": "markdown_link",
            },
        })

    # Process wiki links (HAS_LINKS relationship)
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
            "label": "HAS_LINKS",
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
        "node": concept_node,
        "nodes": all_nodes,
        "edges": edges,
    }
