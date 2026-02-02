# Phase 2A: Searchable Database with OpenSearch

This document covers building a searchable layer on top of our cleaned incident data.

---

## High-Level Plan

From the workshop objectives (PROBLEM.md lines 328-331):

1. **Why you might want a searchable layer** on top of your cleaned data
2. **Options**: OpenSearch/Elasticsearch, ClickHouse, DuckDB, Postgres with indexing
3. **Designing a search-friendly document model**
4. **Building a simple ETL pipeline**

---

## 1. Why a Searchable Layer?

SQLite (and most relational DBs) excel at:
- Structured queries with known fields
- Joins across normalized tables
- ACID transactions

But they struggle with:
- **Full-text search** on description fields
- **Faceted filtering** (show counts per category while filtering)
- **Fuzzy matching** (typos, partial matches)
- **Aggregations across dimensions** (without complex GROUP BY)

OpenSearch gives us:
- Full-text search with relevance scoring
- Instant faceted navigation
- Date histograms, range queries
- Horizontal scaling (when needed)

---

## 2. Implementation Plan

### 2.1 Prerequisites

```
Local machine:
├── Docker + Docker Compose (for OpenSearch)
├── Python 3.11+
└── uv (package manager)

Data pipeline:
└── Scenario 6 completed (all fields normalized in incidents_clean)
    - zone_code, severity, reported_time columns present
```

> **Important:** Complete [Scenario 6](problems/scenario6.md) first to ensure `incidents_clean`
> has all normalized columns. The OpenSearch ETL reads only clean fields—no `*_raw` data
> is indexed.

### 2.2 Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   SQLite DB     │      │   ETL Pipeline  │      │   OpenSearch    │
│                 │      │                 │      │                 │
│ incidents_clean │─────►│ 1. Extract      │─────►│ incidents index │
│ employees       │      │ 2. Denormalize  │      │                 │
│ machines        │      │ 3. Transform    │      │ Full-text search│
│ zones           │      │ 4. Index        │      │ Faceted filters │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

## 3. Setup

### 3.1 Add Dependencies

```bash
uv add opensearch-py
```

### 3.2 Docker Compose for OpenSearch

Create `docker-compose.yml` in project root:

```yaml
version: '3.8'

services:
  opensearch:
    image: opensearchproject/opensearch:2.11.0
    container_name: opensearch
    environment:
      - discovery.type=single-node
      - plugins.security.disabled=true  # Dev only
      - OPENSEARCH_INITIAL_ADMIN_PASSWORD=admin
      - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
      - "9600:9600"
    volumes:
      - opensearch-data:/usr/share/opensearch/data

  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:2.11.0
    container_name: opensearch-dashboards
    environment:
      - OPENSEARCH_HOSTS=["http://opensearch:9200"]
      - DISABLE_SECURITY_DASHBOARDS_PLUGIN=true
    ports:
      - "5601:5601"
    depends_on:
      - opensearch

volumes:
  opensearch-data:
```

### 3.3 Start Services

```bash
docker compose up -d

# Verify OpenSearch is running
curl -X GET "http://localhost:9200/_cluster/health?pretty"
```

---

## 4. Index Design (Denormalized Document)

### 4.1 Document Model

Each incident becomes a self-contained document with all related data embedded.

> **Note:** We index only **normalized/clean** fields—no `*_raw` fields are included.
> Raw values are preserved in SQLite (`incidents_clean`) for debugging/auditing,
> but the search layer contains only consistent, canonical data.

```json
{
  "incident_id": 42,
  
  "timestamp": {
    "incident_time": "2024-01-15T14:30:00",
    "reported_time": "2024-01-15T15:00:00",
    "indexed_at": "2024-01-20T10:00:00"
  },
  
  "incident": {
    "type": "machine_failure",
    "severity": "medium",
    "description": "Unexpected stop triggered by sensor."
  },
  
  "machine": {
    "code": "M-017",
    "type": "CNC Mill",
    "category": "CNC",
    "vendor": "Haas"
  },
  
  "employee": {
    "badge_id": "B0045",
    "first_name": "John",
    "last_name": "Smith",
    "full_name": "John Smith",
    "role": "Operator"
  },
  
  "location": {
    "zone_code": "Z-02",
    "zone_name": "Assembly East"
  },
  
  "shift": {
    "code": "S-20240115-D",
    "name": "Day"
  }
}
```

### 4.2 Index Mapping

```json
{
  "mappings": {
    "properties": {
      "incident_id": { "type": "integer" },
      
      "timestamp": {
        "properties": {
          "incident_time": { "type": "date" },
          "reported_time": { "type": "date" },
          "indexed_at": { "type": "date" }
        }
      },
      
      "incident": {
        "properties": {
          "type": { "type": "keyword" },
          "severity": { "type": "keyword" },
          "description": { 
            "type": "text",
            "analyzer": "standard",
            "fields": {
              "keyword": { "type": "keyword", "ignore_above": 256 }
            }
          }
        }
      },
      
      "machine": {
        "properties": {
          "code": { "type": "keyword" },
          "type": { "type": "keyword" },
          "category": { "type": "keyword" },
          "vendor": { "type": "keyword" }
        }
      },
      
      "employee": {
        "properties": {
          "badge_id": { "type": "keyword" },
          "first_name": { "type": "keyword" },
          "last_name": { "type": "keyword" },
          "full_name": { 
            "type": "text",
            "fields": {
              "keyword": { "type": "keyword" }
            }
          },
          "role": { "type": "keyword" }
        }
      },
      
      "location": {
        "properties": {
          "zone_code": { "type": "keyword" },
          "zone_name": { "type": "keyword" }
        }
      },
      
      "shift": {
        "properties": {
          "code": { "type": "keyword" },
          "name": { "type": "keyword" }
        }
      }
    }
  }
}
```

---

## 5. ETL Pipeline

### 5.1 File Structure

```
pipeline/
├── __init__.py
├── build_incidents_clean.py    # Existing - SQLite cleaning
├── normalize.py                # Existing - normalization functions
└── opensearch_indexer.py       # NEW - OpenSearch ETL
```

### 5.2 OpenSearch Client Module

Create `pipeline/opensearch_client.py`:

```python
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
```

### 5.3 Index Management Module

Create `pipeline/opensearch_index.py`:

```python
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
```

### 5.4 Data Extraction & Denormalization

Create `pipeline/opensearch_extract.py`:

> **Note:** This module reads from `incidents_clean` which already has all normalized
> fields (after completing Scenario 6). We extract only clean data—no `*_raw` fields
> are included in the OpenSearch documents.

```python
#!/usr/bin/env python3
"""
Extract data from SQLite and denormalize for OpenSearch indexing.

Reads from incidents_clean (which has all normalized fields) and
enriches with lookup data from dimension tables.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterator

DB_PATH = Path(__file__).parent.parent / "data" / "factory_training.db"


def load_lookup_tables(conn: sqlite3.Connection) -> dict:
    """Load all lookup tables for denormalization."""
    lookups = {}

    # Employees: badge_id -> employee details
    cursor = conn.execute(
        "SELECT badge_id, first_name, last_name, role FROM employees"
    )
    lookups["employees"] = {
        row[0]: {
            "badge_id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "full_name": f"{row[1]} {row[2]}",
            "role": row[3],
        }
        for row in cursor.fetchall()
    }

    # Machines: machine_code -> machine details
    cursor = conn.execute(
        """
        SELECT m.machine_code, mt.type_name, mt.category, m.vendor
        FROM machines m
        LEFT JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
        """
    )
    lookups["machines"] = {
        row[0]: {
            "code": row[0],
            "type": row[1],
            "category": row[2],
            "vendor": row[3],
        }
        for row in cursor.fetchall()
    }

    # Zones: zone_code -> zone details
    cursor = conn.execute("SELECT zone_code, zone_name FROM zones")
    lookups["zones"] = {
        row[0]: {"zone_code": row[0], "zone_name": row[1]}
        for row in cursor.fetchall()
    }

    # Shifts: shift_code -> shift details
    cursor = conn.execute("SELECT shift_code, shift_name FROM shifts_raw")
    lookups["shifts"] = {
        row[0]: {"code": row[0], "name": row[1]}
        for row in cursor.fetchall()
    }

    return lookups


def extract_incidents(conn: sqlite3.Connection) -> list[dict]:
    """Extract all incidents from incidents_clean (normalized fields only)."""
    cursor = conn.execute(
        """
        SELECT 
            incident_id,
            incident_type,
            severity,
            description,
            machine_code,
            badge_id,
            zone_code,
            shift_code,
            incident_time,
            reported_time
        FROM incidents_clean
        """
    )

    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def denormalize_incident(incident: dict, lookups: dict) -> dict:
    """
    Transform a single incident row into a denormalized document.
    
    This is the key transformation step - we embed related data
    directly into the document for efficient searching.
    
    Only clean/normalized fields are included (no *_raw fields).
    """
    now = datetime.utcnow().isoformat()

    # Get related entities (with safe defaults)
    machine_code = incident.get("machine_code")
    machine = lookups["machines"].get(machine_code, {}) if machine_code else {}

    badge_id = incident.get("badge_id")
    employee = lookups["employees"].get(badge_id, {}) if badge_id else {}

    zone_code = incident.get("zone_code")
    zone = lookups["zones"].get(zone_code, {}) if zone_code else {}

    shift_code = incident.get("shift_code")
    shift = lookups["shifts"].get(shift_code, {}) if shift_code else {}

    return {
        "incident_id": incident["incident_id"],
        "timestamp": {
            "incident_time": incident.get("incident_time"),
            "reported_time": incident.get("reported_time"),
            "indexed_at": now,
        },
        "incident": {
            "type": incident.get("incident_type"),
            "severity": incident.get("severity"),
            "description": incident.get("description"),
        },
        "machine": {
            "code": machine_code,
            "type": machine.get("type"),
            "category": machine.get("category"),
            "vendor": machine.get("vendor"),
        },
        "employee": {
            "badge_id": badge_id,
            "first_name": employee.get("first_name"),
            "last_name": employee.get("last_name"),
            "full_name": employee.get("full_name"),
            "role": employee.get("role"),
        },
        "location": {
            "zone_code": zone_code,
            "zone_name": zone.get("zone_name"),
        },
        "shift": {
            "code": shift_code,
            "name": shift.get("name"),
        },
    }


def generate_documents(db_path: Path = DB_PATH) -> Iterator[dict]:
    """
    Main extraction function - yields denormalized documents.
    
    Usage:
        for doc in generate_documents():
            # index doc to OpenSearch
    """
    conn = sqlite3.connect(db_path)
    try:
        print("Loading lookup tables for denormalization...")
        lookups = load_lookup_tables(conn)
        print(f"  {len(lookups['employees'])} employees")
        print(f"  {len(lookups['machines'])} machines")
        print(f"  {len(lookups['zones'])} zones")
        print(f"  {len(lookups['shifts'])} shifts")

        print("Extracting incidents...")
        incidents = extract_incidents(conn)
        print(f"  {len(incidents)} incidents to process")

        print("Denormalizing...")
        for incident in incidents:
            yield denormalize_incident(incident, lookups)

    finally:
        conn.close()
```

### 5.5 Main Indexer Script

Create `pipeline/opensearch_indexer.py`:

```python
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
    if not args.dry_run:
        verify_index(client)

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
```

---

## 6. Usage

### 6.1 Full Pipeline

```bash
# 1. Start OpenSearch
docker compose up -d

# 2. Wait for OpenSearch to be ready (~30 seconds)
curl -s "http://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=30s"

# 3. Ensure incidents_clean is up to date
uv run python pipeline/build_incidents_clean.py

# 4. Index to OpenSearch (full reindex)
uv run python pipeline/opensearch_indexer.py --recreate

# 5. Open Dashboards to explore
open http://localhost:5601
```

### 6.2 Example Queries

**Full-text search on descriptions:**
```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "incident.description": "sensor triggered"
    }
  }
}'
```

**Faceted filter by machine category:**
```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "term": { "machine.category": "CNC" }
  },
  "aggs": {
    "by_severity": {
      "terms": { "field": "incident.severity" }
    }
  }
}'
```

**Date range query:**
```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "range": {
      "timestamp.incident_time": {
        "gte": "2024-01-01",
        "lte": "2024-01-31"
      }
    }
  }
}'
```

---

## 7. Future Enhancements

### 7.1 Incremental Sync (Deferred)

Current approach: Full reindex on each run.

For incremental updates, we would need:
1. Add `updated_at` timestamp to `incidents_clean`
2. Track last sync time
3. Query only changed records: `WHERE updated_at > last_sync`
4. Use OpenSearch bulk update with `_id` for upserts

### 7.2 Additional Indices

Consider separate indices for:
- `maintenance_logs` - for maintenance history search
- `employees` - for employee lookup/search
- `machines` - for equipment search

### 7.3 Production Considerations

- Enable TLS and authentication
- Multiple shards/replicas for availability
- Index lifecycle management (ILM) for time-based data
- Monitoring with OpenSearch Dashboards

---

## 8. Checklist

**Prerequisites:**
- [ ] Complete Scenario 6 (normalization catch-up)
- [ ] Verify `incidents_clean` has: `zone_code`, `severity`, `reported_time` columns

**Setup:**
- [ ] Install opensearch-py: `uv add opensearch-py`
- [ ] Create docker-compose.yml
- [ ] Start OpenSearch: `docker compose up -d`

**Implementation:**
- [ ] Create pipeline/opensearch_client.py
- [ ] Create pipeline/opensearch_index.py
- [ ] Create pipeline/opensearch_extract.py
- [ ] Create pipeline/opensearch_indexer.py

**Verify:**
- [ ] Run: `uv run python pipeline/opensearch_indexer.py --recreate`
- [ ] Verify in OpenSearch Dashboards
