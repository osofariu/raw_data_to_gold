#!/usr/bin/env python3
"""
Main ETL script: SQLite -> OpenSearch

Performs a full reindex of all incidents from incidents_clean
into the OpenSearch incidents index.

Usage:
    uv run python pipeline/opensearch_indexer.py

Options:
    --dry-run    Extract and transform without indexing
    --recreate   Delete and recreate index before indexing
"""

import argparse
import json
import sys
from pathlib import Path

from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.opensearch_client import (
    get_client,
    check_connection,
    INCIDENTS_INDEX,
)
from pipeline.opensearch_index import create_index, recreate_index
from pipeline.opensearch_extract import generate_documents


def index_documents(
    client: OpenSearch,
    index_name: str = INCIDENTS_INDEX,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Index all documents from the generator.
    
    Returns:
        Tuple of (success_count, error_count)
    """
    success_count = 0
    error_count = 0

    # Prepare documents for bulk indexing
    def generate_actions():
        for doc in generate_documents():
            yield {
                "_index": index_name,
                "_id": doc["incident_id"],  # Use incident_id as document ID
                "_source": doc,
            }

    if dry_run:
        print("\n[DRY RUN] Would index these documents:\n")
        for i, doc in enumerate(generate_documents()):
            if i < 3:  # Show first 3
                print(f"  Document {doc['incident_id']}:")
                print(f"    machine: {doc['machine']['code']}")
                print(f"    employee: {doc['employee']['full_name']}")
                print(f"    type: {doc['incident']['type']}")
                print(f"    severity: {doc['incident']['severity']}")
            success_count += 1
        print(f"\n  ... and {success_count - 3} more documents")
        return success_count, 0

    # Bulk index
    print("\nIndexing documents...")
    success, errors = bulk(
        client,
        generate_actions(),
        stats_only=False,
        raise_on_error=False,
    )

    success_count = success
    error_count = len(errors) if errors else 0

    if errors:
        print(f"  ⚠ {error_count} indexing errors:")
        for err in errors[:5]:  # Show first 5 errors
            print(f"    {err}")

    return success_count, error_count


def verify_index(client: OpenSearch, index_name: str = INCIDENTS_INDEX) -> None:
    """Print index statistics after indexing."""
    # Refresh to make documents searchable
    client.indices.refresh(index=index_name)

    # Get count
    count = client.count(index=index_name)["count"]
    print(f"\n✓ Index '{index_name}' contains {count} documents")

    # Sample query: count by incident type
    agg_result = client.search(
        index=index_name,
        body={
            "size": 0,
            "aggs": {
                "by_type": {
                    "terms": {"field": "incident.type", "size": 10}
                }
            },
        },
    )

    print("\n  Incidents by type:")
    for bucket in agg_result["aggregations"]["by_type"]["buckets"]:
        print(f"    {bucket['key']}: {bucket['doc_count']}")

    # Count by severity
    agg_result = client.search(
        index=index_name,
        body={
            "size": 0,
            "aggs": {
                "by_severity": {
                    "terms": {"field": "incident.severity", "size": 10}
                }
            },
        },
    )

    print("\n  Incidents by severity:")
    for bucket in agg_result["aggregations"]["by_severity"]["buckets"]:
        print(f"    {bucket['key']}: {bucket['doc_count']}")


def main():
    parser = argparse.ArgumentParser(description="Index incidents to OpenSearch")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and transform without indexing",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate index before indexing",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("OpenSearch Indexer: incidents_clean -> OpenSearch")
    print("=" * 60)

    if args.dry_run:
        # Dry run doesn't need OpenSearch connection
        print("\n[DRY RUN MODE - No OpenSearch connection needed]")
        success, errors = index_documents(None, dry_run=True)
        print(f"\n✓ Would index {success} documents")
        print("\n" + "=" * 60)
        print("Done! (dry run)")
        return

    # Connect
    client = get_client()
    if not check_connection(client):
        sys.exit(1)

    # Prepare index
    if args.recreate:
        print("\nRecreating index...")
        recreate_index(client)
    else:
        create_index(client)

    # Index documents
    success, errors = index_documents(client, dry_run=args.dry_run)

    print(f"\n✓ Indexed {success} documents")
    if errors:
        print(f"✗ {errors} errors")

    # Verify
    verify_index(client)

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
