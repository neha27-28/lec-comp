"""
database.py
-----------

Local SQLite persistence for Lecture Companion.

Stores:
- processing jobs
- extracted logical slides
- chronological slide occurrences
- timestamped speech segments
- FTS5 transcript search
- complete per-job performance/benchmark metadata
"""

from pathlib import Path
import sqlite3
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lecture_companion.db"


# -------------------------------------------------------------------
# Connection
# -------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DB_PATH))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# -------------------------------------------------------------------
# Schema / migration
# -------------------------------------------------------------------

JOB_COLUMNS = {
    "video_size_bytes": "INTEGER",
    "video_duration_sec": "REAL",
    "processing_fps": "REAL",
    "whisper_model": "TEXT",
    "device": "TEXT",
    "download_time_sec": "REAL",
    "frame_extraction_time_sec": "REAL",
    "slide_detection_time_sec": "REAL",
    "pdf_generation_time_sec": "REAL",
    "audio_extraction_time_sec": "REAL",
    "transcription_time_sec": "REAL",
    "slide_speech_linking_time_sec": "REAL",
    "database_storage_time_sec": "REAL",
    "total_processing_time_sec": "REAL",
    "frames_extracted": "INTEGER",
    "unique_slides": "INTEGER",
    "slide_appearances": "INTEGER",
    "transcript_segments": "INTEGER",
    "transcript_words": "INTEGER",
    "pdf_size_bytes": "INTEGER",
    "processing_ratio": "REAL",
    "peak_memory_mb": "REAL",
}


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    existing = {
        row["name"]
        for row in connection.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in existing:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


def initialize_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                video_filename TEXT NOT NULL,
                video_path TEXT NOT NULL,
                fps REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS slides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                slide_id INTEGER NOT NULL,
                representative_path TEXT,
                speech_text TEXT DEFAULT '',
                FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
                UNIQUE(job_id, slide_id)
            );

            CREATE TABLE IF NOT EXISTS slide_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slide_db_id INTEGER NOT NULL,
                appearance_index INTEGER,
                start_frame INTEGER NOT NULL,
                end_frame INTEGER NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                speech_text TEXT DEFAULT '',
                FOREIGN KEY(slide_db_id) REFERENCES slides(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS speech_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                occurrence_id INTEGER,
                segment_id INTEGER,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
                FOREIGN KEY(occurrence_id) REFERENCES slide_occurrences(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_slides_job
                ON slides(job_id);

            CREATE INDEX IF NOT EXISTS idx_occurrences_slide
                ON slide_occurrences(slide_db_id);

            CREATE INDEX IF NOT EXISTS idx_speech_job
                ON speech_segments(job_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS speech_fts USING fts5(
                text,
                job_id UNINDEXED,
                speech_segment_id UNINDEXED,
                slide_db_id UNINDEXED,
                start_time UNINDEXED,
                end_time UNINDEXED,
                slide_number UNINDEXED,
                image_path UNINDEXED,
                tokenize='unicode61'
            );
            """
        )

        # Migrate an existing jobs table without destroying data.
        for column, definition in JOB_COLUMNS.items():
            _ensure_column(
                connection,
                "jobs",
                column,
                definition,
            )

        connection.commit()


# -------------------------------------------------------------------
# Jobs
# -------------------------------------------------------------------

def save_job(
    job_id: str,
    video_filename: str,
    video_path: str,
    fps: float,
) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO jobs (
                job_id,
                video_filename,
                video_path,
                fps
            ) VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                video_filename,
                video_path,
                float(fps),
            ),
        )
        connection.commit()


def update_job_performance(
    job_id: str,
    metrics: dict[str, Any],
) -> None:
    """
    Persist complete benchmark/performance metadata for one job.
    """

    allowed = set(JOB_COLUMNS)
    updates = {
        key: value
        for key, value in metrics.items()
        if key in allowed
    }

    if not updates:
        return

    assignments = ", ".join(
        f"{key} = ?"
        for key in updates
    )

    values = list(updates.values())
    values.append(job_id)

    with get_connection() as connection:
        connection.execute(
            f"UPDATE jobs SET {assignments} WHERE job_id = ?",
            values,
        )
        connection.commit()


# -------------------------------------------------------------------
# Linked slide / speech storage
# -------------------------------------------------------------------

def save_linked_slides(
    job_id: str,
    linked_slides: list[dict[str, Any]],
) -> None:
    with get_connection() as connection:
        # Allow a retry of the same job without duplicating records.
        connection.execute(
            "DELETE FROM speech_fts WHERE job_id = ?",
            (job_id,),
        )
        connection.execute(
            "DELETE FROM speech_segments WHERE job_id = ?",
            (job_id,),
        )
        connection.execute(
            """
            DELETE FROM slide_occurrences
            WHERE slide_db_id IN (
                SELECT id FROM slides WHERE job_id = ?
            )
            """,
            (job_id,),
        )
        connection.execute(
            "DELETE FROM slides WHERE job_id = ?",
            (job_id,),
        )

        for slide in linked_slides:
            slide_id = int(slide["slide_id"])
            representative_path = slide.get("representative_path")
            speech_text = slide.get("speech_text", "") or ""

            cursor = connection.execute(
                """
                INSERT INTO slides (
                    job_id,
                    slide_id,
                    representative_path,
                    speech_text
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    job_id,
                    slide_id,
                    representative_path,
                    speech_text,
                ),
            )
            slide_db_id = cursor.lastrowid

            for occurrence in slide.get("occurrences", []):
                cursor = connection.execute(
                    """
                    INSERT INTO slide_occurrences (
                        slide_db_id,
                        appearance_index,
                        start_frame,
                        end_frame,
                        start_time,
                        end_time,
                        speech_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        slide_db_id,
                        occurrence.get("appearance_index"),
                        int(occurrence["start_frame"]),
                        int(occurrence["end_frame"]),
                        float(occurrence["start_time"]),
                        float(occurrence["end_time"]),
                        occurrence.get("speech_text", "") or "",
                    ),
                )
                occurrence_db_id = cursor.lastrowid

                for segment in occurrence.get("speech_segments", []):
                    text = (segment.get("text") or "").strip()
                    if not text:
                        continue

                    cursor = connection.execute(
                        """
                        INSERT INTO speech_segments (
                            job_id,
                            occurrence_id,
                            segment_id,
                            start_time,
                            end_time,
                            text
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job_id,
                            occurrence_db_id,
                            segment.get("segment_id"),
                            float(segment["start"]),
                            float(segment["end"]),
                            text,
                        ),
                    )
                    speech_segment_id = cursor.lastrowid

                    connection.execute(
                        """
                        INSERT INTO speech_fts (
                            text,
                            job_id,
                            speech_segment_id,
                            slide_db_id,
                            start_time,
                            end_time,
                            slide_number,
                            image_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            text,
                            job_id,
                            speech_segment_id,
                            slide_db_id,
                            float(segment["start"]),
                            float(segment["end"]),
                            slide_id,
                            representative_path,
                        ),
                    )

        connection.commit()


# -------------------------------------------------------------------
# Search
# -------------------------------------------------------------------

def search_lecture(
    job_id: str,
    query: str,
) -> list[dict[str, Any]]:
    words = [
        word
        for word in query.split()
        if word.isalnum()
    ]

    if not words:
        return []

    fts_query = " OR ".join(words)

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                ss.id AS id,
                ss.text AS text,
                ss.start_time AS start_time,
                ss.end_time AS end_time,
                sf.slide_number AS slide_number,
                sf.image_path AS image_path,
                bm25(speech_fts) AS rank
            FROM speech_fts AS sf
            JOIN speech_segments AS ss
                ON ss.id = sf.speech_segment_id
            WHERE sf.job_id = ?
              AND speech_fts MATCH ?
            ORDER BY rank ASC, ss.start_time ASC
            LIMIT 50
            """,
            (job_id, fts_query),
        ).fetchall()

    return [dict(row) for row in rows]
