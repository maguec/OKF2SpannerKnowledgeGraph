import glob
import os
from okf_service import parse_and_validate_okf_content
from spanner_service import SpannerGraphService

def main():
    print("--- OKF v2 to Spanner Knowledge Graph Ingestion Demo ---")
    sample_files = glob.glob("data/sample_okf/*.md")
    print(f"Found {len(sample_files)} sample files: {sample_files}")

    all_nodes = []
    all_edges = []

    for file_path in sample_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        res = parse_and_validate_okf_content(content, default_id=os.path.basename(file_path).removesuffix(".md"))
        print(f"\nProcessing {file_path}:")
        print(f"  Valid: {res['valid']}")
        print(f"  Node ID: {res['node']['id']} ({res['node']['properties']['id']})")
        print(f"  Total Nodes generated (concept + tags + sources): {len(res.get('nodes', []))}")
        print(f"  Edges extracted: {len(res['edges'])}")
        for e in res['edges']:
            print(f"    - {e['properties'].get('source_id')} --[{e['label']}]--> {e['properties'].get('dest_id')}")
        
        if res["valid"]:
            all_nodes.extend(res.get("nodes", [res["node"]]))
            all_edges.extend(res["edges"])

    print(f"\nTotal Nodes to write: {len(all_nodes)}")
    print(f"Total Edges to write: {len(all_edges)}")

    spanner_service = SpannerGraphService()
    if os.getenv("GOOGLE_SPANNER_INSTANCE") and os.getenv("GOOGLE_SPANNER_DATABASE"):
        print("\nAttempting to populate Cloud Spanner Graph...")
        try:
            result = spanner_service.upsert_graph(all_nodes, all_edges)
            print(f"SUCCESS: Inserted/Updated {result['nodes_count']} nodes and {result['edges_count']} edges into Spanner!")
        except Exception as e:
            print(f"Spanner ingest error: {e}")
    else:
        print("\nSpanner environment variables not set; skipping live Spanner database write.")

if __name__ == "__main__":
    main()
