import sqlite3
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "lecture_companion.db"


def get_connection():
    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():

    connection = get_connection()

    cursor = connection.cursor()

    # --------------------------------------------------------
    # Jobs
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            video_filename TEXT NOT NULL,
            video_path TEXT NOT NULL,
            fps REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # --------------------------------------------------------
    # Slides
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS slides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            slide_number INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            FOREIGN KEY (job_id)
                REFERENCES jobs(job_id)
        )
        """
    )

    # --------------------------------------------------------
    # Slide occurrences
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS slide_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slide_id INTEGER NOT NULL,
            appearance_index INTEGER NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            FOREIGN KEY (slide_id)
                REFERENCES slides(id)
        )
        """
    )

    # --------------------------------------------------------
    # Speech segments
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS speech_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slide_occurrence_id INTEGER NOT NULL,
            transcript_segment_id INTEGER,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            text TEXT NOT NULL,
            FOREIGN KEY (slide_occurrence_id)
                REFERENCES slide_occurrences(id)
        )
        """
    )

    # --------------------------------------------------------
    # Full-text search
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS speech_fts
        USING fts5(
            text,
            content='speech_segments',
            content_rowid='id'
        )
        """
    )

    connection.commit()
    connection.close()


def save_job(
    job_id: str,
    video_filename: str,
    video_path: str,
    fps: float,
):

    connection = get_connection()

    connection.execute(
        """
        INSERT OR REPLACE INTO jobs (
            job_id,
            video_filename,
            video_path,
            fps,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            job_id,
            video_filename,
            video_path,
            fps,
            datetime.now().isoformat(),
        ),
    )

    connection.commit()
    connection.close()


def save_linked_slides(
    job_id: str,
    linked_slides: list | dict,
):

    if isinstance(linked_slides, dict):
        slides = linked_slides.get("slides", [])
    else:
        slides = linked_slides

    if not isinstance(slides, list):
        raise TypeError(
            "linked_slides must be a list or a dict containing a 'slides' list."
        )

    connection = get_connection()

    cursor = connection.cursor()

    for slide in slides:

        slide_number = slide.get(
            "slide_id"
        )

        image_path = slide.get(
            "representative_path"
        )

        if not image_path:
            continue

        cursor.execute(
            """
            INSERT INTO slides (
                job_id,
                slide_number,
                image_path
            )
            VALUES (?, ?, ?)
            """,
            (
                job_id,
                slide_number,
                image_path,
            ),
        )

        slide_db_id = cursor.lastrowid

        occurrences = slide.get(
            "occurrences",
            [],
        )

        for occurrence in occurrences:

            cursor.execute(
                """
                INSERT INTO slide_occurrences (
                    slide_id,
                    appearance_index,
                    start_time,
                    end_time
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    slide_db_id,
                    occurrence.get(
                        "appearance_index",
                        0,
                    ),
                    occurrence.get(
                        "start_time",
                        0.0,
                    ),
                    occurrence.get(
                        "end_time",
                        0.0,
                    ),
                ),
            )

            occurrence_db_id = cursor.lastrowid

            speech_segments = occurrence.get(
                "speech_segments",
                [],
            )

            for segment in speech_segments:

                cursor.execute(
                    """
                    INSERT INTO speech_segments (
                        slide_occurrence_id,
                        transcript_segment_id,
                        start_time,
                        end_time,
                        text
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        occurrence_db_id,
                        segment.get(
                            "segment_id"
                        ),
                        segment.get(
                            "start",
                            0.0,
                        ),
                        segment.get(
                            "end",
                            0.0,
                        ),
                        segment.get(
                            "text",
                            "",
                        ),
                    ),
                )

                speech_db_id = cursor.lastrowid

                cursor.execute(
                    """
                    INSERT INTO speech_fts (
                        rowid,
                        text
                    )
                    VALUES (?, ?)
                    """,
                    (
                        speech_db_id,
                        segment.get(
                            "text",
                            "",
                        ),
                    ),
                )

    connection.commit()
    connection.close()


def search_lecture(
    job_id: str,
    query: str,
    limit: int = 10,
):

    connection = get_connection()

    cursor = connection.cursor()

    # --------------------------------------------------------
    # Convert plain English input into safe FTS terms
    # --------------------------------------------------------

    words = [
        word.strip()
        for word in query.lower().split()
        if word.strip().isalnum()
    ]

    if not words:
        connection.close()
        return []

    fts_query = " OR ".join(
        f'"{word}"'
        for word in words
    )

    # --------------------------------------------------------
    # Search transcript
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT
            speech_segments.id,
            speech_segments.start_time,
            speech_segments.end_time,
            speech_segments.text,
            slide_occurrences.start_time
                AS slide_start_time,
            slide_occurrences.end_time
                AS slide_end_time,
            slides.slide_number,
            slides.image_path,
            bm25(speech_fts) AS rank

        FROM speech_fts

        JOIN speech_segments
            ON speech_segments.id = speech_fts.rowid

        JOIN slide_occurrences
            ON slide_occurrences.id =
               speech_segments.slide_occurrence_id

        JOIN slides
            ON slides.id =
               slide_occurrences.slide_id

        WHERE speech_fts MATCH ?
          AND slides.job_id = ?

        ORDER BY rank

        LIMIT ?
        """,
        (
            fts_query,
            job_id,
            limit,
        ),
    )

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]