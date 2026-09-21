import argparse
import glob
import json
import os
import sys
from okf_service import parse_and_validate_okf_content, md5_to_uuid
from spanner_service import SpannerGraphService
import okf_core


def generate_json_files_from_md(data_dir: str = "data/sample_okf") -> list[str]:
    """
    Reads all .md files in data_dir, computes the MD5 checksum of each file,
    formats it as a UUID, and writes corresponding .json files:
    { "id": "<uuid>", "content": "<raw OKF markdown>" }
    """
    md_files = sorted(glob.glob(os.path.join(data_dir, "*.md")))
    created_files = []
    for file_path in md_files:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        file_uuid = md5_to_uuid(raw_bytes)
        json_path = file_path.removesuffix(".md") + ".json"
        payload = {
            "id": file_uuid,
            "content": raw_bytes.decode("utf-8"),
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        created_files.append(json_path)
    return created_files


def main():
    parser = argparse.ArgumentParser(description="OKF v2 to Spanner Knowledge Graph Ingestion")
    parser.add_argument("--instance-id", default=os.getenv("GOOGLE_SPANNER_INSTANCE"), help="Spanner instance ID")
    parser.add_argument("--database-id", default=os.getenv("GOOGLE_SPANNER_DATABASE"), help="Spanner database ID")
    parser.add_argument("--project-id", default=os.getenv("GOOGLE_PROJECT"), help="Google Cloud project ID")
    parser.add_argument("--dry-run", action="store_true", help="Validate data and show stats without writing to Spanner")
    parser.add_argument("--generate-json", action="store_true", help="Generate JSON sample files from Markdown")
    args, _ = parser.parse_known_args()

    print("--- OKF v2 to Spanner Knowledge Graph Ingestion ---")
    if args.generate_json:
        print("Generating JSON sample files from Markdown...")
        created = generate_json_files_from_md()
        print(f"Generated {len(created)} JSON sample files.")
        return

    # Prefer JSON sample files with pre-calculated MD5 UUIDs; fallback to MD files
    json_files = sorted(glob.glob("data/sample_okf/*.json"))
    md_files = sorted(glob.glob("data/sample_okf/*.md"))

    if json_files:
        sample_files = json_files
        is_json = True
        print(f"Found {len(sample_files)} JSON sample files (using file MD5 UUIDs).")
    else:
        sample_files = md_files
        is_json = False
        print(f"Found {len(sample_files)} Markdown sample files.")

    # Phase 1: Pre-scan files to map concept IDs and filenames to their MD5-derived UUIDs
    concept_to_id_map: dict[str, str] = {}
    file_records = []

    for file_path in sample_files:
        if is_json:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_id = data.get("id") or md5_to_uuid(data.get("content", ""))
            content = data.get("content", "")
            default_id = os.path.basename(file_path).removesuffix(".json")
        else:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            file_id = md5_to_uuid(raw_bytes)
            content = raw_bytes.decode("utf-8")
            default_id = os.path.basename(file_path).removesuffix(".md")

        # Extract concept_id from frontmatter if possible
        try:
            doc = okf_core.parse_concept_document(content)
            fm = doc.frontmatter or {}
            c_id = str(fm.get("concept_id", fm.get("id", default_id)))
        except Exception:
            c_id = default_id

        concept_to_id_map[c_id] = file_id
        concept_to_id_map[default_id] = file_id
        concept_to_id_map[default_id.replace("_", "/")] = file_id
        concept_to_id_map[c_id.replace("/", "_")] = file_id

        file_records.append({
            "path": file_path,
            "id": file_id,
            "content": content,
            "default_id": default_id,
        })

    # Phase 2: Ingest all documents using pre-generated MD5 UUIDs instead of creating our own
    all_nodes = []
    all_edges = []

    for item in file_records:
        file_path = item["path"]
        file_id = item["id"]
        content = item["content"]
        default_id = item["default_id"]

        res = parse_and_validate_okf_content(
            content=content,
            default_id=default_id,
            node_id=file_id,
            concept_to_id_map=concept_to_id_map,
        )

        print(f"\nProcessing {file_path}:")
        print(f"  Valid: {res['valid']}")
        print(f"  Node ID (MD5 UUID): {res['node']['id']} ({res['node']['properties']['id']})")
        print(f"  Total Nodes generated (concept + tags + sources): {len(res.get('nodes', []))}")
        print(f"  Edges extracted: {len(res['edges'])}")
        for e in res['edges']:
            print(f"    - {e['properties'].get('source_id')} --[{e['label']}]--> {e['properties'].get('dest_id')}")

        if res["valid"]:
            all_nodes.extend(res.get("nodes", [res["node"]]))
            all_edges.extend(res["edges"])

    print(f"\nTotal Nodes to write: {len(all_nodes)}")
    print(f"Total Edges to write: {len(all_edges)}")

    if args.dry_run:
        print("\n✅ DRY-RUN COMPLETE: Validated all nodes and edges. Skipped writing to Cloud Spanner.")
        return

    instance_id = args.instance_id
    database_id = args.database_id
    project_id = args.project_id

    if instance_id and database_id:
        print(f"\nAttempting to populate Cloud Spanner Graph (instance={instance_id}, database={database_id})...")
        spanner_service = SpannerGraphService(
            project_id=project_id,
            instance_id=instance_id,
            database_id=database_id,
        )
        try:
            result = spanner_service.upsert_graph(all_nodes, all_edges)
            print(f"SUCCESS: Inserted/Updated {result['nodes_count']} nodes and {result['edges_count']} edges into Spanner!")
        except Exception as e:
            print(f"Spanner ingest error: {e}")
    else:
        print("\nSpanner environment variables/flags not set; skipping live Spanner database write.")


if __name__ == "__main__":
    main()
