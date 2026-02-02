# Scenario 7: Querying OpenSearch — Things SQL Can't Do Well

## Goal

Learn to query the OpenSearch incidents index with practical examples that highlight capabilities difficult or impossible in traditional SQL.

---

## Prerequisites

OpenSearch must be running with indexed data:

```bash
# Start OpenSearch (if not running)
docker compose up -d

# Verify index exists
curl -s "localhost:9200/incidents/_count" | jq .count
# Should return: 478
```

---

## Why OpenSearch Over SQL?

| Capability | SQL | OpenSearch |
|------------|-----|------------|
| Full-text search with ranking | `LIKE '%word%'` (no ranking) | Relevance-scored results |
| Fuzzy matching (typos) | Manual, painful | Built-in, automatic |
| Search + aggregate in one query | Requires subqueries/CTEs | Single query |
| Faceted counts while filtering | Complex, slow | Native support |
| Highlight matching text | Not supported | Built-in |
| Date histograms | Complex GROUP BY | One-liner |
| Multi-field search | Multiple OR conditions | Single query |

---

## 1. Full-Text Search with Relevance Scoring

### The SQL Problem

```sql
-- SQL: Find incidents mentioning "sensor"
-- No ranking, no relevance, just substring match
SELECT * FROM incidents_clean 
WHERE description LIKE '%sensor%';
```

This returns results in arbitrary order. Which result is *most relevant*? SQL doesn't know.

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "incident.description": "sensor triggered alarm"
    }
  }
}'
```

**What you get:**
- Results ranked by relevance score (`_score`)
- Documents matching more words rank higher
- "sensor triggered alarm" beats "sensor" alone

### Try It: Compare Scores

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "incident.description": "unexpected stop machine"
    }
  },
  "_source": ["incident_id", "incident.description"],
  "size": 5
}'
```

Notice how `_score` varies — higher scores mean better matches.

---

## 2. Fuzzy Matching (Handling Typos)

### The SQL Problem

```sql
-- User searches for "safty" (typo for "safety")
-- SQL finds nothing
SELECT * FROM incidents_clean 
WHERE description LIKE '%safty%';
-- 0 results
```

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "incident.description": {
        "query": "safty violation",
        "fuzziness": "AUTO"
      }
    }
  },
  "_source": ["incident_id", "incident.description", "incident.type"],
  "size": 5
}'
```

**What you get:**
- Finds "safety" even though user typed "safty"
- `fuzziness: AUTO` allows 1-2 character edits based on word length

### Try It: Typo Tolerance

```bash
# Search with typo "machne" instead of "machine"
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "incident.description": {
        "query": "machne failure",
        "fuzziness": "AUTO"
      }
    }
  },
  "size": 3
}'
```

---

## 3. Search + Aggregate in One Query (Faceted Search)

### The SQL Problem

```sql
-- SQL: Search for "failure" AND get counts by severity
-- Requires two queries or a complex CTE

-- Query 1: Get the results
SELECT * FROM incidents_clean 
WHERE description LIKE '%failure%';

-- Query 2: Get the counts
SELECT severity, COUNT(*) 
FROM incidents_clean 
WHERE description LIKE '%failure%'
GROUP BY severity;
```

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "incident.description": "failure"
    }
  },
  "size": 5,
  "aggs": {
    "by_severity": {
      "terms": { "field": "incident.severity" }
    },
    "by_zone": {
      "terms": { "field": "location.zone_name" }
    }
  }
}'
```

**What you get (in ONE query):**
- Top 5 matching documents
- Count of matches per severity level
- Count of matches per zone

This is the foundation of **faceted navigation** — like filtering on Amazon while seeing "Electronics (234), Books (89)".

### Try It: Multi-Facet Dashboard Query

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "by_type": {
      "terms": { "field": "incident.type", "size": 10 }
    },
    "by_severity": {
      "terms": { "field": "incident.severity" }
    },
    "by_machine_category": {
      "terms": { "field": "machine.category" }
    },
    "by_zone": {
      "terms": { "field": "location.zone_name" }
    }
  }
}'
```

`size: 0` means "don't return documents, just aggregations" — perfect for dashboards.

---

## 4. Date Histograms (Incidents Over Time)

### The SQL Problem

```sql
-- SQL: Count incidents per month
-- Requires date formatting and grouping
SELECT 
    strftime('%Y-%m', incident_time) as month,
    COUNT(*) as count
FROM incidents_clean
WHERE incident_time IS NOT NULL
GROUP BY strftime('%Y-%m', incident_time)
ORDER BY month;
```

Works, but what about "per week"? "Per day"? Each requires different format strings.

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "incidents_over_time": {
      "date_histogram": {
        "field": "timestamp.incident_time",
        "calendar_interval": "month"
      }
    }
  }
}'
```

**Change interval instantly:**
- `"calendar_interval": "week"` — weekly buckets
- `"calendar_interval": "day"` — daily buckets
- `"fixed_interval": "6h"` — every 6 hours

### Try It: Weekly Trend with Severity Breakdown

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "weekly_trend": {
      "date_histogram": {
        "field": "timestamp.incident_time",
        "calendar_interval": "week"
      },
      "aggs": {
        "by_severity": {
          "terms": { "field": "incident.severity" }
        }
      }
    }
  }
}'
```

This gives you incidents per week, broken down by severity — a nested aggregation that would be painful in SQL.

---

## 5. Multi-Field Search

### The SQL Problem

```sql
-- SQL: Search for "Smith" in employee name OR description
SELECT * FROM incidents_clean ic
JOIN employees e ON ic.badge_id = e.badge_id
WHERE e.first_name LIKE '%Smith%'
   OR e.last_name LIKE '%Smith%'
   OR ic.description LIKE '%Smith%';
```

Gets ugly fast. What if you want to search 5 fields?

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "multi_match": {
      "query": "sensor assembly",
      "fields": [
        "incident.description^2",
        "location.zone_name",
        "machine.type"
      ]
    }
  },
  "_source": ["incident_id", "incident.description", "location.zone_name", "machine.type"],
  "size": 5
}'
```

**What you get:**
- Searches across multiple fields at once
- `^2` means "description matches count double" (boosting)
- Results ranked by best overall match

### Try It: Search Everything

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "multi_match": {
      "query": "CNC zone",
      "fields": ["*"],
      "type": "best_fields"
    }
  },
  "size": 3
}'
```

`"fields": ["*"]` searches ALL text fields.

---

## 6. Highlighting (Show What Matched)

### The SQL Problem

SQL has no built-in way to highlight which part of the text matched your search.

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match": {
      "incident.description": "unexpected stop"
    }
  },
  "highlight": {
    "fields": {
      "incident.description": {}
    }
  },
  "_source": ["incident_id"],
  "size": 3
}'
```

**What you get:**

```json
"highlight": {
  "incident.description": [
    "<em>Unexpected</em> <em>stop</em> triggered by sensor."
  ]
}
```

The matched words are wrapped in `<em>` tags — perfect for displaying search results in a UI.

---

## 7. Filter + Query (Scoped Search)

### The SQL Problem

```sql
-- Find "failure" in high-severity CNC machine incidents
SELECT * FROM incidents_clean ic
JOIN machines m ON ic.machine_code = m.machine_code
JOIN machine_types mt ON m.machine_type_id = mt.machine_type_id
WHERE ic.description LIKE '%failure%'
  AND ic.severity = 'high'
  AND mt.category = 'CNC';
```

Works, but multiple joins and no relevance ranking.

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": {
        "match": { "incident.description": "failure" }
      },
      "filter": [
        { "term": { "incident.severity": "high" } },
        { "term": { "machine.category": "CNC" } }
      ]
    }
  }
}'
```

**Key insight:**
- `must` — affects relevance scoring (full-text search)
- `filter` — yes/no filtering, no scoring overhead (faster)

### Try It: Complex Filtered Search

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "query": {
    "bool": {
      "must": {
        "match": { "incident.description": "stopped sensor" }
      },
      "filter": [
        { "terms": { "incident.severity": ["high", "critical"] } },
        { "range": { 
            "timestamp.incident_time": { 
              "gte": "2024-06-01", 
              "lte": "2024-12-31" 
            } 
          } 
        }
      ]
    }
  },
  "size": 5
}'
```

---

## 8. Top-N per Category (Bucket Aggregation + Top Hits)

### The SQL Problem

```sql
-- Get the 2 most recent incidents per zone
-- Requires window functions
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY zone_code 
        ORDER BY incident_time DESC
    ) as rn
    FROM incidents_clean
) WHERE rn <= 2;
```

Works, but window functions aren't always intuitive.

### The OpenSearch Solution

```bash
curl -X GET "localhost:9200/incidents/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 0,
  "aggs": {
    "by_zone": {
      "terms": { "field": "location.zone_name" },
      "aggs": {
        "recent_incidents": {
          "top_hits": {
            "size": 2,
            "sort": [{ "timestamp.incident_time": "desc" }],
            "_source": ["incident_id", "incident.description", "timestamp.incident_time"]
          }
        }
      }
    }
  }
}'
```

**What you get:**
- Buckets by zone
- Top 2 most recent incidents in each zone
- Clean, readable query

---

## Summary: When to Use OpenSearch vs SQL

| Use Case | SQL | OpenSearch |
|----------|-----|------------|
| Exact lookups by ID | ✅ Best | Overkill |
| Complex joins | ✅ Best | Not designed for |
| Transactions/writes | ✅ Best | Eventual consistency |
| Full-text search | ❌ Poor | ✅ Best |
| Typo tolerance | ❌ Manual | ✅ Built-in |
| Relevance ranking | ❌ None | ✅ Best |
| Faceted navigation | ❌ Complex | ✅ Native |
| Date histograms | ⚠️ Verbose | ✅ Easy |
| Highlighting | ❌ None | ✅ Built-in |

**The pattern:** Use SQL for your source of truth and transactional operations. Use OpenSearch for search, exploration, and analytics.

---

## Exercises

1. **Find incidents** mentioning "cut" or "injury" with fuzzy matching enabled
2. **Build a dashboard query** that returns: count by type, count by severity, count by month — all in one request
3. **Search for "assembly"** across all fields, with highlighting enabled
4. **Find the top 3 employees** with the most incidents (hint: terms aggregation on `employee.badge_id`)

---

## Next Steps

- Explore the data visually in **OpenSearch Dashboards**: http://localhost:5601
- Build a Python search module for application integration
- Add more document types (maintenance_logs, shift_assignments)
