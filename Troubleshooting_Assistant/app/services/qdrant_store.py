"""
Controlled Qdrant vector-index boundary.

PostgreSQL remains the system of record for enterprise documents,
vector artifacts, revisions, metadata, and later authorization.

Qdrant is only a derived semantic vector index.

This module does not:
- infer current/preferred/approved artifacts,
- infer document revision order,
- perform authorization,
- expose access_level as a caller-selected filter,
- generate embeddings,
- diagnose equipment faults.
"""

from __future__ import annotations

import re

from uuid import (
    NAMESPACE_URL,
    uuid5,
)

import numpy as np

from qdrant_client import (
    QdrantClient,
)

from qdrant_client.http import (
    models as qmodels,
)


VECTOR_SIZE = 384

VECTOR_DISTANCE = (
    qmodels.Distance.COSINE
)

DEFAULT_COLLECTION_NAME = (
    "industrial_knowledge_dense_v1"
)


_COLLECTION_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


def _clean_nonempty_text(
    value,
    *,
    field_name,
    max_length=255,
):
    if not isinstance(
        value,
        str,
    ):
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


def _clean_collection_name(
    collection_name,
):
    cleaned = _clean_nonempty_text(
        collection_name,
        field_name="collection_name",
        max_length=128,
    )

    if not _COLLECTION_PATTERN.fullmatch(
        cleaned
    ):
        raise ValueError(
            "collection_name contains unsupported characters."
        )

    return cleaned


def _validate_matrix(
    vectors,
    *,
    expected_rows,
):
    array = np.asarray(
        vectors,
        dtype=np.float32,
    )

    if array.ndim != 2:
        raise ValueError(
            "vectors must be a two-dimensional array."
        )

    if array.shape != (
        expected_rows,
        VECTOR_SIZE,
    ):
        raise ValueError(
            "vectors must have shape "
            f"({expected_rows}, {VECTOR_SIZE})."
        )

    if not np.isfinite(
        array
    ).all():
        raise ValueError(
            "vectors contain non-finite values."
        )

    norms = np.linalg.norm(
        array,
        axis=1,
    )

    if np.any(
        norms <= 0
    ):
        raise ValueError(
            "vectors must have non-zero norm."
        )

    if not np.allclose(
        norms,
        1.0,
        rtol=0.0,
        atol=1e-3,
    ):
        raise ValueError(
            "vectors must be normalized before Qdrant indexing."
        )

    return array


def _validate_query_vector(
    query_vector,
):
    array = np.asarray(
        query_vector,
        dtype=np.float32,
    )

    if array.shape != (
        VECTOR_SIZE,
    ):
        raise ValueError(
            f"query_vector must have shape ({VECTOR_SIZE},)."
        )

    if not np.isfinite(
        array
    ).all():
        raise ValueError(
            "query_vector contains non-finite values."
        )

    norm = float(
        np.linalg.norm(
            array
        )
    )

    if norm <= 0:
        raise ValueError(
            "query_vector must have non-zero norm."
        )

    if not np.isclose(
        norm,
        1.0,
        rtol=0.0,
        atol=1e-3,
    ):
        raise ValueError(
            "query_vector must be normalized."
        )

    return array


def deterministic_point_id(
    *,
    vector_artifact_id,
    chunk_id,
):
    """
    Derive a stable UUID from the immutable artifact/chunk identity.

    Re-indexing the same artifact/chunk therefore updates the same
    Qdrant point instead of silently creating a duplicate.
    """
    artifact_id = _clean_nonempty_text(
        vector_artifact_id,
        field_name="vector_artifact_id",
    )

    chunk = _clean_nonempty_text(
        chunk_id,
        field_name="chunk_id",
        max_length=512,
    )

    identity = (
        "troubleshooting-assistant:"
        + artifact_id
        + ":"
        + chunk
    )

    return str(
        uuid5(
            NAMESPACE_URL,
            identity,
        )
    )


def ensure_dense_collection(
    client,
    *,
    collection_name=DEFAULT_COLLECTION_NAME,
):
    """
    Create the 384-D cosine collection if absent.

    An existing collection is validated rather than recreated.
    A mismatched collection fails closed.
    """
    if not isinstance(
        client,
        QdrantClient,
    ):
        raise TypeError(
            "client must be a QdrantClient."
        )

    collection = _clean_collection_name(
        collection_name
    )

    if not client.collection_exists(
        collection
    ):
        client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=VECTOR_DISTANCE,
            ),
        )

    info = client.get_collection(
        collection
    )

    vectors = (
        info.config.params.vectors
    )

    if isinstance(
        vectors,
        dict,
    ):
        raise ValueError(
            "Named-vector collections are not supported "
            "by this dense retrieval contract."
        )

    if vectors is None:
        raise ValueError(
            "Qdrant collection has no dense-vector configuration."
        )

    if int(
        vectors.size
    ) != VECTOR_SIZE:
        raise ValueError(
            "Qdrant collection vector dimension "
            f"is {vectors.size}; expected {VECTOR_SIZE}."
        )

    if (
        vectors.distance
        != VECTOR_DISTANCE
    ):
        raise ValueError(
            "Qdrant collection distance must be cosine."
        )

    return info


def upsert_artifact_vectors(
    client,
    *,
    vector_artifact_id,
    document_id,
    chunk_ids,
    vectors,
    collection_name=DEFAULT_COLLECTION_NAME,
):
    """
    Index one already-approved Registry artifact into Qdrant.

    The caller must obtain vector_artifact_id from the trusted
    Registry layer. This function does not select an artifact.
    """
    artifact_id = _clean_nonempty_text(
        vector_artifact_id,
        field_name="vector_artifact_id",
    )

    document = _clean_nonempty_text(
        document_id,
        field_name="document_id",
    )

    if not isinstance(
        chunk_ids,
        (list, tuple),
    ):
        raise ValueError(
            "chunk_ids must be a list or tuple."
        )

    if not chunk_ids:
        raise ValueError(
            "chunk_ids must not be empty."
        )

    cleaned_chunk_ids = [
        _clean_nonempty_text(
            chunk_id,
            field_name="chunk_id",
            max_length=512,
        )
        for chunk_id
        in chunk_ids
    ]

    if len(
        set(
            cleaned_chunk_ids
        )
    ) != len(
        cleaned_chunk_ids
    ):
        raise ValueError(
            "chunk_ids must be unique within one artifact."
        )

    matrix = _validate_matrix(
        vectors,
        expected_rows=len(
            cleaned_chunk_ids
        ),
    )

    collection = _clean_collection_name(
        collection_name
    )

    ensure_dense_collection(
        client,
        collection_name=collection,
    )

    points = []

    for vector_index, (
        chunk_id,
        vector,
    ) in enumerate(
        zip(
            cleaned_chunk_ids,
            matrix,
            strict=True,
        )
    ):
        payload = {
            "vector_artifact_id":
                artifact_id,

            "document_id":
                document,

            "chunk_id":
                chunk_id,

            "vector_index":
                vector_index,
        }

        # Authorization metadata is deliberately not copied into
        # the vector index. Trusted authorization belongs outside
        # this derived semantic index.
        if "access_level" in payload:
            raise RuntimeError(
                "access_level must not be stored "
                "by this Qdrant indexing boundary."
            )

        points.append(
            qmodels.PointStruct(
                id=deterministic_point_id(
                    vector_artifact_id=
                        artifact_id,

                    chunk_id=
                        chunk_id,
                ),

                vector=vector.tolist(),

                payload=payload,
            )
        )

    result = client.upsert(
        collection_name=collection,
        points=points,
        wait=True,
    )

    return {
        "collection_name":
            collection,

        "vector_artifact_id":
            artifact_id,

        "document_id":
            document,

        "points_count":
            len(points),

        "automatic_artifact_selection":
            False,

        "authorization_enforced":
            False,

        "qdrant_update_status":
            str(
                result.status
            ),
    }


def query_eligible_artifacts(
    client,
    *,
    query_vector,
    eligible_vector_artifact_ids,
    limit=5,
    collection_name=DEFAULT_COLLECTION_NAME,
):
    """
    Perform semantic ranking only inside explicitly eligible artifacts.

    Eligibility must be decided before this call, normally from
    PostgreSQL Registry discovery and later trusted authorization.
    """
    if type(limit) is not int:
        raise ValueError(
            "limit must be an integer."
        )

    if not 1 <= limit <= 25:
        raise ValueError(
            "limit must be between 1 and 25."
        )

    if not isinstance(
        eligible_vector_artifact_ids,
        (list, tuple),
    ):
        raise ValueError(
            "eligible_vector_artifact_ids "
            "must be a list or tuple."
        )

    if not eligible_vector_artifact_ids:
        raise ValueError(
            "At least one eligible vector artifact "
            "must be supplied explicitly."
        )

    artifact_ids = [
        _clean_nonempty_text(
            value,
            field_name=
                "eligible_vector_artifact_id",
        )
        for value
        in eligible_vector_artifact_ids
    ]

    artifact_ids = list(
        dict.fromkeys(
            artifact_ids
        )
    )

    if len(
        artifact_ids
    ) > 25:
        raise ValueError(
            "No more than 25 eligible vector artifacts "
            "may be queried in one development request."
        )

    vector = _validate_query_vector(
        query_vector
    )

    collection = _clean_collection_name(
        collection_name
    )

    require_dense_collection(
        client,
        collection_name=collection,
    )

    query_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="vector_artifact_id",
                match=qmodels.MatchAny(
                    any=artifact_ids
                ),
            )
        ]
    )

    response = client.query_points(
        collection_name=collection,
        query=vector.tolist(),
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    results = []

    for rank, point in enumerate(
        response.points,
        start=1,
    ):
        payload = dict(
            point.payload
            or {}
        )

        artifact_id = payload.get(
            "vector_artifact_id"
        )

        if artifact_id not in artifact_ids:
            raise RuntimeError(
                "Qdrant returned a point outside "
                "the eligible artifact set."
            )

        if "access_level" in payload:
            raise RuntimeError(
                "Qdrant result unexpectedly contains "
                "access_level."
            )

        results.append(
            {
                "rank":
                    rank,

                "point_id":
                    str(
                        point.id
                    ),

                "cosine_similarity":
                    float(
                        point.score
                    ),

                "similarity_is_confidence":
                    False,

                "vector_artifact_id":
                    artifact_id,

                "document_id":
                    payload.get(
                        "document_id"
                    ),

                "chunk_id":
                    payload.get(
                        "chunk_id"
                    ),

                "vector_index":
                    payload.get(
                        "vector_index"
                    ),
            }
        )

    return {
        "collection_name":
            collection,

        "eligible_vector_artifact_ids":
            artifact_ids,

        "results_count":
            len(results),

        "results":
            results,

        "automatic_artifact_selection":
            False,

        "authorization_enforced":
            False,

        "message": (
            "Ranked Qdrant source candidates only. "
            "Cosine similarity is not diagnostic confidence."
        ),
    }


def require_dense_collection(
    client,
    *,
    collection_name=DEFAULT_COLLECTION_NAME,
):
    """
    Validate an already-existing dense Qdrant collection.

    Unlike ensure_dense_collection(), this read-side helper
    never creates a missing collection.
    """

    if not isinstance(
        client,
        QdrantClient,
    ):
        raise TypeError(
            "client must be a QdrantClient."
        )

    collection = _clean_collection_name(
        collection_name
    )

    if not client.collection_exists(
        collection
    ):
        raise FileNotFoundError(
            "Qdrant collection is not initialized."
        )

    info = client.get_collection(
        collection
    )

    vectors = (
        info.config.params.vectors
    )

    if isinstance(
        vectors,
        dict,
    ):
        raise ValueError(
            "Named-vector collections are not supported "
            "by this dense retrieval contract."
        )

    if vectors is None:
        raise ValueError(
            "Qdrant collection has no dense-vector configuration."
        )

    if int(
        vectors.size
    ) != VECTOR_SIZE:
        raise ValueError(
            "Qdrant collection vector dimension "
            f"is {vectors.size}; expected {VECTOR_SIZE}."
        )

    if (
        vectors.distance
        != VECTOR_DISTANCE
    ):
        raise ValueError(
            "Qdrant collection distance must be cosine."
        )

    return info


def query_eligible_artifacts_deep(
    client,
    *,
    query_vector,
    eligible_vector_artifact_ids,
    limit,
    collection_name=DEFAULT_COLLECTION_NAME,
):
    """
    Read-only bounded Qdrant query used when parent-level
    deduplication requires more raw chunk candidates.

    This does not create collections, select artifacts,
    authorize access, or interpret cosine similarity as
    diagnostic confidence.
    """

    from qdrant_client.models import (
        FieldCondition,
        Filter,
        MatchAny,
        SearchParams,
    )


    if (
        type(limit) is not int
        or not 1 <= limit <= 1000
    ):
        raise ValueError(
            "limit must be an integer between 1 and 1000."
        )


    if (
        not isinstance(
            eligible_vector_artifact_ids,
            list,
        )
        or not eligible_vector_artifact_ids
        or len(
            eligible_vector_artifact_ids
        ) > 25
    ):
        raise ValueError(
            "eligible_vector_artifact_ids must contain "
            "between 1 and 25 explicit artifact IDs."
        )


    eligible_ids = []


    for value in eligible_vector_artifact_ids:

        if (
            not isinstance(
                value,
                str,
            )
            or not value.strip()
        ):
            raise ValueError(
                "Every eligible artifact ID must "
                "be a non-empty string."
            )


        value = value.strip()


        if value in eligible_ids:
            raise ValueError(
                "Eligible artifact IDs must be unique."
            )


        eligible_ids.append(
            value
        )


    vector = np.asarray(
        query_vector,
        dtype=np.float32,
    )


    if (
        vector.shape
        != (
            VECTOR_SIZE,
        )
    ):
        raise ValueError(
            f"Query vector must have shape ({VECTOR_SIZE},)."
        )


    if not np.all(
        np.isfinite(
            vector
        )
    ):
        raise ValueError(
            "Query vector contains non-finite values."
        )


    norm = float(
        np.linalg.norm(
            vector
        )
    )


    if (
        not np.isfinite(
            norm
        )
        or norm <= 0.0
    ):
        raise ValueError(
            "Query vector must be nonzero."
        )


    if abs(
        norm - 1.0
    ) > 0.001:
        raise ValueError(
            "Query vector must be normalized."
        )


    require_dense_collection(
        client,
        collection_name=
            collection_name,
    )


    response = client.query_points(
        collection_name=
            collection_name,

        query=
            vector.tolist(),

        query_filter=
            Filter(
                must=[
                    FieldCondition(
                        key=
                            "vector_artifact_id",

                        match=
                            MatchAny(
                                any=
                                    eligible_ids
                            ),
                    )
                ]
            ),

        search_params=
            SearchParams(
                exact=True
            ),

        limit=
            limit,

        with_payload=
            True,

        with_vectors=
            False,
    )


    results = []


    for rank, point in enumerate(
        response.points,
        start=1,
    ):

        payload = (
            point.payload
            or {}
        )


        artifact_id = payload.get(
            "vector_artifact_id"
        )


        if artifact_id not in eligible_ids:
            raise RuntimeError(
                "Qdrant returned a point outside "
                "the eligible artifact set."
            )


        document_id = payload.get(
            "document_id"
        )

        chunk_id = payload.get(
            "chunk_id"
        )

        vector_index = payload.get(
            "vector_index"
        )


        if (
            not isinstance(
                document_id,
                str,
            )
            or not document_id.strip()
        ):
            raise RuntimeError(
                "Qdrant point lacks document_id."
            )


        if (
            not isinstance(
                chunk_id,
                str,
            )
            or not chunk_id.strip()
        ):
            raise RuntimeError(
                "Qdrant point lacks chunk_id."
            )


        if (
            type(vector_index) is not int
            or vector_index < 0
        ):
            raise RuntimeError(
                "Qdrant point has invalid vector_index."
            )


        score = float(
            point.score
        )


        if not np.isfinite(
            score
        ):
            raise RuntimeError(
                "Qdrant returned a non-finite score."
            )


        results.append(
            {
                "rank":
                    rank,

                "vector_artifact_id":
                    artifact_id,

                "document_id":
                    document_id,

                "chunk_id":
                    chunk_id,

                "vector_index":
                    vector_index,

                "cosine_similarity":
                    float(
                        np.clip(
                            score,
                            -1.0,
                            1.0,
                        )
                    ),

                "similarity_is_confidence":
                    False,
            }
        )


    return {
        "collection_name":
            collection_name,

        "eligible_vector_artifact_ids":
            eligible_ids,

        "requested_limit":
            limit,

        "results_count":
            len(
                results
            ),

        "results":
            results,

        "exact_vector_search":
            True,

        "automatic_artifact_selection":
            False,

        "authorization_enforced":
            False,

        "similarity_is_confidence":
            False,
    }


# ======================================================================
# Trusted application-level vector retrieval configuration.
#
# These values are process configuration only.
# Browser/request payloads must never control them.
# ======================================================================

import os as _application_os

from pathlib import Path as _ApplicationPath
from threading import RLock as _ApplicationRLock


VECTOR_RETRIEVAL_BACKEND_ENV = (
    "TA_VECTOR_RETRIEVAL_BACKEND"
)

QDRANT_PATH_ENV = (
    "TA_QDRANT_PATH"
)

QDRANT_COLLECTION_ENV = (
    "TA_QDRANT_COLLECTION"
)

DEFAULT_VECTOR_RETRIEVAL_BACKEND = (
    "npz"
)

ALLOWED_VECTOR_RETRIEVAL_BACKENDS = frozenset(
    (
        "npz",
        "qdrant",
    )
)


_APPLICATION_PROJECT_ROOT = (
    _ApplicationPath(
        __file__
    )
    .resolve()
    .parents[2]
)


DEFAULT_APPLICATION_QDRANT_PATH = (
    _APPLICATION_PROJECT_ROOT
    / "data"
    / "qdrant"
).resolve()


_APPLICATION_QDRANT_CLIENT = None
_APPLICATION_QDRANT_CLIENT_PATH = None

_APPLICATION_QDRANT_CLIENT_LOCK = (
    _ApplicationRLock()
)


def get_vector_retrieval_backend():
    """
    Resolve the trusted process-level vector retrieval backend.

    NPZ remains the default during migration.
    Invalid configured values fail closed.
    """

    configured = (
        _application_os.environ.get(
            VECTOR_RETRIEVAL_BACKEND_ENV
        )
    )


    if configured is None:

        return (
            DEFAULT_VECTOR_RETRIEVAL_BACKEND
        )


    configured = (
        configured
        .strip()
        .lower()
    )


    if not configured:

        raise ValueError(
            "TA_VECTOR_RETRIEVAL_BACKEND must not "
            "be blank when configured."
        )


    if (
        configured
        not in ALLOWED_VECTOR_RETRIEVAL_BACKENDS
    ):

        raise ValueError(
            "Unsupported vector retrieval backend. "
            "Expected one of: npz, qdrant."
        )


    return configured


def get_application_qdrant_path():
    """
    Resolve the trusted persistent local Qdrant path.
    """

    configured = (
        _application_os.environ.get(
            QDRANT_PATH_ENV
        )
    )


    if configured is None:

        return (
            DEFAULT_APPLICATION_QDRANT_PATH
        )


    configured = (
        configured.strip()
    )


    if not configured:

        raise ValueError(
            "TA_QDRANT_PATH must not be blank "
            "when configured."
        )


    path = (
        _ApplicationPath(
            configured
        )
        .expanduser()
    )


    if not path.is_absolute():

        raise ValueError(
            "TA_QDRANT_PATH must be an "
            "absolute filesystem path."
        )


    path = (
        path.resolve()
    )


    if (
        path.exists()
        and not path.is_dir()
    ):

        raise ValueError(
            "TA_QDRANT_PATH exists but is "
            "not a directory."
        )


    return path


def get_application_qdrant_collection_name():
    """
    Resolve the trusted application Qdrant collection.
    """

    import re


    configured = (
        _application_os.environ.get(
            QDRANT_COLLECTION_ENV
        )
    )


    if configured is None:

        return (
            DEFAULT_COLLECTION_NAME
        )


    configured = (
        configured.strip()
    )


    if not configured:

        raise ValueError(
            "TA_QDRANT_COLLECTION must not "
            "be blank when configured."
        )


    if (
        re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",
            configured,
        )
        is None
    ):

        raise ValueError(
            "TA_QDRANT_COLLECTION contains "
            "unsupported characters."
        )


    return configured


def get_application_qdrant_client():
    """
    Return the process-owned persistent local Qdrant client.

    Client construction is permitted only when the trusted
    process-level vector backend is explicitly qdrant.

    This function does not create a collection.
    """

    global _APPLICATION_QDRANT_CLIENT
    global _APPLICATION_QDRANT_CLIENT_PATH


    backend = (
        get_vector_retrieval_backend()
    )


    if backend != "qdrant":

        raise RuntimeError(
            "Application Qdrant client requested "
            "while vector retrieval backend is not qdrant."
        )


    path = (
        get_application_qdrant_path()
    )


    with _APPLICATION_QDRANT_CLIENT_LOCK:

        if (
            _APPLICATION_QDRANT_CLIENT
            is not None
        ):

            if (
                _APPLICATION_QDRANT_CLIENT_PATH
                != path
            ):

                raise RuntimeError(
                    "TA_QDRANT_PATH changed after the "
                    "application Qdrant client was initialized. "
                    "Close the client or restart the process "
                    "before changing storage."
                )


            return (
                _APPLICATION_QDRANT_CLIENT
            )


        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        client = QdrantClient(
            path=str(
                path
            )
        )


        _APPLICATION_QDRANT_CLIENT = (
            client
        )

        _APPLICATION_QDRANT_CLIENT_PATH = (
            path
        )


        return client


def close_application_qdrant_client():
    """
    Close and clear the process-owned Qdrant client.
    """

    global _APPLICATION_QDRANT_CLIENT
    global _APPLICATION_QDRANT_CLIENT_PATH


    with _APPLICATION_QDRANT_CLIENT_LOCK:

        client = (
            _APPLICATION_QDRANT_CLIENT
        )


        if client is None:

            _APPLICATION_QDRANT_CLIENT_PATH = (
                None
            )

            return False


        try:

            close = getattr(
                client,
                "close",
                None,
            )


            if callable(
                close
            ):

                close()


        finally:

            _APPLICATION_QDRANT_CLIENT = (
                None
            )

            _APPLICATION_QDRANT_CLIENT_PATH = (
                None
            )


        return True
