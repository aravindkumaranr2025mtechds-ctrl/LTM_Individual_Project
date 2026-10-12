import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile


UPLOAD_DIRECTORY = Path("data/raw_documents")

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".docx"
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


async def save_uploaded_document(file: UploadFile) -> dict:
    """
    Validate an uploaded document and save it inside data/raw_documents.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="The uploaded document does not have a filename."
        )

    original_filename = Path(file.filename).name
    file_extension = Path(original_filename).suffix.lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF, TXT and DOCX documents are allowed."
        )

    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

    unique_filename = f"{uuid4().hex}_{original_filename}"
    saved_file_path = UPLOAD_DIRECTORY / unique_filename

    file_size = 0

    source_hasher = hashlib.sha256()
    try:
        with saved_file_path.open("wb") as output_file:
            while True:
                file_chunk = await file.read(1024 * 1024)

                if not file_chunk:
                    break

                file_size += len(file_chunk)

                if file_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="The uploaded document exceeds the 20 MB limit."
                    )

                source_hasher.update(file_chunk)

                output_file.write(file_chunk)
        if file_size == 0:
            raise HTTPException(
                status_code=400,
                detail="The uploaded document is empty."
            )

    except Exception:
        if saved_file_path.exists():
            saved_file_path.unlink()
        raise

    finally:
        await file.close()

    document_id = Path(unique_filename).stem

    return {
        "document_id": document_id,
        "original_filename": original_filename,
        "stored_filename": unique_filename,
        "file_type": file_extension,
        "file_size_bytes": file_size,
        "source_sha256": source_hasher.hexdigest(),
        "saved_location": str(saved_file_path)
    }

# === ENTERPRISE DOCUMENT REGISTRY V1 ===

REGISTRY_DATABASE = Path("data/document_registry.sqlite3")
REGISTRY_SCHEMA_VERSION = 3


ENTERPRISE_METADATA_FIELDS = (
    "plant_id",
    "department",
    "equipment_id",
    "equipment_type",
    "manufacturer",
    "model",
    "document_family_id",
    "supersedes_document_id",
    "document_type",
    "revision",
    "effective_date",
    "document_status",
    "access_level",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_optional_text(value: str | None) -> str | None:
    """
    Normalize optional enterprise metadata.

    Missing values remain unknown and are never inferred.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            "Enterprise metadata values must be strings or None."
        )

    cleaned = value.strip()

    return cleaned if cleaned else None


def _validate_sha256(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("source_sha256 must be a string.")

    cleaned = value.strip().lower()

    if (
        len(cleaned) != 64
        or any(
            character not in "0123456789abcdef"
            for character in cleaned
        )
    ):
        raise ValueError(
            "source_sha256 must contain exactly "
            "64 hexadecimal characters."
        )

    return cleaned


def initialize_document_registry(
    database_path: Path = REGISTRY_DATABASE,
) -> None:
    """
    Create the enterprise registry if necessary.

    Safe to call repeatedly.
    """
    database_path = Path(database_path)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with closing(sqlite3.connect(database_path)) as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS enterprise_documents (
                document_id TEXT PRIMARY KEY,

                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL,

                file_size_bytes INTEGER NOT NULL
                    CHECK(file_size_bytes > 0),

                source_sha256 TEXT NOT NULL,

                document_family_id TEXT,
                supersedes_document_id TEXT,

                plant_id TEXT,
                department TEXT,

                equipment_id TEXT,
                equipment_type TEXT,
                manufacturer TEXT,
                model TEXT,

                document_type TEXT,
                revision TEXT,
                effective_date TEXT,

                document_status TEXT,
                access_level TEXT,

                ingested_at_utc TEXT NOT NULL,
                metadata_updated_at_utc TEXT NOT NULL
            )
            """
        )

        existing_columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(enterprise_documents)"
            ).fetchall()
        }

        safe_v2_columns = {
            "document_family_id": "TEXT",
            "supersedes_document_id": "TEXT",
        }

        for column_name, column_type in safe_v2_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE enterprise_documents "
                    f"ADD COLUMN {column_name} {column_type}"
                )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS registry_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT INTO registry_metadata(key, value)
            VALUES('schema_version', ?)

            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            """,
            (str(REGISTRY_SCHEMA_VERSION),),
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_sha256
            ON enterprise_documents(source_sha256)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_family
            ON enterprise_documents(document_family_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_plant
            ON enterprise_documents(plant_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_department
            ON enterprise_documents(department)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_equipment
            ON enterprise_documents(equipment_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_document_type
            ON enterprise_documents(document_type)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_manufacturer
            ON enterprise_documents(manufacturer)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_enterprise_documents_status
            ON enterprise_documents(document_status)
            """
        )

        # Registry schema V3:
        # one enterprise document may have multiple vector artifacts.
        #
        # No artifact is automatically treated as current,
        # preferred, approved, or safe for retrieval.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_vector_artifacts (
                vector_artifact_id TEXT PRIMARY KEY,

                document_id TEXT NOT NULL,

                vector_store_filename TEXT NOT NULL UNIQUE,
                prepared_filename TEXT NOT NULL,

                prepared_sha256 TEXT NOT NULL,
                vector_store_sha256 TEXT NOT NULL,

                embedding_model TEXT NOT NULL,
                embedding_dimension INTEGER NOT NULL
                    CHECK(embedding_dimension > 0),

                vector_count INTEGER NOT NULL
                    CHECK(vector_count > 0),

                embedding_created_at_utc TEXT NOT NULL,
                registered_at_utc TEXT NOT NULL,

                FOREIGN KEY(document_id)
                    REFERENCES enterprise_documents(document_id)
                    ON DELETE RESTRICT
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_document_vector_artifacts_document
            ON document_vector_artifacts(document_id)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_document_vector_artifacts_sha256
            ON document_vector_artifacts(vector_store_sha256)
            """
        )

        connection.commit()


def register_enterprise_document(
    document_information: dict,
    *,
    plant_id: str | None = None,
    department: str | None = None,
    equipment_id: str | None = None,
    equipment_type: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    document_family_id: str | None = None,
    supersedes_document_id: str | None = None,
    document_type: str | None = None,
    revision: str | None = None,
    effective_date: str | None = None,
    document_status: str | None = None,
    access_level: str | None = None,
    database_path: Path = REGISTRY_DATABASE,
) -> dict:
    """
    Register one uploaded document.

    The function does not infer missing enterprise metadata.
    """
    if not isinstance(document_information, dict):
        raise ValueError(
            "document_information must be a dictionary."
        )

    required = (
        "document_id",
        "original_filename",
        "stored_filename",
        "file_type",
        "file_size_bytes",
        "source_sha256",
    )

    missing = [
        key
        for key in required
        if key not in document_information
    ]

    if missing:
        raise ValueError(
            f"Missing document identity fields: {missing}"
        )

    document_id = document_information["document_id"]
    original_filename = document_information["original_filename"]
    stored_filename = document_information["stored_filename"]
    file_type = document_information["file_type"]
    file_size_bytes = document_information["file_size_bytes"]

    for name, value in (
        ("document_id", document_id),
        ("original_filename", original_filename),
        ("stored_filename", stored_filename),
        ("file_type", file_type),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{name} must be a non-empty string."
            )

    if (
        type(file_size_bytes) is not int
        or file_size_bytes <= 0
    ):
        raise ValueError(
            "file_size_bytes must be a positive integer."
        )

    source_sha256 = _validate_sha256(
        document_information["source_sha256"]
    )

    metadata = {
        "plant_id": _clean_optional_text(plant_id),
        "department": _clean_optional_text(department),
        "equipment_id": _clean_optional_text(equipment_id),
        "equipment_type": _clean_optional_text(
            equipment_type
        ),
        "manufacturer": _clean_optional_text(
            manufacturer
        ),
        "model": _clean_optional_text(model),
        "document_family_id": _clean_optional_text(
            document_family_id
        ),
        "supersedes_document_id": _clean_optional_text(
            supersedes_document_id
        ),
        "document_type": _clean_optional_text(
            document_type
        ),
        "revision": _clean_optional_text(revision),
        "effective_date": _clean_optional_text(
            effective_date
        ),
        "document_status": _clean_optional_text(
            document_status
        ),
        "access_level": _clean_optional_text(
            access_level
        ),
    }

    if metadata["supersedes_document_id"] is not None:

        if metadata["document_family_id"] is None:
            raise ValueError(
                "document_family_id is required when "
                "supersedes_document_id is provided."
            )

        predecessor = get_enterprise_document(
            metadata["supersedes_document_id"],
            database_path=database_path,
        )

        if predecessor is None:
            raise ValueError(
                "supersedes_document_id does not reference "
                "an existing registered document."
            )

        if (
            predecessor.get("document_family_id")
            != metadata["document_family_id"]
        ):
            raise ValueError(
                "A document may supersede only another document "
                "from the same document_family_id."
            )

    timestamp = _utc_now_iso()

    initialize_document_registry(database_path)

    with closing(sqlite3.connect(database_path)) as connection:

        connection.row_factory = sqlite3.Row

        try:
            connection.execute(
                """
                INSERT INTO enterprise_documents (
                    document_id,
                    original_filename,
                    stored_filename,
                    file_type,
                    file_size_bytes,
                    source_sha256,

                    document_family_id,
                    supersedes_document_id,

                    plant_id,
                    department,

                    equipment_id,
                    equipment_type,
                    manufacturer,
                    model,

                    document_type,
                    revision,
                    effective_date,

                    document_status,
                    access_level,

                    ingested_at_utc,
                    metadata_updated_at_utc
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?
                )
                """,
                (
                    document_id,
                    original_filename,
                    stored_filename,
                    file_type,
                    file_size_bytes,
                    source_sha256,

                    metadata["document_family_id"],
                    metadata["supersedes_document_id"],

                    metadata["plant_id"],
                    metadata["department"],

                    metadata["equipment_id"],
                    metadata["equipment_type"],
                    metadata["manufacturer"],
                    metadata["model"],

                    metadata["document_type"],
                    metadata["revision"],
                    metadata["effective_date"],

                    metadata["document_status"],
                    metadata["access_level"],

                    timestamp,
                    timestamp,
                ),
            )

        except sqlite3.IntegrityError as error:
            raise ValueError(
                "A registry record with the same "
                "document_id or stored_filename already exists."
            ) from error

        connection.commit()

        row = connection.execute(
            """
            SELECT *
            FROM enterprise_documents
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "Registry insert succeeded but the record "
            "could not be read back."
        )

    return dict(row)


def get_enterprise_document(
    document_id: str,
    *,
    database_path: Path = REGISTRY_DATABASE,
) -> dict | None:

    if not isinstance(document_id, str):
        raise ValueError(
            "document_id must be a non-empty string."
        )

    document_id = document_id.strip()

    if not document_id:
        raise ValueError(
            "document_id must be a non-empty string."
        )

    database_path = Path(database_path)

    if not database_path.is_file():
        return None

    with closing(sqlite3.connect(database_path)) as connection:

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM enterprise_documents
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()

    return dict(row) if row is not None else None



# === ENTERPRISE VECTOR ARTIFACT REGISTRY V1 ===

def _clean_artifact_filename(
    value: str,
    *,
    field_name: str,
    suffix: str,
) -> str:
    """
    Validate a registry artifact filename.

    Only a filename is accepted; directory paths are forbidden.
    """
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a non-empty string."
        )

    cleaned = value.strip()

    if not cleaned:
        raise ValueError(
            f"{field_name} must be a non-empty string."
        )

    if (
        any(character in cleaned for character in "/\\:\x00")
        or Path(cleaned).name != cleaned
        or Path(cleaned).suffix.lower() != suffix
    ):
        raise ValueError(
            f"{field_name} must be a {suffix} filename "
            "without a folder path."
        )

    if len(cleaned) > 255:
        raise ValueError(
            f"{field_name} exceeds 255 characters."
        )

    return cleaned


def register_document_vector_artifact(
    artifact_information: dict,
    *,
    database_path: Path = REGISTRY_DATABASE,
) -> dict:
    """
    Register one derived vector-store artifact.

    Multiple artifacts may reference the same enterprise document.

    Registration does not mark an artifact as current, preferred,
    approved, or authorized for retrieval.
    """
    if not isinstance(artifact_information, dict):
        raise ValueError(
            "artifact_information must be a dictionary."
        )

    required = (
        "document_id",
        "vector_store_filename",
        "prepared_filename",
        "prepared_sha256",
        "vector_store_sha256",
        "embedding_model",
        "embedding_dimension",
        "vector_count",
        "embedding_created_at_utc",
    )

    missing = [
        key
        for key in required
        if key not in artifact_information
    ]

    if missing:
        raise ValueError(
            f"Missing vector artifact fields: {missing}"
        )

    document_id = artifact_information[
        "document_id"
    ]

    if not isinstance(document_id, str):
        raise ValueError(
            "document_id must be a non-empty string."
        )

    document_id = document_id.strip()

    if not document_id:
        raise ValueError(
            "document_id must be a non-empty string."
        )

    document = get_enterprise_document(
        document_id,
        database_path=database_path,
    )

    if document is None:
        raise ValueError(
            "Vector artifacts may be registered only for "
            "an existing enterprise document."
        )

    vector_store_filename = _clean_artifact_filename(
        artifact_information[
            "vector_store_filename"
        ],
        field_name="vector_store_filename",
        suffix=".npz",
    )

    prepared_filename = _clean_artifact_filename(
        artifact_information[
            "prepared_filename"
        ],
        field_name="prepared_filename",
        suffix=".json",
    )

    prepared_sha256 = _validate_sha256(
        artifact_information[
            "prepared_sha256"
        ]
    )

    vector_store_sha256 = _validate_sha256(
        artifact_information[
            "vector_store_sha256"
        ]
    )

    embedding_model = artifact_information[
        "embedding_model"
    ]

    if (
        not isinstance(embedding_model, str)
        or not embedding_model.strip()
    ):
        raise ValueError(
            "embedding_model must be a non-empty string."
        )

    embedding_model = embedding_model.strip()

    if len(embedding_model) > 255:
        raise ValueError(
            "embedding_model exceeds 255 characters."
        )

    embedding_dimension = artifact_information[
        "embedding_dimension"
    ]

    if (
        type(embedding_dimension) is not int
        or embedding_dimension <= 0
    ):
        raise ValueError(
            "embedding_dimension must be a positive integer."
        )

    vector_count = artifact_information[
        "vector_count"
    ]

    if (
        type(vector_count) is not int
        or vector_count <= 0
    ):
        raise ValueError(
            "vector_count must be a positive integer."
        )

    embedding_created_at_utc = artifact_information[
        "embedding_created_at_utc"
    ]

    if (
        not isinstance(embedding_created_at_utc, str)
        or not embedding_created_at_utc.strip()
    ):
        raise ValueError(
            "embedding_created_at_utc must be "
            "a non-empty string."
        )

    embedding_created_at_utc = (
        embedding_created_at_utc.strip()
    )

    vector_artifact_id = (
        "vec_" + uuid4().hex
    )

    registered_at_utc = _utc_now_iso()

    initialize_document_registry(
        database_path
    )

    with closing(
        sqlite3.connect(database_path)
    ) as connection:

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        try:
            connection.execute(
                """
                INSERT INTO document_vector_artifacts (
                    vector_artifact_id,
                    document_id,
                    vector_store_filename,
                    prepared_filename,
                    prepared_sha256,
                    vector_store_sha256,
                    embedding_model,
                    embedding_dimension,
                    vector_count,
                    embedding_created_at_utc,
                    registered_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vector_artifact_id,
                    document_id,
                    vector_store_filename,
                    prepared_filename,
                    prepared_sha256,
                    vector_store_sha256,
                    embedding_model,
                    embedding_dimension,
                    vector_count,
                    embedding_created_at_utc,
                    registered_at_utc,
                ),
            )

        except sqlite3.IntegrityError as error:
            raise ValueError(
                "A vector artifact with the same "
                "vector_store_filename or artifact identity "
                "already exists."
            ) from error

        connection.commit()

        row = connection.execute(
            """
            SELECT *
            FROM document_vector_artifacts
            WHERE vector_artifact_id = ?
            """,
            (vector_artifact_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "Vector artifact registration succeeded but "
            "the record could not be read back."
        )

    return dict(row)


def get_document_vector_artifact(
    vector_store_filename: str,
    *,
    database_path: Path = REGISTRY_DATABASE,
) -> dict | None:
    """
    Read one vector artifact by its exact stored filename.
    """
    vector_store_filename = _clean_artifact_filename(
        vector_store_filename,
        field_name="vector_store_filename",
        suffix=".npz",
    )

    database_path = Path(
        database_path
    )

    if not database_path.is_file():
        return None

    with closing(
        sqlite3.connect(database_path)
    ) as connection:

        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM document_vector_artifacts
            WHERE vector_store_filename = ?
            """,
            (vector_store_filename,),
        ).fetchone()

    return (
        dict(row)
        if row is not None
        else None
    )


def find_document_vector_artifacts(
    document_id: str,
    *,
    database_path: Path = REGISTRY_DATABASE,
) -> list[dict]:
    """
    Return every registered vector artifact for one document.

    Ordering is deterministic for inspection only and does not
    imply preference, approval, revision order, or retrieval rank.
    """
    if not isinstance(document_id, str):
        raise ValueError(
            "document_id must be a non-empty string."
        )

    document_id = document_id.strip()

    if not document_id:
        raise ValueError(
            "document_id must be a non-empty string."
        )

    database_path = Path(
        database_path
    )

    if not database_path.is_file():
        return []

    with closing(
        sqlite3.connect(database_path)
    ) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT *
            FROM document_vector_artifacts
            WHERE document_id = ?
            ORDER BY registered_at_utc, vector_store_filename
            """,
            (document_id,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]



# === ENTERPRISE VECTOR CANDIDATE DISCOVERY V1 ===

ENTERPRISE_VECTOR_DISCOVERY_FILTER_FIELDS = (
    "plant_id",
    "department",
    "equipment_id",
    "equipment_type",
    "manufacturer",
    "model",
    "document_family_id",
    "document_type",
    "revision",
    "document_status",
)


def _normalize_enterprise_vector_discovery_filters(
    metadata_filters=None,
) -> dict:
    """
    Validate explicit enterprise vector-discovery filters.

    Missing metadata is not inferred.

    access_level is intentionally not caller-selectable here;
    authorization will be enforced separately from retrieval
    metadata filtering.
    """
    if metadata_filters is None:
        return {}

    if not isinstance(metadata_filters, dict):
        raise ValueError(
            "metadata_filters must be an object or null."
        )

    unsupported = sorted(
        set(metadata_filters)
        - set(
            ENTERPRISE_VECTOR_DISCOVERY_FILTER_FIELDS
        )
    )

    if unsupported:
        raise ValueError(
            "Unsupported enterprise discovery "
            "filter field(s): "
            + ", ".join(unsupported)
        )

    normalized = {}

    for field in (
        ENTERPRISE_VECTOR_DISCOVERY_FILTER_FIELDS
    ):

        value = metadata_filters.get(
            field
        )

        if value is None:
            continue

        if not isinstance(value, str):
            raise ValueError(
                f"{field} must be a string or null."
            )

        cleaned = value.strip()

        if not cleaned:
            continue

        if len(cleaned) > 255:
            raise ValueError(
                f"{field} exceeds 255 characters."
            )

        normalized[field] = cleaned

    return normalized


def discover_enterprise_vector_artifacts(
    metadata_filters=None,
    *,
    database_path: Path = REGISTRY_DATABASE,
) -> dict:
    """
    Discover registered vector artifacts using explicit
    enterprise document metadata.

    This function performs registry discovery only.

    It does not:
    - select a preferred artifact,
    - infer revision order,
    - infer document status,
    - authorize access,
    - open vector files,
    - execute semantic retrieval.

    If one document has multiple matching artifacts, all are
    returned and the document is reported as ambiguous.
    """
    filters = (
        _normalize_enterprise_vector_discovery_filters(
            metadata_filters
        )
    )

    database_path = Path(
        database_path
    )

    empty_result = {
        "metadata_filters": filters,
        "metadata_filter_applied": bool(filters),
        "documents_with_artifacts": 0,
        "artifacts_count": 0,
        "candidate_artifacts": [],
        "single_artifact_candidates": [],
        "ambiguous_documents": [],
        "automatic_artifact_selection": False,
    }

    if not database_path.is_file():
        return empty_result

    clauses = []
    parameters = []

    for field, value in filters.items():

        # field comes only from the fixed whitelist above.
        clauses.append(
            f"LOWER(TRIM(d.{field})) "
            "= LOWER(TRIM(?))"
        )

        parameters.append(
            value
        )

    where_clause = ""

    if clauses:
        where_clause = (
            " WHERE "
            + " AND ".join(clauses)
        )

    sql = (
        """
        SELECT
            a.vector_artifact_id,
            a.document_id,
            a.vector_store_filename,
            a.prepared_filename,
            a.prepared_sha256,
            a.vector_store_sha256,
            a.embedding_model,
            a.embedding_dimension,
            a.vector_count,
            a.embedding_created_at_utc,
            a.registered_at_utc,

            d.original_filename,
            d.stored_filename,
            d.source_sha256,

            d.document_family_id,
            d.supersedes_document_id,

            d.plant_id,
            d.department,
            d.equipment_id,
            d.equipment_type,
            d.manufacturer,
            d.model,

            d.document_type,
            d.revision,
            d.effective_date,
            d.document_status,
            d.access_level

        FROM document_vector_artifacts AS a

        INNER JOIN enterprise_documents AS d
            ON d.document_id = a.document_id
        """
        + where_clause
        +
        """
        ORDER BY
            d.document_id,
            a.registered_at_utc,
            a.vector_store_filename
        """
    )

    with closing(
        sqlite3.connect(database_path)
    ) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            sql,
            tuple(parameters),
        ).fetchall()

    artifacts = [
        dict(row)
        for row in rows
    ]

    grouped = {}

    for artifact in artifacts:

        document_id = artifact[
            "document_id"
        ]

        grouped.setdefault(
            document_id,
            [],
        ).append(
            artifact
        )

    single_artifact_candidates = []

    ambiguous_documents = []

    for document_id in sorted(grouped):

        document_artifacts = grouped[
            document_id
        ]

        if len(document_artifacts) == 1:

            single_artifact_candidates.append(
                document_artifacts[0]
            )

            continue

        ambiguous_documents.append(
            {
                "document_id":
                    document_id,

                "artifact_count":
                    len(document_artifacts),

                "vector_store_filenames": [
                    item[
                        "vector_store_filename"
                    ]
                    for item
                    in document_artifacts
                ],
            }
        )

    return {
        "metadata_filters":
            filters,

        "metadata_filter_applied":
            bool(filters),

        "documents_with_artifacts":
            len(grouped),

        "artifacts_count":
            len(artifacts),

        "candidate_artifacts":
            artifacts,

        "single_artifact_candidates":
            single_artifact_candidates,

        "ambiguous_documents":
            ambiguous_documents,

        "automatic_artifact_selection":
            False,
    }


def find_enterprise_documents_by_sha256(
    source_sha256: str,
    *,
    database_path: Path = REGISTRY_DATABASE,
) -> list[dict]:
    """
    Find documents having identical source bytes.

    A match is treated only as a possible duplicate.
    Nothing is deleted automatically.
    """
    fingerprint = _validate_sha256(
        source_sha256
    )

    database_path = Path(database_path)

    if not database_path.is_file():
        return []

    with closing(sqlite3.connect(database_path)) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT *
            FROM enterprise_documents
            WHERE source_sha256 = ?
            ORDER BY ingested_at_utc ASC
            """,
            (fingerprint,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def find_enterprise_documents_by_family(
    document_family_id: str,
    *,
    database_path: Path = REGISTRY_DATABASE,
) -> list[dict]:
    """
    Return all documents explicitly assigned to one document family.

    Revision ordering is not inferred from revision labels.
    """
    family_id = _clean_optional_text(document_family_id)

    if family_id is None:
        raise ValueError(
            "document_family_id must be a non-empty string."
        )

    database_path = Path(database_path)

    if not database_path.is_file():
        return []

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT *
            FROM enterprise_documents
            WHERE document_family_id = ?
            ORDER BY ingested_at_utc ASC
            """,
            (family_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def analyze_enterprise_document_relationship(
    document_information: dict,
    *,
    document_family_id: str | None = None,
    supersedes_document_id: str | None = None,
    database_path: Path = REGISTRY_DATABASE,
) -> dict:
    """
    Classify a new source against documents already in the registry.

    This is descriptive only:
    - files are never deleted automatically;
    - document status is never changed automatically;
    - revision ordering is never guessed from filenames or labels.
    """
    if not isinstance(document_information, dict):
        raise ValueError(
            "document_information must be a dictionary."
        )

    fingerprint = _validate_sha256(
        document_information.get("source_sha256")
    )

    family_id = _clean_optional_text(
        document_family_id
    )

    predecessor_id = _clean_optional_text(
        supersedes_document_id
    )

    exact_matches = find_enterprise_documents_by_sha256(
        fingerprint,
        database_path=database_path,
    )

    family_matches = (
        find_enterprise_documents_by_family(
            family_id,
            database_path=database_path,
        )
        if family_id is not None
        else []
    )

    predecessor = None

    if predecessor_id is not None:
        if family_id is None:
            raise ValueError(
                "document_family_id is required when "
                "supersedes_document_id is provided."
            )

        predecessor = get_enterprise_document(
            predecessor_id,
            database_path=database_path,
        )

        if predecessor is None:
            raise ValueError(
                "supersedes_document_id does not reference "
                "an existing registered document."
            )

        if predecessor.get("document_family_id") != family_id:
            raise ValueError(
                "The declared predecessor belongs to a "
                "different document family."
            )

    if exact_matches:
        classification = "exact_content_match"

    elif predecessor is not None:
        classification = "declared_revision_successor"

    elif family_matches:
        classification = "same_family_new_content"

    else:
        classification = "new_document"

    return {
        "classification": classification,

        "document_family_id": family_id,
        "supersedes_document_id": predecessor_id,

        "exact_content_match_count": len(
            exact_matches
        ),
        "exact_content_document_ids": [
            row["document_id"]
            for row in exact_matches
        ],

        "same_family_document_count": len(
            family_matches
        ),
        "same_family_document_ids": [
            row["document_id"]
            for row in family_matches
        ],

        "automatic_deletion": False,
        "automatic_status_change": False,
        "revision_order_inferred": False,
    }

