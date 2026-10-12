"""
Read-only PostgreSQL Registry V3 adapter.

The existing SQLite registry remains unchanged and active.

This adapter provides PostgreSQL-backed registry reads only.

It does not:
- register documents;
- register vector artifacts;
- select preferred/current artifacts;
- infer revision ordering;
- authorize access;
- modify document status;
- delete documents;
- open vector files;
- perform semantic retrieval.
"""

from __future__ import annotations

from collections import defaultdict
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.services.document_service import (
    REGISTRY_SCHEMA_VERSION,
    _clean_artifact_filename,
    _clean_optional_text,
    _normalize_enterprise_vector_discovery_filters,
    _validate_sha256,
)


DEFAULT_SECRET_FILE = (
    Path.home()
    / ".troubleshooting-assistant"
    / "postgres.local.env"
)


# ============================================================
# CONNECTION CONFIGURATION
# ============================================================

def _load_postgres_config(
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict:

    secret_file = Path(secret_file)

    if not secret_file.is_file():
        raise FileNotFoundError(
            f"PostgreSQL configuration file not found: {secret_file}"
        )

    config = {}

    for raw_line in secret_file.read_text(
        encoding="ascii"
    ).splitlines():

        line = raw_line.strip()

        if not line:
            continue

        if "=" not in line:
            raise ValueError(
                "Invalid PostgreSQL configuration line."
            )

        key, value = line.split("=", 1)

        config[key.strip()] = value


    required = (
        "TA_DB_HOST",
        "TA_DB_PORT",
        "TA_DB_NAME",
        "TA_DB_USER",
        "TA_DB_PASSWORD",
    )

    missing = [
        key
        for key in required
        if not config.get(key)
    ]

    if missing:
        raise ValueError(
            f"Missing PostgreSQL configuration fields: {missing}"
        )


    try:
        port = int(
            config["TA_DB_PORT"]
        )

    except ValueError as error:
        raise ValueError(
            "TA_DB_PORT must be an integer."
        ) from error


    if not 1 <= port <= 65535:
        raise ValueError(
            "TA_DB_PORT must be between 1 and 65535."
        )


    return {
        "host": config["TA_DB_HOST"],
        "port": port,
        "dbname": config["TA_DB_NAME"],
        "user": config["TA_DB_USER"],
        "password": config["TA_DB_PASSWORD"],
    }


def _connect(
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
):

    return psycopg.connect(
        **_load_postgres_config(
            secret_file
        ),
        row_factory=dict_row,
        connect_timeout=5,
    )


# ============================================================
# REGISTRY FOUNDATION VALIDATION
# ============================================================

def validate_postgres_registry_v3(
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict:

    if REGISTRY_SCHEMA_VERSION != 3:
        raise RuntimeError(
            "Application Registry V3 contract is not active."
        )


    with _connect(
        secret_file=secret_file
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                """
            )

            tables = {
                row["table_name"]
                for row in cursor.fetchall()
            }


            expected_tables = {
                "enterprise_documents",
                "document_vector_artifacts",
                "registry_metadata",
            }


            missing_tables = (
                expected_tables - tables
            )

            if missing_tables:
                raise RuntimeError(
                    "Missing PostgreSQL Registry V3 tables: "
                    f"{sorted(missing_tables)}"
                )


            cursor.execute(
                """
                SELECT value
                FROM registry_metadata
                WHERE key = %s
                """,
                (
                    "schema_version",
                ),
            )

            version = cursor.fetchone()

            if (
                version is None
                or version["value"] != "3"
            ):
                raise RuntimeError(
                    "PostgreSQL Registry schema_version is not 3."
                )


            cursor.execute(
                """
                SELECT
                    rolsuper,
                    rolcreatedb,
                    rolcreaterole,
                    rolreplication
                FROM pg_roles
                WHERE rolname = current_user
                """
            )

            role = cursor.fetchone()

            if role is None:
                raise RuntimeError(
                    "Current PostgreSQL role could not be inspected."
                )


            if (
                role["rolsuper"]
                or role["rolcreatedb"]
                or role["rolcreaterole"]
                or role["rolreplication"]
            ):
                raise RuntimeError(
                    "PostgreSQL registry is using an elevated role."
                )


    return {
        "schema_version": 3,
        "tables": sorted(
            expected_tables
        ),
        "application_role_superuser": False,
    }


# ============================================================
# DOCUMENT READ
# ============================================================

def get_enterprise_document(
    document_id: str,
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict | None:

    if not isinstance(
        document_id,
        str,
    ):
        raise ValueError(
            "document_id must be a non-empty string."
        )

    document_id = (
        document_id.strip()
    )

    if not document_id:
        raise ValueError(
            "document_id must be a non-empty string."
        )


    with _connect(
        secret_file=secret_file
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM enterprise_documents
                WHERE document_id = %s
                """,
                (
                    document_id,
                ),
            )

            row = cursor.fetchone()


    return (
        dict(row)
        if row is not None
        else None
    )


# ============================================================
# VECTOR ARTIFACT READ
# ============================================================

def get_document_vector_artifact(
    vector_store_filename: str,
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict | None:

    vector_store_filename = (
        _clean_artifact_filename(
            vector_store_filename,
            field_name="vector_store_filename",
            suffix=".npz",
        )
    )


    with _connect(
        secret_file=secret_file
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM document_vector_artifacts
                WHERE vector_store_filename = %s
                """,
                (
                    vector_store_filename,
                ),
            )

            row = cursor.fetchone()


    return (
        dict(row)
        if row is not None
        else None
    )


# ============================================================
# ALL ARTIFACTS FOR ONE DOCUMENT
# ============================================================

def find_document_vector_artifacts(
    document_id: str,
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> list[dict]:

    if not isinstance(
        document_id,
        str,
    ):
        raise ValueError(
            "document_id must be a non-empty string."
        )

    document_id = (
        document_id.strip()
    )

    if not document_id:
        raise ValueError(
            "document_id must be a non-empty string."
        )


    with _connect(
        secret_file=secret_file
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM document_vector_artifacts
                WHERE document_id = %s
                ORDER BY
                    registered_at_utc,
                    vector_store_filename
                """,
                (
                    document_id,
                ),
            )

            rows = cursor.fetchall()


    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# SHA LOOKUP
# ============================================================

def find_enterprise_documents_by_sha256(
    source_sha256: str,
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> list[dict]:

    fingerprint = (
        _validate_sha256(
            source_sha256
        )
    )


    with _connect(
        secret_file=secret_file
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM enterprise_documents
                WHERE source_sha256 = %s
                ORDER BY ingested_at_utc ASC
                """,
                (
                    fingerprint,
                ),
            )

            rows = cursor.fetchall()


    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# FAMILY LOOKUP
# ============================================================

def find_enterprise_documents_by_family(
    document_family_id: str,
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> list[dict]:

    family_id = (
        _clean_optional_text(
            document_family_id
        )
    )

    if family_id is None:
        raise ValueError(
            "document_family_id must be a non-empty string."
        )


    with _connect(
        secret_file=secret_file
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM enterprise_documents
                WHERE document_family_id = %s
                ORDER BY ingested_at_utc ASC
                """,
                (
                    family_id,
                ),
            )

            rows = cursor.fetchall()


    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# ENTERPRISE ARTIFACT DISCOVERY
# ============================================================

def discover_enterprise_vector_artifacts(
    metadata_filters=None,
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict:

    filters = (
        _normalize_enterprise_vector_discovery_filters(
            metadata_filters
        )
    )


    empty_result = {
        "metadata_filters":
            filters,

        "metadata_filter_applied":
            bool(filters),

        "documents_with_artifacts":
            0,

        "artifacts_count":
            0,

        "candidate_artifacts":
            [],

        "single_artifact_candidates":
            [],

        "ambiguous_documents":
            [],

        "automatic_artifact_selection":
            False,
    }


    clauses = []
    parameters = []


    for field, value in filters.items():

        # `field` originates only from the fixed
        # document_service metadata whitelist.
        clauses.append(
            f"LOWER(TRIM(d.{field})) "
            "= LOWER(TRIM(%s))"
        )

        parameters.append(
            value
        )


    where_clause = ""

    if clauses:
        where_clause = (
            " WHERE "
            + " AND ".join(
                clauses
            )
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


    with _connect(
        secret_file=secret_file
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                sql,
                tuple(parameters),
            )

            rows = cursor.fetchall()


    artifacts = [
        dict(row)
        for row in rows
    ]


    if not artifacts:
        return empty_result


    grouped = defaultdict(
        list
    )


    for artifact in artifacts:

        grouped[
            artifact["document_id"]
        ].append(
            artifact
        )


    single_artifact_candidates = []
    ambiguous_documents = []


    for document_id in sorted(
        grouped
    ):

        document_artifacts = (
            grouped[document_id]
        )

        if len(
            document_artifacts
        ) == 1:

            single_artifact_candidates.append(
                document_artifacts[0]
            )

            continue


        ambiguous_documents.append(
            {
                "document_id":
                    document_id,

                "artifact_count":
                    len(
                        document_artifacts
                    ),

                "vector_store_filenames":
                    [
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


# ============================================================
# RELATIONSHIP ANALYSIS
# ============================================================

def analyze_enterprise_document_relationship(
    document_information: dict,
    *,
    document_family_id: str | None = None,
    supersedes_document_id: str | None = None,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict:

    if not isinstance(
        document_information,
        dict,
    ):
        raise ValueError(
            "document_information must be a dictionary."
        )


    fingerprint = (
        _validate_sha256(
            document_information.get(
                "source_sha256"
            )
        )
    )


    family_id = (
        _clean_optional_text(
            document_family_id
        )
    )


    predecessor_id = (
        _clean_optional_text(
            supersedes_document_id
        )
    )


    exact_matches = (
        find_enterprise_documents_by_sha256(
            fingerprint,
            secret_file=secret_file,
        )
    )


    family_matches = (
        find_enterprise_documents_by_family(
            family_id,
            secret_file=secret_file,
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


        predecessor = (
            get_enterprise_document(
                predecessor_id,
                secret_file=secret_file,
            )
        )


        if predecessor is None:
            raise ValueError(
                "supersedes_document_id does not reference "
                "an existing registered document."
            )


        if (
            predecessor.get(
                "document_family_id"
            )
            != family_id
        ):
            raise ValueError(
                "The declared predecessor belongs to a "
                "different document family."
            )


    if exact_matches:

        classification = (
            "exact_content_match"
        )

    elif predecessor is not None:

        classification = (
            "declared_revision_successor"
        )

    elif family_matches:

        classification = (
            "same_family_new_content"
        )

    else:

        classification = (
            "new_document"
        )


    return {
        "classification":
            classification,

        "document_family_id":
            family_id,

        "supersedes_document_id":
            predecessor_id,

        "exact_content_match_count":
            len(
                exact_matches
            ),

        "exact_content_document_ids":
            [
                row["document_id"]
                for row
                in exact_matches
            ],

        "same_family_document_count":
            len(
                family_matches
            ),

        "same_family_document_ids":
            [
                row["document_id"]
                for row
                in family_matches
            ],

        "automatic_deletion":
            False,

        "automatic_status_change":
            False,

        "revision_order_inferred":
            False,
    }



# ============================================================
# POSTGRESQL WRITE VALIDATION BRIDGE
# ============================================================

def _seed_temporary_sqlite_document(
    database_path: Path,
    document: dict,
) -> None:
    """
    Seed one existing PostgreSQL document into a temporary
    SQLite Registry V3 used only for validation.

    The live SQLite registry is never used by this helper.
    """
    from app.services import document_service

    document_service.initialize_document_registry(
        database_path=database_path
    )

    fields = (
        "document_id",
        "original_filename",
        "stored_filename",
        "file_type",
        "file_size_bytes",
        "source_sha256",
        "document_family_id",
        "supersedes_document_id",
        "plant_id",
        "department",
        "equipment_id",
        "equipment_type",
        "manufacturer",
        "model",
        "document_type",
        "revision",
        "effective_date",
        "document_status",
        "access_level",
        "ingested_at_utc",
        "metadata_updated_at_utc",
    )

    values = tuple(
        document.get(field)
        for field in fields
    )

    with closing(
        sqlite3.connect(
            database_path
        )
    ) as connection:

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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            values,
        )

        connection.commit()


def _prepare_postgres_document_row(
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
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict:
    """
    Reuse the validated SQLite Registry V3 normalization rules
    without touching data/document_registry.sqlite3.

    A temporary SQLite database exists only for the duration of
    this validation call.
    """
    from app.services import document_service

    predecessor = None

    cleaned_predecessor_id = (
        _clean_optional_text(
            supersedes_document_id
        )
    )

    if cleaned_predecessor_id is not None:

        predecessor = (
            get_enterprise_document(
                cleaned_predecessor_id,
                secret_file=secret_file,
            )
        )

        if predecessor is None:
            raise ValueError(
                "supersedes_document_id does not reference "
                "an existing registered document."
            )


    with tempfile.TemporaryDirectory() as temp_name:

        temporary_registry = (
            Path(temp_name)
            / "document_validation.sqlite3"
        )

        document_service.initialize_document_registry(
            database_path=temporary_registry
        )

        if predecessor is not None:

            _seed_temporary_sqlite_document(
                temporary_registry,
                predecessor,
            )


        validated = (
            document_service
            .register_enterprise_document(
                document_information,
                plant_id=plant_id,
                department=department,
                equipment_id=equipment_id,
                equipment_type=equipment_type,
                manufacturer=manufacturer,
                model=model,
                document_family_id=document_family_id,
                supersedes_document_id=supersedes_document_id,
                document_type=document_type,
                revision=revision,
                effective_date=effective_date,
                document_status=document_status,
                access_level=access_level,
                database_path=temporary_registry,
            )
        )

    return validated


def _prepare_postgres_artifact_row(
    artifact_information: dict,
    *,
    document: dict,
) -> dict:
    """
    Reuse the existing Registry V3 artifact validation rules
    using a temporary SQLite database.

    No live SQLite registry is created.
    """
    from app.services import document_service

    if not isinstance(
        document,
        dict,
    ):
        raise ValueError(
            "document must be a validated registry row."
        )


    with tempfile.TemporaryDirectory() as temp_name:

        temporary_registry = (
            Path(temp_name)
            / "artifact_validation.sqlite3"
        )

        document_service.initialize_document_registry(
            database_path=temporary_registry
        )

        _seed_temporary_sqlite_document(
            temporary_registry,
            document,
        )

        validated = (
            document_service
            .register_document_vector_artifact(
                artifact_information,
                database_path=temporary_registry,
            )
        )

    return validated


# ============================================================
# LOW-LEVEL POSTGRESQL WRITE FUNCTIONS
# ============================================================

def _insert_enterprise_document(
    connection,
    document: dict,
) -> dict:
    """
    Insert one already validated enterprise document into the
    supplied PostgreSQL transaction.

    This helper does not commit.
    """
    try:

        with connection.cursor() as cursor:

            cursor.execute(
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
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    document["document_id"],
                    document["original_filename"],
                    document["stored_filename"],
                    document["file_type"],
                    document["file_size_bytes"],
                    document["source_sha256"],
                    document["document_family_id"],
                    document["supersedes_document_id"],
                    document["plant_id"],
                    document["department"],
                    document["equipment_id"],
                    document["equipment_type"],
                    document["manufacturer"],
                    document["model"],
                    document["document_type"],
                    document["revision"],
                    document["effective_date"],
                    document["document_status"],
                    document["access_level"],
                    document["ingested_at_utc"],
                    document["metadata_updated_at_utc"],
                ),
            )

            row = cursor.fetchone()

    except psycopg.errors.UniqueViolation as error:

        raise ValueError(
            "An enterprise document with the same "
            "document_id or stored_filename already exists."
        ) from error


    if row is None:
        raise RuntimeError(
            "PostgreSQL document registration succeeded "
            "but the record could not be read back."
        )

    return dict(row)


def _insert_document_vector_artifact(
    connection,
    artifact: dict,
) -> dict:
    """
    Insert one already validated vector artifact into the
    supplied PostgreSQL transaction.

    This helper does not commit.
    """
    try:

        with connection.cursor() as cursor:

            cursor.execute(
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
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    artifact["vector_artifact_id"],
                    artifact["document_id"],
                    artifact["vector_store_filename"],
                    artifact["prepared_filename"],
                    artifact["prepared_sha256"],
                    artifact["vector_store_sha256"],
                    artifact["embedding_model"],
                    artifact["embedding_dimension"],
                    artifact["vector_count"],
                    artifact["embedding_created_at_utc"],
                    artifact["registered_at_utc"],
                ),
            )

            row = cursor.fetchone()

    except psycopg.errors.UniqueViolation as error:

        raise ValueError(
            "A vector artifact with the same "
            "vector_store_filename or artifact identity "
            "already exists."
        ) from error

    except psycopg.errors.ForeignKeyViolation as error:

        raise ValueError(
            "Vector artifacts may be registered only for "
            "an existing enterprise document."
        ) from error


    if row is None:
        raise RuntimeError(
            "PostgreSQL vector artifact registration succeeded "
            "but the record could not be read back."
        )

    return dict(row)


# ============================================================
# PUBLIC POSTGRESQL DOCUMENT REGISTRATION
# ============================================================

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
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict:
    """
    Register one enterprise document in PostgreSQL Registry V3.

    Missing metadata is never inferred.
    Existing documents are never modified automatically.
    """
    validated = (
        _prepare_postgres_document_row(
            document_information,
            plant_id=plant_id,
            department=department,
            equipment_id=equipment_id,
            equipment_type=equipment_type,
            manufacturer=manufacturer,
            model=model,
            document_family_id=document_family_id,
            supersedes_document_id=supersedes_document_id,
            document_type=document_type,
            revision=revision,
            effective_date=effective_date,
            document_status=document_status,
            access_level=access_level,
            secret_file=secret_file,
        )
    )


    connection = _connect(
        secret_file=secret_file
    )

    try:

        result = _insert_enterprise_document(
            connection,
            validated,
        )

        connection.commit()

        return result

    except BaseException:

        connection.rollback()
        raise

    finally:

        connection.close()


# ============================================================
# PUBLIC POSTGRESQL VECTOR ARTIFACT REGISTRATION
# ============================================================

def register_document_vector_artifact(
    artifact_information: dict,
    *,
    secret_file: Path = DEFAULT_SECRET_FILE,
) -> dict:
    """
    Register one vector artifact in PostgreSQL Registry V3.

    Multiple vector artifacts may reference the same document.

    This operation does not declare any artifact current,
    preferred, approved, or authorized for retrieval.
    """
    if not isinstance(
        artifact_information,
        dict,
    ):
        raise ValueError(
            "artifact_information must be a dictionary."
        )


    document_id = artifact_information.get(
        "document_id"
    )

    if not isinstance(
        document_id,
        str,
    ):
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
        secret_file=secret_file,
    )

    if document is None:
        raise ValueError(
            "Vector artifacts may be registered only for "
            "an existing enterprise document."
        )


    validated = (
        _prepare_postgres_artifact_row(
            artifact_information,
            document=document,
        )
    )


    connection = _connect(
        secret_file=secret_file
    )

    try:

        result = (
            _insert_document_vector_artifact(
                connection,
                validated,
            )
        )

        connection.commit()

        return result

    except BaseException:

        connection.rollback()
        raise

    finally:

        connection.close()
