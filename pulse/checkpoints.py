"""
pulse/checkpoints.py — 断点续传 (Resume from Checkpoint)

DAG 任务崩溃后, 可从中断位置恢复, 不需全量重跑。
"""

import duckdb


class CheckpointManager:
    def __init__(self, db_path: str = "data/jobs.duckdb") -> None:
        self.con = duckdb.connect(str(db_path))
        self._init_table()

    def _init_table(self) -> None:
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS processing_checkpoints (
                checkpoint_id VARCHAR PRIMARY KEY,
                dag_run_id VARCHAR,
                task_name VARCHAR,
                stage VARCHAR,
                offset_col INTEGER DEFAULT 0,
                total_items INTEGER DEFAULT 0,
                processed_items INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR DEFAULT 'in_progress'
            )
        """)

    def save(
        self, run_id: str, task_name: str, stage: str, offset: int, total: int, processed: int
    ):
        ckpt_id = f"{run_id}_{task_name}_{stage}"
        self.con.execute(
            """
            INSERT OR REPLACE INTO processing_checkpoints
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'in_progress')
        """,
            [ckpt_id, run_id, task_name, stage, offset, total, processed],
        )

    def load(self, run_id: str, task_name: str, stage: str):
        ckpt_id = f"{run_id}_{task_name}_{stage}"
        r = self.con.execute(
            "SELECT offset_col, processed_items FROM processing_checkpoints WHERE checkpoint_id=?",
            [ckpt_id],
        ).fetchone()
        return (r[0], r[1]) if r else (0, 0)

    def complete(self, run_id: str, task_name: str, stage: str) -> None:
        ckpt_id = f"{run_id}_{task_name}_{stage}"
        self.con.execute(
            "UPDATE processing_checkpoints SET status='completed' WHERE checkpoint_id=?", [ckpt_id]
        )
