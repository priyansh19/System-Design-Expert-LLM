# Proximity Search & Geohashing

## Summary
Proximity search finds entities (drivers, restaurants, stores) near a location, requiring an encoding of 2D coordinates that supports fast range queries — geohashing, quadtrees, and S2 cells are the dominant approaches.

## Core Principles
- Geohashing encodes lat/lng into a base32 string by subdividing the world into a grid; each added character increases precision, and shared prefixes mean proximity (mostly).
- Quadtrees recursively divide space into four quadrants until each leaf holds a bounded number of points, giving adaptive resolution — dense areas get finer cells.
- R-trees group nearby objects into minimum bounding rectangles, efficient for indexing regions, and used natively by PostGIS.
- Google's S2 library maps the sphere to a cube then a Hilbert curve per face, avoiding pole/dateline distortion flat grids suffer from.
- The geohash "edge problem": nearby points can have different prefixes when straddling a grid boundary, requiring neighbor-cell queries, not just prefix match.

## When to Use / When Not
- Use geohash/S2 indexing for "find nearby X" queries at scale — ride-hailing matching, restaurant discovery, store locators.
- Use R-trees for indexing polygons/regions (delivery zones, geofences) rather than points, or within a single-node spatial database.
- Avoid geohash prefix-only matching when boundary precision matters — always expand to neighbor cells.

## Tradeoffs
- Geohash simplicity (string prefix = shard key) vs boundary artifacts requiring neighbor-cell handling for correctness.
- Quadtree adaptive density vs rebalancing cost as data shifts (rush-hour driver clustering).
- S2's spherical accuracy and uniform cell area vs higher implementation complexity than a plain geohash string.

## Common Patterns & Techniques
- Redis `GEOADD`/`GEORADIUS` implement geohash-backed sorted sets for in-memory proximity queries at low latency.
- Sharding by region: geohash/S2-cell prefixes make natural shard keys, colocating nearby entities on the same node.
- Query expansion: search the target cell plus its 8 neighbors to correctly capture near-boundary matches.
- Two-phase search: coarse cell filter to shrink candidates, then precise Haversine distance on the shortlist.

## Pitfalls
- Relying on geohash prefix equality alone and silently missing nearby points across a cell boundary.
- Using flat Euclidean distance instead of great-circle (Haversine) distance, causing meaningful error at scale or high latitude.
- Choosing one fixed geohash precision for both dense urban and sparse rural regions instead of adapting to density.

## Real-World Examples
- Uber's H3 hexagonal grid (successor to early geohash use) indexes locations for matching and surge computation, favoring hexagons for uniform neighbor distance.
- Yelp and Foursquare use geohash-based indexes (Elasticsearch geo-queries) for "restaurants near me" search.
- Google Maps uses the S2 cell hierarchy for spherical-accurate spatial indexing across its location services.
</content>
<parameter name="i">Rewrite proximity-geohashing tighter