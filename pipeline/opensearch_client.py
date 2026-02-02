#!/usr/bin/env python3
"""
OpenSearch client configuration and helpers.
"""

from opensearchpy import OpenSearch

# Default local development settings
OPENSEARCH_HOST = "localhost"
OPENSEARCH_PORT = 9200

# Index names
INCIDENTS_INDEX = "incidents"


def get_client() -> OpenSearch:
    """Create and return an OpenSearch client."""
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
    )


def check_connection(client: OpenSearch) -> bool:
    """Verify OpenSearch is reachable."""
    try:
        info = client.info()
        print(f"✓ Connected to OpenSearch {info['version']['number']}")
        return True
    except Exception as e:
        print(f"✗ Failed to connect to OpenSearch: {e}")
        return False
