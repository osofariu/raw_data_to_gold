#!/usr/bin/env python3
"""
OpenSearch index management - create, delete, configure indices.
"""

from opensearchpy import OpenSearch

from pipeline.opensearch_client import INCIDENTS_INDEX


# Index mapping for incidents (clean fields only, no *_raw)
INCIDENTS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,  # Single node dev setup
    },
    "mappings": {
        "properties": {
            "incident_id": {"type": "integer"},
            "timestamp": {
                "properties": {
                    "incident_time": {"type": "date"},
                    "reported_time": {"type": "date"},
                    "indexed_at": {"type": "date"},
                }
            },
            "incident": {
                "properties": {
                    "type": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "description": {
                        "type": "text",
                        "analyzer": "standard",
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                    },
                }
            },
            "machine": {
                "properties": {
                    "code": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "vendor": {"type": "keyword"},
                }
            },
            "employee": {
                "properties": {
                    "badge_id": {"type": "keyword"},
                    "first_name": {"type": "keyword"},
                    "last_name": {"type": "keyword"},
                    "full_name": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "role": {"type": "keyword"},
                }
            },
            "location": {
                "properties": {
                    "zone_code": {"type": "keyword"},
                    "zone_name": {"type": "keyword"},
                }
            },
            "shift": {
                "properties": {
                    "code": {"type": "keyword"},
                    "name": {"type": "keyword"},
                }
            },
        }
    },
}


def create_index(client: OpenSearch, index_name: str = INCIDENTS_INDEX) -> bool:
    """Create the incidents index with mapping."""
    if client.indices.exists(index=index_name):
        print(f"  Index '{index_name}' already exists")
        return True

    response = client.indices.create(index=index_name, body=INCIDENTS_MAPPING)
    if response.get("acknowledged"):
        print(f"✓ Created index '{index_name}'")
        return True
    return False


def delete_index(client: OpenSearch, index_name: str = INCIDENTS_INDEX) -> bool:
    """Delete an index (for full reindex)."""
    if not client.indices.exists(index=index_name):
        print(f"  Index '{index_name}' does not exist")
        return True

    response = client.indices.delete(index=index_name)
    if response.get("acknowledged"):
        print(f"✓ Deleted index '{index_name}'")
        return True
    return False


def recreate_index(client: OpenSearch, index_name: str = INCIDENTS_INDEX) -> bool:
    """Delete and recreate index (full reindex pattern)."""
    delete_index(client, index_name)
    return create_index(client, index_name)
