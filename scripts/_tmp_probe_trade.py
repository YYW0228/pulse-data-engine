"""临时: 外贸企业名单种子提取 (从 Pulse 招聘数据)"""
import duckdb

con = duckdb.connect("data/jobs.duckdb", read_only=True)
rows = con.execute(
    """
    SELECT company, city, COUNT(*) as n, MIN(title) as sample_title
    FROM dwd_cleaned_jobs
    WHERE (
      title ILIKE '%外贸%' OR title ILIKE '%跨境%' OR title ILIKE '%海外%'
      OR title ILIKE '%国际%' OR title ILIKE '%出口%' OR title ILIKE '%采购%'
    )
    AND company NOT ILIKE '某%'
    GROUP BY company, city
    ORDER BY n DESC LIMIT 30
    """
).fetchall()
for r in rows:
    print(f"{r[1]} | {r[0]} | {r[2]}岗位 | {str(r[3])[:40]}")
print("---")
total = con.execute(
    """SELECT COUNT(*) FROM dwd_cleaned_jobs WHERE (
    title ILIKE '%外贸%' OR title ILIKE '%跨境%' OR title ILIKE '%海外%'
    OR title ILIKE '%国际%' OR title ILIKE '%出口%')"""
).fetchone()[0]
print("外贸相关岗位总数:", total)
