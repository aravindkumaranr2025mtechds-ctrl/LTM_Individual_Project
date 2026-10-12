"""
Import one explicitly registered NPZ vector artifact into Qdrant.

The Registry remains authoritative for document and artifact identity.
Qdrant receives only vectors that have passed existing NPZ validation
and Registry provenance checks.

No artifact is selected automatically.
No embedding model is executed here.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from qdrant_client import QdrantClient

from app.services import (
    qdrant_store,
    registry_backend,
    retrieval_service,
)


def _clean_nonempty_text(
    value,
    *,
    field_name,
    max_length=512,
):
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a non-empty string."
        )

    cleaned = value.strip()

    if not cleaned:
        raise ValueError(
            f"{field_name} must be a non-empty string."
        )

    if len(cleaned) > max_length:
        raise ValueError(
            f"{field_name} exceeds {max_length} characters."
        )

    return cleaned


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def _registered_artifact_by_id(
    *,
    document_id,
    vector_artifact_id,
    database_path=None,
):
    artifacts = (
        registry_backend
        .find_document_vector_artifacts(
            document_id,
            database_path=database_path,
        )
    )

    matches = [
        artifact
        for artifact in artifacts
        if artifact.get("vector_artifact_id")
        == vector_artifact_id
    ]

    if not matches:
        raise ValueError(
            "The supplied vector_artifact_id is not "
            "registered for the supplied document_id."
        )

    if len(matches) != 1:
        raise RuntimeError(
            "Registry returned duplicate artifact identities."
        )

    return matches[0]


def import_registered_npz_artifact(
    client,
    *,
    document_id,
    vector_artifact_id,
    collection_name=qdrant_store.DEFAULT_COLLECTION_NAME,
    database_path=None,
):
    """
    Import exactly one Registry artifact into Qdrant.

    Both document_id and vector_artifact_id must be supplied.
    No preferred/current artifact is inferred.
    """

    if not isinstance(client, QdrantClient):
        raise TypeError(
            "client must be a QdrantClient."
        )

    document_id = _clean_nonempty_text(
        document_id,
        field_name="document_id",
    )

    vector_artifact_id = _clean_nonempty_text(
        vector_artifact_id,
        field_name="vector_artifact_id",
    )

    registered_document = (
        registry_backend
        .get_enterprise_document(
            document_id,
            database_path=database_path,
        )
    )

    if registered_document is None:
        raise ValueError(
            "document_id is not registered."
        )

    artifact = _registered_artifact_by_id(
        document_id=document_id,
        vector_artifact_id=vector_artifact_id,
        database_path=database_path,
    )

    if artifact.get("document_id") != document_id:
        raise RuntimeError(
            "Registry artifact/document identity mismatch."
        )

    vector_store_filename = artifact.get(
        "vector_store_filename"
    )

    if not isinstance(vector_store_filename, str):
        raise ValueError(
            "Registered artifact lacks vector_store_filename."
        )

    vector_directory = Path(
        retrieval_service.VECTOR_DIRECTORY
    ).resolve()

    vector_path = (
        vector_directory
        / vector_store_filename
    ).resolve()

    if vector_path.parent != vector_directory:
        raise ValueError(
            "Registered vector artifact escapes "
            "the vector-store directory."
        )

    if vector_path.suffix.lower() != ".npz":
        raise ValueError(
            "Registered vector artifact must be an NPZ file."
        )

    if not vector_path.is_file():
        raise FileNotFoundError(
            "Registered vector artifact file is missing."
        )

    actual_vector_sha256 = _sha256_file(
        vector_path
    )

    expected_vector_sha256 = artifact.get(
        "vector_store_sha256"
    )

    if actual_vector_sha256 != expected_vector_sha256:
        raise ValueError(
            "Vector-store SHA-256 differs from "
            "the registered artifact fingerprint."
        )

    vectors, metadata, parents = (
        retrieval_service
        .load_vector_store(
            vector_store_filename
        )
    )

    if not isinstance(metadata, dict):
        raise RuntimeError(
            "Validated vector metadata is invalid."
        )

    if metadata.get("document_id") != document_id:
        raise ValueError(
            "Vector metadata document_id differs "
            "from the Registry document."
        )

    if (
        metadata.get("source_filename")
        != registered_document.get("stored_filename")
    ):
        raise ValueError(
            "Vector source_filename differs from "
            "the registered stored_filename."
        )

    if (
        metadata.get("source_sha256")
        != registered_document.get("source_sha256")
    ):
        raise ValueError(
            "Vector source SHA-256 differs from "
            "the registered source document."
        )

    embedding = metadata.get(
        "embedding"
    )

    if not isinstance(embedding, dict):
        raise ValueError(
            "Vector metadata lacks embedding provenance."
        )

    checks = (
        (
            "prepared_filename",
            embedding.get("prepared_filename"),
            artifact.get("prepared_filename"),
        ),
        (
            "prepared_sha256",
            embedding.get("prepared_sha256"),
            artifact.get("prepared_sha256"),
        ),
        (
            "embedding_model",
            embedding.get("model_name"),
            artifact.get("embedding_model"),
        ),
        (
            "embedding_dimension",
            embedding.get("embedding_dimension"),
            artifact.get("embedding_dimension"),
        ),
        (
            "embedding_created_at_utc",
            embedding.get("created_at_utc"),
            artifact.get("embedding_created_at_utc"),
        ),
    )

    for field, actual, expected in checks:
        if actual != expected:
            raise ValueError(
                f"Vector metadata {field} differs "
                "from the registered artifact."
            )

    if embedding.get("normalized") is not True:
        raise ValueError(
            "Registered vector artifact must contain "
            "normalized embeddings."
        )

    if (
        artifact.get("embedding_dimension")
        != qdrant_store.VECTOR_SIZE
    ):
        raise ValueError(
            "Registered embedding dimension does not "
            "match the Qdrant collection contract."
        )

    vector_count = artifact.get(
        "vector_count"
    )

    if (
        type(vector_count) is not int
        or vector_count <= 0
    ):
        raise ValueError(
            "Registered vector_count is invalid."
        )

    if vectors.shape != (
        vector_count,
        qdrant_store.VECTOR_SIZE,
    ):
        raise ValueError(
            "Validated vectors do not match the "
            "registered vector_count/dimension."
        )

    if metadata.get("total_chunks") != vector_count:
        raise ValueError(
            "Vector metadata total_chunks differs "
            "from registered vector_count."
        )

    chunks = metadata.get(
        "chunks"
    )

    if (
        not isinstance(chunks, list)
        or len(chunks) != vector_count
    ):
        raise ValueError(
            "Validated chunk metadata does not match "
            "registered vector_count."
        )

    ordered_chunk_ids = []

    for expected_index, chunk in enumerate(
        chunks
    ):
        if not isinstance(chunk, dict):
            raise ValueError(
                "Validated chunk metadata is invalid."
            )

        if (
            chunk.get("vector_index")
            != expected_index
        ):
            raise ValueError(
                "Validated chunk vector_index ordering changed."
            )

        chunk_id = _clean_nonempty_text(
            chunk.get("chunk_id"),
            field_name="chunk_id",
        )

        ordered_chunk_ids.append(
            chunk_id
        )

    if (
        len(set(ordered_chunk_ids))
        != len(ordered_chunk_ids)
    ):
        raise ValueError(
            "Validated chunk IDs are not unique."
        )

    qdrant_result = (
        qdrant_store
        .upsert_artifact_vectors(
            client,
            vector_artifact_id=vector_artifact_id,
            document_id=document_id,
            chunk_ids=ordered_chunk_ids,
            vectors=vectors,
            collection_name=collection_name,
        )
    )

    return {
        "document_id":
            document_id,

        "vector_artifact_id":
            vector_artifact_id,

        "collection_name":
            qdrant_result["collection_name"],

        "points_count":
            qdrant_result["points_count"],

        "source_sha256_verified":
            True,

        "vector_store_sha256_verified":
            True,

        "prepared_sha256_verified":
            True,

        "embedding_contract_verified":
            True,

        "validated_parent_count":
            len(parents),

        "automatic_artifact_selection":
            False,

        "authorization_enforced":
            False,

        "message": (
            "One explicitly registered and validated "
            "vector artifact was indexed into Qdrant."
        ),
    }


def create_legacy_source_attested_vector_copy(
    vector_store_filename,
    *,
    output_filename=None,
):
    """
    Create a new provenance-attested copy of one validated legacy NPZ.

    This migration is intentionally non-destructive.

    It does not:
    - overwrite the legacy NPZ,
    - modify vectors,
    - regenerate embeddings,
    - infer document identity,
    - infer revision preference,
    - register anything automatically.

    The migration establishes missing raw-source provenance by:
    1. validating the existing NPZ through retrieval_service;
    2. locating the exact raw source_filename;
    3. hashing the raw source bytes;
    4. validating the exact prepared JSON against prepared_sha256;
    5. verifying prepared/NPZ document and filename identity;
    6. writing a new NPZ with identical vectors/chunks plus
       source_sha256 and source_size_bytes.
    """

    import json

    import numpy as np


    vector_store_filename = _clean_nonempty_text(
        vector_store_filename,
        field_name="vector_store_filename",
    )


    if (
        any(
            character in vector_store_filename
            for character in "/\\:\x00"
        )
        or Path(
            vector_store_filename
        ).suffix.lower()
        != ".npz"
    ):
        raise ValueError(
            "Provide only an NPZ filename inside vector_store."
        )


    vector_directory = Path(
        retrieval_service.VECTOR_DIRECTORY
    ).resolve()


    source_vector_path = (
        vector_directory
        / vector_store_filename
    ).resolve()


    if (
        source_vector_path.parent
        != vector_directory
    ):
        raise ValueError(
            "Legacy vector artifact escapes vector_store."
        )


    if not source_vector_path.is_file():
        raise FileNotFoundError(
            "Legacy vector artifact was not found."
        )


    vectors, metadata, parents = (
        retrieval_service
        .load_vector_store(
            vector_store_filename
        )
    )


    if not isinstance(
        metadata,
        dict,
    ):
        raise RuntimeError(
            "Validated vector metadata is invalid."
        )


    existing_source_sha = (
        metadata.get(
            "source_sha256"
        )
    )


    if existing_source_sha is not None:
        raise ValueError(
            "Vector artifact already contains source_sha256; "
            "legacy provenance migration is not applicable."
        )


    document_id = _clean_nonempty_text(
        metadata.get(
            "document_id"
        ),
        field_name="document_id",
    )


    source_filename = _clean_nonempty_text(
        metadata.get(
            "source_filename"
        ),
        field_name="source_filename",
    )


    if (
        any(
            character in source_filename
            for character in "/\\:\x00"
        )
        or Path(
            source_filename
        ).suffix.lower()
        != ".pdf"
    ):
        raise ValueError(
            "Legacy source_filename must be a PDF filename."
        )


    data_directory = (
        vector_directory.parent
    )


    raw_directory = (
        data_directory
        / "raw_documents"
    ).resolve()


    raw_source_path = (
        raw_directory
        / source_filename
    ).resolve()


    if (
        raw_source_path.parent
        != raw_directory
    ):
        raise ValueError(
            "Raw source escapes raw_documents."
        )


    if not raw_source_path.is_file():
        raise FileNotFoundError(
            "Exact raw source PDF was not found."
        )


    raw_source_sha256 = (
        _sha256_file(
            raw_source_path
        )
    )


    raw_source_size_bytes = (
        raw_source_path
        .stat()
        .st_size
    )


    if raw_source_size_bytes <= 0:
        raise ValueError(
            "Raw source PDF is empty."
        )


    embedding = (
        metadata.get(
            "embedding"
        )
    )


    if not isinstance(
        embedding,
        dict,
    ):
        raise ValueError(
            "Legacy vector metadata lacks embedding provenance."
        )


    prepared_filename = _clean_nonempty_text(
        embedding.get(
            "prepared_filename"
        ),
        field_name="prepared_filename",
    )


    if (
        any(
            character in prepared_filename
            for character in "/\\:\x00"
        )
        or Path(
            prepared_filename
        ).suffix.lower()
        != ".json"
    ):
        raise ValueError(
            "prepared_filename must be a JSON filename."
        )


    expected_prepared_sha256 = (
        embedding.get(
            "prepared_sha256"
        )
    )


    if (
        not isinstance(
            expected_prepared_sha256,
            str,
        )
        or len(
            expected_prepared_sha256
        )
        != 64
    ):
        raise ValueError(
            "Legacy embedding metadata has invalid prepared_sha256."
        )


    prepared_directory = (
        data_directory
        / "embedding_documents"
    ).resolve()


    prepared_path = (
        prepared_directory
        / prepared_filename
    ).resolve()


    if (
        prepared_path.parent
        != prepared_directory
    ):
        raise ValueError(
            "Prepared artifact escapes embedding_documents."
        )


    if not prepared_path.is_file():
        raise FileNotFoundError(
            "Exact prepared JSON was not found."
        )


    actual_prepared_sha256 = (
        _sha256_file(
            prepared_path
        )
    )


    if (
        actual_prepared_sha256
        != expected_prepared_sha256
    ):
        raise ValueError(
            "Prepared JSON SHA-256 differs from "
            "the legacy vector artifact provenance."
        )


    try:

        prepared_document = json.loads(
            prepared_path
            .read_bytes()
        )

    except Exception as error:

        raise ValueError(
            "Prepared JSON could not be parsed."
        ) from error


    if not isinstance(
        prepared_document,
        dict,
    ):
        raise ValueError(
            "Prepared document must be a JSON object."
        )


    if (
        prepared_document.get(
            "document_id"
        )
        != document_id
    ):
        raise ValueError(
            "Prepared document_id differs from vector metadata."
        )


    if (
        prepared_document.get(
            "source_filename"
        )
        != source_filename
    ):
        raise ValueError(
            "Prepared source_filename differs from vector metadata."
        )


    prepared_source_sha = (
        prepared_document.get(
            "source_sha256"
        )
    )


    if (
        prepared_source_sha is not None
        and prepared_source_sha
        != raw_source_sha256
    ):
        raise ValueError(
            "Prepared source_sha256 conflicts with "
            "the actual raw source bytes."
        )


    chunks = (
        metadata.get(
            "chunks"
        )
    )


    if (
        not isinstance(
            chunks,
            list,
        )
        or len(chunks)
        != vectors.shape[0]
    ):
        raise ValueError(
            "Validated legacy chunk metadata is inconsistent."
        )


    ordered_chunk_ids = []


    for expected_index, chunk in enumerate(
        chunks
    ):

        if not isinstance(
            chunk,
            dict,
        ):
            raise ValueError(
                "Legacy chunk metadata is invalid."
            )


        if (
            chunk.get(
                "vector_index"
            )
            != expected_index
        ):
            raise ValueError(
                "Legacy vector_index ordering changed."
            )


        if (
            chunk.get(
                "document_id"
            )
            != document_id
        ):
            raise ValueError(
                "Legacy chunk document identity mismatch."
            )


        if (
            chunk.get(
                "source_filename"
            )
            != source_filename
        ):
            raise ValueError(
                "Legacy chunk source identity mismatch."
            )


        chunk_id = _clean_nonempty_text(
            chunk.get(
                "chunk_id"
            ),
            field_name="chunk_id",
        )


        ordered_chunk_ids.append(
            chunk_id
        )


    if (
        len(
            set(
                ordered_chunk_ids
            )
        )
        != len(
            ordered_chunk_ids
        )
    ):
        raise ValueError(
            "Legacy chunk IDs are not unique."
        )


    for parent in parents.values():

        if (
            parent.get(
                "document_id"
            )
            != document_id
        ):
            raise ValueError(
                "Legacy parent document identity mismatch."
            )


        if (
            parent.get(
                "source_filename"
            )
            != source_filename
        ):
            raise ValueError(
                "Legacy parent source identity mismatch."
            )


    original_vector_sha256 = (
        _sha256_file(
            source_vector_path
        )
    )


    if output_filename is None:

        output_filename = (
            Path(
                vector_store_filename
            ).stem
            + "_source_attested_v1.npz"
        )


    output_filename = _clean_nonempty_text(
        output_filename,
        field_name="output_filename",
    )


    if (
        any(
            character in output_filename
            for character in "/\\:\x00"
        )
        or Path(
            output_filename
        ).suffix.lower()
        != ".npz"
    ):
        raise ValueError(
            "output_filename must be an NPZ filename "
            "inside vector_store."
        )


    if (
        output_filename
        == vector_store_filename
    ):
        raise ValueError(
            "Migration output must not overwrite "
            "the legacy vector artifact."
        )


    output_path = (
        vector_directory
        / output_filename
    ).resolve()


    if (
        output_path.parent
        != vector_directory
    ):
        raise ValueError(
            "Migration output escapes vector_store."
        )


    if output_path.exists():
        raise FileExistsError(
            "Migration output already exists."
        )


    # JSON round-trip gives us an independent deep copy
    # without mutating the cached validated metadata object.
    migrated_metadata = json.loads(
        json.dumps(
            metadata,
            ensure_ascii=False,
        )
    )


    migrated_metadata[
        "source_sha256"
    ] = raw_source_sha256


    migrated_metadata[
        "source_size_bytes"
    ] = raw_source_size_bytes


    migrated_metadata[
        "provenance_migration"
    ] = {
        "strategy":
            "legacy_vector_source_attestation_v1",

        "legacy_vector_store_filename":
            vector_store_filename,

        "legacy_vector_store_sha256":
            original_vector_sha256,

        "raw_source_filename":
            source_filename,

        "raw_source_sha256":
            raw_source_sha256,

        "raw_source_size_bytes":
            raw_source_size_bytes,

        "prepared_filename":
            prepared_filename,

        "prepared_sha256":
            actual_prepared_sha256,

        "vectors_reembedded":
            False,

        "vector_values_changed":
            False,

        "automatic_artifact_selection":
            False,
    }


    metadata_bytes = json.dumps(
        migrated_metadata,
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )


    created = False


    try:

        with output_path.open(
            "xb"
        ) as handle:

            created = True

            np.savez_compressed(
                handle,

                embeddings=
                    vectors,

                chunk_ids=
                    np.asarray(
                        ordered_chunk_ids
                    ),

                metadata_utf8=
                    np.frombuffer(
                        metadata_bytes,
                        dtype=np.uint8,
                    ),
            )


        (
            migrated_vectors,
            migrated_metadata_loaded,
            migrated_parents,
        ) = (
            retrieval_service
            .load_vector_store(
                output_filename
            )
        )


        if not np.array_equal(
            migrated_vectors,
            vectors,
        ):
            raise RuntimeError(
                "Vector values changed during provenance migration."
            )


        if (
            migrated_metadata_loaded.get(
                "source_sha256"
            )
            != raw_source_sha256
        ):
            raise RuntimeError(
                "Migrated source_sha256 did not persist."
            )


        if (
            migrated_metadata_loaded.get(
                "source_size_bytes"
            )
            != raw_source_size_bytes
        ):
            raise RuntimeError(
                "Migrated source_size_bytes did not persist."
            )


        if (
            migrated_metadata_loaded.get(
                "embedding"
            )
            != metadata.get(
                "embedding"
            )
        ):
            raise RuntimeError(
                "Embedding provenance changed during migration."
            )


        if (
            migrated_metadata_loaded.get(
                "chunks"
            )
            != metadata.get(
                "chunks"
            )
        ):
            raise RuntimeError(
                "Chunk metadata changed during migration."
            )


        if (
            migrated_metadata_loaded.get(
                "parents"
            )
            != metadata.get(
                "parents"
            )
        ):
            raise RuntimeError(
                "Parent metadata changed during migration."
            )


        if (
            migrated_parents
            != parents
        ):
            raise RuntimeError(
                "Validated parent mapping changed during migration."
            )


        migrated_vector_sha256 = (
            _sha256_file(
                output_path
            )
        )


        return {
            "document_id":
                document_id,

            "source_filename":
                source_filename,

            "source_sha256":
                raw_source_sha256,

            "source_size_bytes":
                raw_source_size_bytes,

            "prepared_filename":
                prepared_filename,

            "prepared_sha256":
                actual_prepared_sha256,

            "legacy_vector_store_filename":
                vector_store_filename,

            "legacy_vector_store_sha256":
                original_vector_sha256,

            "vector_store_filename":
                output_filename,

            "vector_store_sha256":
                migrated_vector_sha256,

            "vector_count":
                int(
                    vectors.shape[0]
                ),

            "embedding_dimension":
                int(
                    vectors.shape[1]
                ),

            "vectors_reembedded":
                False,

            "vector_values_changed":
                False,

            "automatic_artifact_selection":
                False,
        }


    except BaseException:

        if created:
            output_path.unlink(
                missing_ok=True
            )

        raise


# ======================================================================
# Explicit Qdrant bootstrap and reconciliation.
#
# Registry identity remains authoritative.
# No current/preferred artifact is inferred.
# No automatic deletion or repair is performed.
# ======================================================================


def _resolve_registered_artifact_for_reconciliation(
    *,
    document_id,
    vector_artifact_id,
    database_path=None,
):
    if (
        not isinstance(
            document_id,
            str,
        )
        or not document_id.strip()
    ):
        raise ValueError(
            "document_id must be a non-empty string."
        )


    if (
        not isinstance(
            vector_artifact_id,
            str,
        )
        or not vector_artifact_id.strip()
    ):
        raise ValueError(
            "vector_artifact_id must be a non-empty string."
        )


    document_id = document_id.strip()
    vector_artifact_id = (
        vector_artifact_id.strip()
    )


    document = (
        registry_backend
        .get_enterprise_document(
            document_id,

            database_path=
                database_path,
        )
    )


    if document is None:
        raise ValueError(
            "The supplied document_id is not registered."
        )


    artifacts = (
        registry_backend
        .find_document_vector_artifacts(
            document_id,

            database_path=
                database_path,
        )
    )


    matches = [
        artifact
        for artifact in artifacts
        if artifact.get(
            "vector_artifact_id"
        )
        == vector_artifact_id
    ]


    if len(matches) != 1:
        raise ValueError(
            "The supplied vector_artifact_id is not "
            "registered exactly once for the supplied document_id."
        )


    return (
        document,
        matches[0],
    )


def _load_registered_npz_for_reconciliation(
    *,
    document_id,
    document,
    artifact,
):
    filename = artifact.get(
        "vector_store_filename"
    )


    if (
        not isinstance(
            filename,
            str,
        )
        or not filename.strip()
    ):
        raise RuntimeError(
            "Registered artifact lacks vector_store_filename."
        )


    filename = filename.strip()


    if Path(filename).name != filename:
        raise RuntimeError(
            "Registered vector-store filename "
            "must not contain a path."
        )


    vector_path = (
        Path(
            retrieval_service
            .VECTOR_DIRECTORY
        )
        / filename
    )


    if not vector_path.is_file():
        raise FileNotFoundError(
            "Registered vector-store file is missing."
        )


    expected_sha = artifact.get(
        "vector_store_sha256"
    )


    if (
        not isinstance(
            expected_sha,
            str,
        )
        or len(expected_sha) != 64
    ):
        raise RuntimeError(
            "Registered vector artifact lacks "
            "a valid vector_store_sha256."
        )


    digest = hashlib.sha256()


    with vector_path.open(
        "rb"
    ) as stream:

        while True:

            block = stream.read(
                1024 * 1024
            )


            if not block:
                break


            digest.update(
                block
            )


    actual_sha = digest.hexdigest()


    if actual_sha != expected_sha:
        raise RuntimeError(
            "Registered vector-store SHA-256 does "
            "not match the current NPZ bytes."
        )


    vectors, metadata, parents = (
        retrieval_service
        .load_vector_store(
            filename
        )
    )


    if (
        metadata.get(
            "document_id"
        )
        != document_id
    ):
        raise RuntimeError(
            "Vector-store document_id does not match "
            "the registered document."
        )


    registered_source_sha = (
        document.get(
            "source_sha256"
        )
    )


    metadata_source_sha = (
        metadata.get(
            "source_sha256"
        )
    )


    if (
        not isinstance(
            registered_source_sha,
            str,
        )
        or len(
            registered_source_sha
        ) != 64
        or metadata_source_sha
        != registered_source_sha
    ):
        raise RuntimeError(
            "Vector-store source provenance does not "
            "match the registered document."
        )


    chunks = metadata.get(
        "chunks"
    )


    if (
        not isinstance(
            chunks,
            list,
        )
        or not chunks
    ):
        raise RuntimeError(
            "Validated vector store contains no chunks."
        )


    expected_count = artifact.get(
        "vector_count"
    )


    if (
        type(
            expected_count
        ) is not int
        or expected_count <= 0
    ):
        raise RuntimeError(
            "Registered vector_count is invalid."
        )


    if (
        vectors.shape[0]
        != expected_count
        or len(chunks)
        != expected_count
    ):
        raise RuntimeError(
            "Registered vector_count does not match "
            "the validated NPZ artifact."
        )


    expected_dimension = artifact.get(
        "embedding_dimension"
    )


    if (
        expected_dimension
        != qdrant_store.VECTOR_SIZE
        or vectors.ndim != 2
        or vectors.shape[1]
        != qdrant_store.VECTOR_SIZE
    ):
        raise RuntimeError(
            "Registered embedding dimension does not "
            "match the Qdrant vector contract."
        )


    embedding = metadata.get(
        "embedding"
    )


    if not isinstance(
        embedding,
        dict,
    ):
        raise RuntimeError(
            "Vector-store embedding provenance is missing."
        )


    checks = (
        (
            artifact.get(
                "embedding_model"
            ),
            embedding.get(
                "model_name"
            ),
            "embedding_model",
        ),
        (
            artifact.get(
                "prepared_filename"
            ),
            embedding.get(
                "prepared_filename"
            ),
            "prepared_filename",
        ),
        (
            artifact.get(
                "prepared_sha256"
            ),
            embedding.get(
                "prepared_sha256"
            ),
            "prepared_sha256",
        ),
    )


    for registered, stored, field in checks:

        if registered != stored:
            raise RuntimeError(
                "Registered "
                + field
                + " does not match vector-store provenance."
            )


    return {
        "filename":
            filename,

        "vectors":
            vectors,

        "metadata":
            metadata,

        "parents":
            parents,

        "chunks":
            chunks,

        "vector_count":
            expected_count,

        "vector_store_sha256":
            actual_sha,
    }


def inspect_registered_artifact_qdrant_state(
    client,
    *,
    document_id,
    vector_artifact_id,
    collection_name=
        qdrant_store.DEFAULT_COLLECTION_NAME,
    database_path=None,
):
    """
    Read-only comparison between one explicitly supplied
    Registry artifact and its Qdrant state.
    """

    from qdrant_client.models import (
        FieldCondition,
        Filter,
        MatchValue,
    )


    if (
        not isinstance(
            collection_name,
            str,
        )
        or not collection_name.strip()
    ):
        raise ValueError(
            "collection_name must be a non-empty string."
        )


    collection_name = (
        collection_name.strip()
    )


    document, artifact = (
        _resolve_registered_artifact_for_reconciliation(
            document_id=
                document_id,

            vector_artifact_id=
                vector_artifact_id,

            database_path=
                database_path,
        )
    )


    validated = (
        _load_registered_npz_for_reconciliation(
            document_id=
                document_id,

            document=
                document,

            artifact=
                artifact,
        )
    )


    expected_count = (
        validated[
            "vector_count"
        ]
    )


    def result(
        state,
        indexed_points,
        *,
        safe_to_bootstrap,
        mismatch_categories=None,
    ):
        output = {
            "state":
                state,

            "document_id":
                document_id,

            "vector_artifact_id":
                vector_artifact_id,

            "expected_points":
                expected_count,

            "indexed_points":
                indexed_points,

            "safe_to_bootstrap":
                safe_to_bootstrap,

            "write_performed":
                False,

            "automatic_artifact_selection":
                False,

            "automatic_deletion":
                False,
        }


        if mismatch_categories is not None:

            output[
                "mismatch_categories"
            ] = sorted(
                set(
                    mismatch_categories
                )
            )


        return output


    if not client.collection_exists(
        collection_name
    ):

        return result(
            "missing_collection",
            0,
            safe_to_bootstrap=True,
        )


    qdrant_store.require_dense_collection(
        client,

        collection_name=
            collection_name,
    )


    artifact_filter = Filter(
        must=[
            FieldCondition(
                key=
                    "vector_artifact_id",

                match=
                    MatchValue(
                        value=
                            vector_artifact_id
                    ),
            )
        ]
    )


    indexed_count = int(
        client.count(
            collection_name=
                collection_name,

            count_filter=
                artifact_filter,

            exact=
                True,
        )
        .count
    )


    if indexed_count == 0:

        return result(
            "artifact_absent",
            0,
            safe_to_bootstrap=True,
        )


    if indexed_count != expected_count:

        return result(
            "point_count_mismatch",
            indexed_count,
            safe_to_bootstrap=False,
        )


    records = []

    offset = None


    while True:

        page, next_offset = (
            client.scroll(
                collection_name=
                    collection_name,

                scroll_filter=
                    artifact_filter,

                limit=
                    min(
                        256,
                        expected_count,
                    ),

                offset=
                    offset,

                with_payload=
                    True,

                with_vectors=
                    False,
            )
        )


        records.extend(
            page
        )


        if next_offset is None:
            break


        if next_offset == offset:
            raise RuntimeError(
                "Qdrant scroll offset did not advance."
            )


        offset = next_offset


    if len(records) != expected_count:

        return result(
            "point_count_mismatch",
            len(records),
            safe_to_bootstrap=False,
        )


    chunks = validated[
        "chunks"
    ]


    seen_indexes = set()
    seen_chunks = set()
    mismatches = []


    for record in records:

        payload = (
            record.payload
            or {}
        )


        if (
            payload.get(
                "vector_artifact_id"
            )
            != vector_artifact_id
        ):
            mismatches.append(
                "vector_artifact_id"
            )

            continue


        if (
            payload.get(
                "document_id"
            )
            != document_id
        ):
            mismatches.append(
                "document_id"
            )

            continue


        vector_index = payload.get(
            "vector_index"
        )


        if (
            type(vector_index) is not int
            or vector_index < 0
            or vector_index >= expected_count
        ):
            mismatches.append(
                "vector_index"
            )

            continue


        chunk_id = payload.get(
            "chunk_id"
        )


        if (
            not isinstance(
                chunk_id,
                str,
            )
            or not chunk_id
        ):
            mismatches.append(
                "chunk_id"
            )

            continue


        if vector_index in seen_indexes:
            mismatches.append(
                "duplicate_vector_index"
            )

            continue


        if chunk_id in seen_chunks:
            mismatches.append(
                "duplicate_chunk_id"
            )

            continue


        expected_chunk_id = (
            chunks[
                vector_index
            ].get(
                "chunk_id"
            )
        )


        if chunk_id != expected_chunk_id:
            mismatches.append(
                "chunk_identity"
            )

            continue


        expected_point_id = (
            qdrant_store
            .deterministic_point_id(
                vector_artifact_id=
                    vector_artifact_id,

                chunk_id=
                    chunk_id,
            )
        )


        if (
            str(
                record.id
            )
            != str(
                expected_point_id
            )
        ):
            mismatches.append(
                "point_identity"
            )

            continue


        seen_indexes.add(
            vector_index
        )

        seen_chunks.add(
            chunk_id
        )


    if (
        mismatches
        or seen_indexes
        != set(
            range(
                expected_count
            )
        )
        or len(
            seen_chunks
        )
        != expected_count
    ):

        return result(
            "payload_mismatch",
            indexed_count,
            safe_to_bootstrap=False,
            mismatch_categories=
                mismatches,
        )


    return result(
        "synchronized",
        indexed_count,
        safe_to_bootstrap=False,
    )


def bootstrap_registered_npz_artifact(
    client,
    *,
    document_id,
    vector_artifact_id,
    collection_name=
        qdrant_store.DEFAULT_COLLECTION_NAME,
    database_path=None,
):
    """
    Explicitly bootstrap one registered NPZ artifact.

    Existing synchronized state is idempotent.
    Partial or mismatched state fails closed.
    """

    before = (
        inspect_registered_artifact_qdrant_state(
            client,

            document_id=
                document_id,

            vector_artifact_id=
                vector_artifact_id,

            collection_name=
                collection_name,

            database_path=
                database_path,
        )
    )


    if (
        before[
            "state"
        ]
        == "synchronized"
    ):

        return {
            "status":
                "already_synchronized",

            "write_performed":
                False,

            "before":
                before,

            "after":
                before,

            "automatic_artifact_selection":
                False,

            "automatic_deletion":
                False,
        }


    if (
        before[
            "state"
        ]
        not in (
            "missing_collection",
            "artifact_absent",
        )
    ):

        raise RuntimeError(
            "Qdrant contains a partial or mismatched "
            "state for this explicit artifact. "
            "Automatic deletion, replacement, or repair "
            "is not permitted."
        )


    imported = (
        import_registered_npz_artifact(
            client,

            document_id=
                document_id,

            vector_artifact_id=
                vector_artifact_id,

            collection_name=
                collection_name,

            database_path=
                database_path,
        )
    )


    after = (
        inspect_registered_artifact_qdrant_state(
            client,

            document_id=
                document_id,

            vector_artifact_id=
                vector_artifact_id,

            collection_name=
                collection_name,

            database_path=
                database_path,
        )
    )


    if (
        after[
            "state"
        ]
        != "synchronized"
    ):

        raise RuntimeError(
            "Qdrant bootstrap did not establish an "
            "exact synchronized state. "
            "Automatic cleanup was not attempted."
        )


    return {
        "status":
            "bootstrapped",

        "write_performed":
            True,

        "before":
            before,

        "after":
            after,

        "import_result":
            imported,

        "automatic_artifact_selection":
            False,

        "automatic_deletion":
            False,
    }
