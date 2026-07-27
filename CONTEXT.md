# Pulse Data Engine — Domain Context

A lightweight data pipeline that collects job listings from multiple public APIs,
validates them through Pydantic contracts, stores them in a three-layer medallion
architecture, and exposes them via Iceberg time travel + SQL browser query.

## Language

**ODS (操作数据存储)**:
The raw ingestion layer. Append-only, SCD Type 2 versioned.
_Avoid_: Raw table, source data, landing zone

**DWD (数据仓库明细)**:
The cleaned, classified, de-duplicated layer. One row per entity (latest version).
_Avoid_: Clean table, transformed data

**DWS (数据仓库汇总)**:
Pre-computed aggregations — salary percentiles by skill category and city.
_Avoid_: Aggregations, summary tables, BI layer

**Data Contract**:
A Pydantic v2 model that validates every record before it enters ODS.
Violations → DLQ. Not a quality scanner for data already in the warehouse.
_Avoid_: Schema, validation rule, quality check

**DLQ (死信队列)**:
A DuckDB table holding records that failed the Data Contract or exhausted retries.
Records can be reprocessed when the Contract is relaxed.
_Avoid_: Dead letter, error log, trash

**SCD Type 2**:
Versioning strategy: each entity (identified by URL hash) gets a new row when
salary/title/city changes. `is_latest` flag marks the active version.
_Avoid_: History table, changelog

**Source / Extractor**:
An adapter module that calls an external API and returns records in
RawJobContract-compatible dict format. Stateless, no caching.
_Avoid_: Connector, crawler, fetcher (fetcher is the HTTP layer, not the adapter)

**Asset (Dagster)**:
A single materializable unit in the Dagster graph. Maps 1:1 to a table layer
(ods_raw_jobs, dwd_cleaned_jobs, dws_skill_agg) or an export (parquet, iceberg).
_Avoid_: Task, DAG node, step

**Iceberg Snapshot**:
A point-in-time view of the entire ODS table, created each pipeline run.
Enables time travel via `iceberg_scan(path, snapshot_from_id=N)`.
_Avoid_: Backup, checkpoint, Parquet file
