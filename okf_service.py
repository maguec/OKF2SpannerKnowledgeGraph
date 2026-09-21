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


def md5_to_uuid(content: str | bytes) -> str:
    """
    Takes file content (str or bytes), computes its MD5 checksum,
    and formats it as a standard 36-character UUID string.
    """
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content
    md5_digest = hashlib.md5(content_bytes).digest()
    return str(uuid.UUID(bytes=md5_digest))


def sanitize_properties(data: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively sanitizes a dictionary of properties to ensure no null / None values exist.
    None values become empty strings "" or empty lists/dicts.
    Strings matching 'null' or 'none' (case-insensitive) for tags or identifiers are filtered.
    """
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for k, v in data.items():
        if v is None:
            cleaned[k] = ""
        elif isinstance(v, dict):
            cleaned[k] = sanitize_properties(v)
        elif isinstance(v, list):
            cleaned_list = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, str) and item.strip().lower() in ("null", "none", "~", "undefined"):
                    continue
                if isinstance(item, dict):
                    cleaned_list.append(sanitize_properties(item))
                else:
                    cleaned_list.append(item)
            cleaned[k] = cleaned_list
        elif isinstance(v, str):
            cleaned[k] = v.strip()
        else:
            cleaned[k] = v
    return cleaned


def parse_and_validate_okf_content(
    content: str,
    default_id: str | None = None,
    node_id: str | None = None,
    concept_to_id_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Parses OKF content, validates it, and extracts graph node and edge details.
    Includes Tag nodes (HAS_TAGS), Source nodes (HAS_REFERENCE), and Markdown links (HAS_LINKS).
    Ensures all node and edge properties are populated without null values.
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
    description = str(frontmatter.get("description") or "")
    status = str(frontmatter.get("status") or "stable")

    # Primary concept node UUID (use provided node_id if passed, otherwise derive from concept_id)
    if node_id:
        uuidv4_node_id = string_to_uuidv4(node_id)
    else:
        uuidv4_node_id = string_to_uuidv4(concept_id)

    # Process and sanitize Tags (HAS_TAGS relationship)
    raw_tags = frontmatter.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]

    valid_tags: list[str] = []
    for tag_val in raw_tags:
        if not tag_val or not isinstance(tag_val, str):
            continue
        cleaned_tag = tag_val.strip()
        if not cleaned_tag or cleaned_tag.lower() in ("null", "none", "~", "undefined"):
            continue
        valid_tags.append(cleaned_tag)

    primary_tag = valid_tags[0] if valid_tags else node_label.lower()

    # Process Sources info for default author/drive_url
    raw_sources = frontmatter.get("sources") or []
    default_author = ""
    default_url = ""
    if isinstance(raw_sources, list) and raw_sources:
        first_src = raw_sources[0]
        if isinstance(first_src, dict):
            default_author = str(first_src.get("author") or "")
            default_url = str(first_src.get("drive_url") or "")

    # Properties for Spanner GraphNode - guaranteed non-null
    node_properties = sanitize_properties({
        "id": concept_id,
        "name": node_name,
        "title": node_name,
        "type": node_label,
        "tag": primary_tag,
        "tags": valid_tags,
        "description": description or node_name,
        "body": doc.body or "",
        "author": default_author,
        "drive_url": default_url,
        "contributor": frontmatter.get("contributor") or {},
        "sources": raw_sources or [],
        "status": status,
        "frontmatter": frontmatter,
    })

    concept_node = {
        "id": uuidv4_node_id,
        "label": node_label,
        "properties": node_properties,
    }

    all_nodes = [concept_node]
    edges = []

    for tag_name in valid_tags:
        tag_concept_id = f"tag:{tag_name}"
        tag_uuid = string_to_uuidv4(tag_concept_id)

        all_nodes.append({
            "id": tag_uuid,
            "label": "Tag",
            "properties": sanitize_properties({
                "id": tag_concept_id,
                "name": tag_name,
                "title": tag_name,
                "type": "Tag",
                "tag": tag_name,
                "tags": [tag_name],
                "description": f"Tag: {tag_name}",
                "body": f"Tag: {tag_name}",
                "author": "",
                "drive_url": "",
                "status": "active",
                "frontmatter": {"id": tag_concept_id, "name": tag_name, "tag": tag_name, "type": "Tag"},
            }),
        })

        edges.append({
            "id": uuidv4_node_id,
            "dest_id": tag_uuid,
            "edge_id": string_to_uuidv4(f"{concept_id}->tag:{tag_name}"),
            "label": "HAS_TAGS",
            "properties": sanitize_properties({
                "source_id": concept_id,
                "dest_id": tag_concept_id,
                "tag": tag_name,
                "title": tag_name,
                "name": tag_name,
                "text": tag_name,
                "type": "HAS_TAGS",
                "author": "",
                "drive_url": "",
            }),
        })

    # Process Sources (HAS_REFERENCE relationship)
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
                "properties": sanitize_properties({
                    "id": src_concept_id,
                    "name": src_title,
                    "title": src_title,
                    "type": "Source",
                    "tag": "source",
                    "tags": ["source"],
                    "description": f"Source document: {src_title}",
                    "body": f"Source document: {src_title} by {src_author}",
                    "author": src_author,
                    "drive_url": src_url,
                    "status": "reference",
                    "frontmatter": {"id": src_concept_id, "title": src_title, "author": src_author, "drive_url": src_url, "type": "Source"},
                }),
            })

            edges.append({
                "id": uuidv4_node_id,
                "dest_id": src_uuid,
                "edge_id": string_to_uuidv4(f"{concept_id}->source:{src_raw_id}"),
                "label": "HAS_REFERENCE",
                "properties": sanitize_properties({
                    "source_id": concept_id,
                    "dest_id": src_concept_id,
                    "tag": "source",
                    "name": src_title,
                    "title": src_title,
                    "text": src_title,
                    "type": "HAS_REFERENCE",
                    "author": src_author,
                    "drive_url": src_url,
                }),
            })

    # Extract Markdown links using okf_core
    extracted_md_links = okf_core.extract_markdown_links(doc.body)

    # Extract Wiki-style links [[target]] or [[target|label]]
    wiki_link_pattern = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
    wiki_matches = wiki_link_pattern.findall(doc.body)

    edge_idx = 0

    def _resolve_dest_id(tgt_id: str) -> str:
        if concept_to_id_map:
            if tgt_id in concept_to_id_map:
                return concept_to_id_map[tgt_id]
            norm_tgt = tgt_id.replace("/", "_")
            if norm_tgt in concept_to_id_map:
                return concept_to_id_map[norm_tgt]
        return string_to_uuidv4(tgt_id)

    # Process markdown links (HAS_LINKS relationship)
    for md_link in extracted_md_links:
        target = md_link.target
        # Ignore external HTTP links for concept edges
        if target.startswith("http://") or target.startswith("https://"):
            continue
        # Clean target path/extension if present
        target_id = target.removesuffix(".md").strip("/")
        dest_uuidv4_id = _resolve_dest_id(target_id)
        edge_idx += 1
        edge_uuidv4_id = string_to_uuidv4(f"{concept_id}->{target_id}:{edge_idx}")

        edges.append({
            "id": uuidv4_node_id,
            "dest_id": dest_uuidv4_id,
            "edge_id": edge_uuidv4_id,
            "label": "HAS_LINKS",
            "properties": sanitize_properties({
                "source_id": concept_id,
                "dest_id": target_id,
                "tag": "link",
                "title": md_link.text or target_id,
                "name": md_link.text or target_id,
                "text": md_link.text or target_id,
                "type": "markdown_link",
                "author": "",
                "drive_url": "",
            }),
        })

    # Process wiki links (HAS_LINKS relationship)
    for match in wiki_matches:
        target_id = match[0].strip().removesuffix(".md")
        link_label = match[1].strip() if match[1] else target_id
        dest_uuidv4_id = _resolve_dest_id(target_id)
        edge_idx += 1
        edge_uuidv4_id = string_to_uuidv4(f"{concept_id}->{target_id}:{edge_idx}")

        edges.append({
            "id": uuidv4_node_id,
            "dest_id": dest_uuidv4_id,
            "edge_id": edge_uuidv4_id,
            "label": "HAS_LINKS",
            "properties": sanitize_properties({
                "source_id": concept_id,
                "dest_id": target_id,
                "tag": "link",
                "title": link_label,
                "name": link_label,
                "text": link_label,
                "type": "wiki_link",
                "author": "",
                "drive_url": "",
            }),
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
