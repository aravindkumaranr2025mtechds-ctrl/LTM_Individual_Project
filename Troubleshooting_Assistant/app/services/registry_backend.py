"""
Trusted Registry V3 backend selector.

Backend selection is process configuration, never request data.

Supported values:

    TA_REGISTRY_BACKEND=sqlite
    TA_REGISTRY_BACKEND=postgres

Migration safety rules:

- default backend remains SQLite;
- explicit database_path always means SQLite;
- unknown backend values fail closed;
- PostgreSQL failure never silently falls back to SQLite;
- backend selection is never inferred from file existence;
- backend selection is never inferred from Docker availability;
- callers cannot provide PostgreSQL credentials through this API.
"""

from __future__ import annotations

import os

from pathlib import Path

from app.services import (
    document_service,
    postgres_registry,
)


REGISTRY_BACKEND_ENV = (
    "TA_REGISTRY_BACKEND"
)

SQLITE_BACKEND = "sqlite"
POSTGRES_BACKEND = "postgres"

DEFAULT_REGISTRY_BACKEND = (
    SQLITE_BACKEND
)

ALLOWED_REGISTRY_BACKENDS = frozenset(
    {
        SQLITE_BACKEND,
        POSTGRES_BACKEND,
    }
)


# Preserve these existing public constants for integration code.
REGISTRY_DATABASE = (
    document_service
    .REGISTRY_DATABASE
)

REGISTRY_SCHEMA_VERSION = (
    document_service
    .REGISTRY_SCHEMA_VERSION
)


def _configured_registry_backend() -> str:
    """
    Read and validate the trusted process-level backend setting.

    Missing configuration intentionally defaults to SQLite during
    migration.
    """
    raw_value = os.environ.get(
        REGISTRY_BACKEND_ENV,
        DEFAULT_REGISTRY_BACKEND,
    )

    if not isinstance(
        raw_value,
        str,
    ):
        raise RuntimeError(
            "Registry backend configuration must be a string."
        )

    backend = (
        raw_value
        .strip()
        .casefold()
    )

    if backend not in ALLOWED_REGISTRY_BACKENDS:
        raise RuntimeError(
            "Invalid TA_REGISTRY_BACKEND value. "
            "Allowed values are: sqlite, postgres."
        )

    return backend


def get_active_registry_backend(
    *,
    database_path: Path | str | None = None,
) -> str:
    """
    Resolve which Registry V3 implementation should handle a call.

    An explicit database_path always selects SQLite. This preserves
    temporary SQLite databases used by unit tests and controlled
    inspection workflows.

    Otherwise, selection comes only from TA_REGISTRY_BACKEND.
    """
    if database_path is not None:
        return SQLITE_BACKEND

    return _configured_registry_backend()


def _sqlite_database_path(
    database_path: Path | str | None,
) -> Path:
    """
    Resolve the SQLite path for SQLite-backed operations.
    """
    if database_path is None:
        return Path(
            REGISTRY_DATABASE
        )

    return Path(
        database_path
    )


def initialize_document_registry(
    database_path: Path | str | None = None,
):
    """
    Validate or initialize the configured Registry V3 backend.

    PostgreSQL schema creation is intentionally not performed here.
    PostgreSQL must already contain the validated Registry V3 schema.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .initialize_document_registry(
                _sqlite_database_path(
                    database_path
                )
            )
        )

    return (
        postgres_registry
        .validate_postgres_registry_v3()
    )


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
    database_path: Path | str | None = None,
) -> dict:
    """
    Register one document using the trusted active backend.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    common_arguments = {
        "plant_id":
            plant_id,

        "department":
            department,

        "equipment_id":
            equipment_id,

        "equipment_type":
            equipment_type,

        "manufacturer":
            manufacturer,

        "model":
            model,

        "document_family_id":
            document_family_id,

        "supersedes_document_id":
            supersedes_document_id,

        "document_type":
            document_type,

        "revision":
            revision,

        "effective_date":
            effective_date,

        "document_status":
            document_status,

        "access_level":
            access_level,
    }

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .register_enterprise_document(
                document_information,
                **common_arguments,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .register_enterprise_document(
            document_information,
            **common_arguments,
        )
    )


def get_enterprise_document(
    document_id: str,
    *,
    database_path: Path | str | None = None,
) -> dict | None:
    """
    Read one enterprise document from the active backend.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .get_enterprise_document(
                document_id,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .get_enterprise_document(
            document_id
        )
    )


def register_document_vector_artifact(
    artifact_information: dict,
    *,
    database_path: Path | str | None = None,
) -> dict:
    """
    Register one vector artifact using the active backend.

    This does not mark the artifact current, preferred, approved,
    active, or authorized.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .register_document_vector_artifact(
                artifact_information,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .register_document_vector_artifact(
            artifact_information
        )
    )


def get_document_vector_artifact(
    vector_store_filename: str,
    *,
    database_path: Path | str | None = None,
) -> dict | None:
    """
    Read one exact vector artifact from the active backend.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .get_document_vector_artifact(
                vector_store_filename,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .get_document_vector_artifact(
            vector_store_filename
        )
    )


def find_document_vector_artifacts(
    document_id: str,
    *,
    database_path: Path | str | None = None,
) -> list[dict]:
    """
    Return every artifact registered for one document.

    Ordering never implies preference or approval.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .find_document_vector_artifacts(
                document_id,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .find_document_vector_artifacts(
            document_id
        )
    )


def discover_enterprise_vector_artifacts(
    metadata_filters=None,
    *,
    database_path: Path | str | None = None,
) -> dict:
    """
    Discover registered vector artifacts without selecting one
    automatically.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .discover_enterprise_vector_artifacts(
                metadata_filters,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .discover_enterprise_vector_artifacts(
            metadata_filters
        )
    )


def find_enterprise_documents_by_sha256(
    source_sha256: str,
    *,
    database_path: Path | str | None = None,
) -> list[dict]:
    """
    Find identical source fingerprints.

    Matching is descriptive only and never causes deletion.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .find_enterprise_documents_by_sha256(
                source_sha256,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .find_enterprise_documents_by_sha256(
            source_sha256
        )
    )


def find_enterprise_documents_by_family(
    document_family_id: str,
    *,
    database_path: Path | str | None = None,
) -> list[dict]:
    """
    Find explicitly declared members of one document family.

    Revision order is never inferred from filenames or labels.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .find_enterprise_documents_by_family(
                document_family_id,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .find_enterprise_documents_by_family(
            document_family_id
        )
    )


def analyze_enterprise_document_relationship(
    document_information: dict,
    *,
    document_family_id: str | None = None,
    supersedes_document_id: str | None = None,
    database_path: Path | str | None = None,
) -> dict:
    """
    Describe a source relationship using the active backend.

    No deletion, status change, or revision inference is performed.
    """
    backend = (
        get_active_registry_backend(
            database_path=database_path,
        )
    )

    if backend == SQLITE_BACKEND:

        return (
            document_service
            .analyze_enterprise_document_relationship(
                document_information,
                document_family_id=
                    document_family_id,
                supersedes_document_id=
                    supersedes_document_id,
                database_path=
                    _sqlite_database_path(
                        database_path
                    ),
            )
        )

    return (
        postgres_registry
        .analyze_enterprise_document_relationship(
            document_information,
            document_family_id=
                document_family_id,
            supersedes_document_id=
                supersedes_document_id,
        )
    )
