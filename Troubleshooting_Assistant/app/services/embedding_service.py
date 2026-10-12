"""Generate local document embeddings and save a self-contained NumPy store."""

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock

import numpy as np
from app.services import registry_backend

from app.services.embedding_preparer import (
    MODEL_DIRECTORY, MODEL_NAME, MODEL_TOKEN_LIMIT, count_tokens, get_tokenizer,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREPARED_DIRECTORY = PROJECT_ROOT / "data" / "embedding_documents"
VECTOR_DIRECTORY = PROJECT_ROOT / "data" / "vector_store"
EMBEDDING_DIMENSION = 384
EMBEDDING_LOCK = Lock()


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(
        str(MODEL_DIRECTORY),
        device="cpu",
        local_files_only=True,
        trust_remote_code=False,
        model_kwargs={"use_safetensors": True},
    )
    if model.max_seq_length != MODEL_TOKEN_LIMIT:
        raise ValueError("Unexpected model token limit. Review the local model.")
    if model.get_sentence_embedding_dimension() != EMBEDDING_DIMENSION:
        raise ValueError("Unexpected embedding dimension. Review the local model.")
    return model


def validate_prepared_document(document, tokenizer):
    """Reject invalid metadata or text that would be silently truncated."""
    if not isinstance(document, dict):
        raise ValueError("The prepared document must be a JSON object.")
    for key in ("document_id", "source_filename"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise ValueError(f"Missing or invalid {key}.")
    preparation = document.get("preparation")
    if not isinstance(preparation, dict) or preparation.get("embedding_model") != MODEL_NAME:
        raise ValueError("Use the embedding-ready JSON prepared for the BGE model.")
    chunks, parents = document.get("chunks"), document.get("parents")
    if not isinstance(chunks, list) or not chunks or not isinstance(parents, list) or not parents:
        raise ValueError("The document must contain nonempty chunks and parents lists.")
    if document.get("total_chunks") != len(chunks):
        raise ValueError("The declared chunk count does not match the actual list.")

    parent_ids = set()
    for parent in parents:
        parent_id = parent.get("parent_id") if isinstance(parent, dict) else None
        if not isinstance(parent_id, str) or not parent_id.strip() or parent_id in parent_ids:
            raise ValueError("Missing or duplicate parent_id.")
        if not isinstance(parent.get("text"), str) or not parent["text"].strip():
            raise ValueError(f"Missing parent text: {parent_id}")
        parent_ids.add(parent_id)

    seen_ids = set()
    maximum_tokens = 0
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("Every chunk must be a JSON object.")
        chunk_id, text = chunk.get("chunk_id"), chunk.get("text")
        if not isinstance(chunk_id, str) or not chunk_id.strip() or chunk_id in seen_ids:
            raise ValueError("Missing or duplicate chunk_id.")
        seen_ids.add(chunk_id)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Empty or invalid text: {chunk_id}")
        if not isinstance(chunk.get("parent_id"), str) or chunk["parent_id"] not in parent_ids:
            raise ValueError(f"Missing parent: {chunk_id}")
        for key in ("document_id", "source_filename"):
            if chunk.get(key) != document[key]:
                raise ValueError(f"Mismatched {key}: {chunk_id}")
        pages = chunk.get("page_numbers")
        if not isinstance(pages, list) or not pages or any(type(p) is not int or p < 1 for p in pages):
            raise ValueError(f"Invalid page_numbers: {chunk_id}")
        actual_tokens = count_tokens(text, tokenizer)
        if actual_tokens > MODEL_TOKEN_LIMIT:
            raise ValueError(f"Chunk exceeds {MODEL_TOKEN_LIMIT} tokens: {chunk_id}")
        if chunk.get("token_count") != actual_tokens:
            raise ValueError(f"Token count changed. Prepare the document again: {chunk_id}")
        maximum_tokens = max(maximum_tokens, actual_tokens)
    return maximum_tokens


def validate_vectors(vectors, row_count):
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.shape != (row_count, EMBEDDING_DIMENSION):
        raise ValueError(f"Unexpected embedding shape: {vectors.shape}")
    if not np.isfinite(vectors).all():
        raise ValueError("Embeddings contain NaN or infinite values.")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, rtol=1e-4, atol=1e-5):
        raise ValueError("Embeddings must be nonzero, normalized vectors.")
    return vectors



# === ENTERPRISE VECTOR ARTIFACT INTEGRATION V1 ===

def _sha256_file_path(path: Path) -> str:
    """Return the SHA-256 fingerprint of an existing file."""
    path = Path(path)

    hasher = hashlib.sha256()

    with path.open("rb") as handle:

        while True:

            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            hasher.update(block)

    return hasher.hexdigest()


def _register_vector_artifact_if_enterprise(
    *,
    document: dict,
    prepared_filename: str,
    prepared_sha256: str,
    output_path: Path,
    embedding_model: str,
    embedding_dimension: int,
    vector_count: int,
    embedding_created_at_utc: str,
    database_path: Path | None = None,
):
    """
    Register the completed vector artifact only when the
    source document already exists in the enterprise registry.

    Legacy unregistered documents remain supported.

    Registration does not mark any artifact as current,
    preferred, approved, or authorized.
    """
    if not isinstance(document, dict):
        raise ValueError(
            "Prepared document must be a dictionary."
        )

    document_id = document.get(
        "document_id"
    )

    if (
        not isinstance(document_id, str)
        or not document_id.strip()
    ):
        raise ValueError(
            "Prepared document requires a document_id."
        )

    document_id = document_id.strip()

    database_path = (
        Path(database_path)
        if database_path is not None
        else None
    )

    registered_document = (
        registry_backend.get_enterprise_document(
            document_id,
            database_path=database_path,
        )
    )

    # Legacy compatibility.
    if registered_document is None:
        return None

    enterprise_metadata = document.get(
        "enterprise_metadata"
    )

    if enterprise_metadata is not None:

        if not isinstance(
            enterprise_metadata,
            dict,
        ):
            raise ValueError(
                "enterprise_metadata must be "
                "an object or null."
            )

        metadata_document_id = (
            enterprise_metadata.get(
                "document_id"
            )
        )

        if (
            metadata_document_id is not None
            and metadata_document_id
            != document_id
        ):
            raise ValueError(
                "Prepared enterprise metadata "
                "document_id differs from the "
                "registered document."
            )

        metadata_source_sha256 = (
            enterprise_metadata.get(
                "source_sha256"
            )
        )

        if (
            metadata_source_sha256 is not None
            and metadata_source_sha256
            != registered_document[
                "source_sha256"
            ]
        ):
            raise ValueError(
                "Prepared enterprise metadata "
                "source SHA-256 differs from the "
                "registered source document."
            )

    output_path = Path(
        output_path
    )

    if not output_path.is_file():
        raise FileNotFoundError(
            "Completed vector artifact was not found."
        )

    artifact_information = {
        "document_id":
            document_id,

        "vector_store_filename":
            output_path.name,

        "prepared_filename":
            prepared_filename,

        "prepared_sha256":
            prepared_sha256,

        "vector_store_sha256":
            _sha256_file_path(
                output_path
            ),

        "embedding_model":
            embedding_model,

        "embedding_dimension":
            embedding_dimension,

        "vector_count":
            vector_count,

        "embedding_created_at_utc":
            embedding_created_at_utc,
    }

    return (
        registry_backend
        .register_document_vector_artifact(
            artifact_information,
            database_path=database_path,
        )
    )


def generate_document_embeddings(prepared_filename, batch_size=16):
    """Encode prepared text in order; save vectors and metadata without pickle."""
    if type(batch_size) is not int or not 1 <= batch_size <= 32:
        raise ValueError("batch_size must be an integer between 1 and 32.")
    if (
        not isinstance(prepared_filename, str)
        or any(c in prepared_filename for c in '/\\:\x00')
        or Path(prepared_filename).suffix.lower() != ".json"
    ):
        raise ValueError("Provide only the prepared JSON filename, not a folder path.")
    input_path = (PREPARED_DIRECTORY / prepared_filename).resolve()
    if input_path.parent != PREPARED_DIRECTORY.resolve():
        raise ValueError("The input must be inside embedding_documents.")
    if not input_path.is_file():
        raise FileNotFoundError("Document not found in embedding_documents.")
    output_path = VECTOR_DIRECTORY / f"{Path(prepared_filename).stem}_bge_small.npz"

    # Run one embedding job at a time in this process to limit CPU/RAM contention.
    with EMBEDDING_LOCK:
        if output_path.exists():
            raise FileExistsError(f"Vector store already exists: {output_path.name}")
        source_bytes = input_path.read_bytes()
        document = json.loads(source_bytes)
        print("Checking prepared chunks...", flush=True)
        maximum_tokens = validate_prepared_document(document, get_tokenizer())
        chunks = document["chunks"]

        print(f"Generating embeddings for {len(chunks)} chunks on CPU...", flush=True)
        model = get_embedding_model()
        vectors = model.encode(
            [chunk["text"] for chunk in chunks],
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
            prompt="",  # Document text gets no query instruction or extra prefix.
        )
        vectors = validate_vectors(vectors, len(chunks))

        embedding_info = {
            "schema_version": 1,
            "model_name": MODEL_NAME,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "normalized": True,
            "dtype": "float32",
            "document_prompt": "",
            "model_token_limit": MODEL_TOKEN_LIMIT,
            "maximum_input_tokens": maximum_tokens,
            "prepared_filename": prepared_filename,
            "prepared_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        metadata = {
            **document,
            "embedding": embedding_info,
            "chunks": [
                {**chunk, "vector_index": index}
                for index, chunk in enumerate(chunks)
            ],
        }
        metadata_bytes = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
        VECTOR_DIRECTORY.mkdir(parents=True, exist_ok=True)
        handle = output_path.open("xb")
        try:
            with handle:
                np.savez_compressed(
                    handle,
                    embeddings=vectors,
                    chunk_ids=np.asarray([chunk["chunk_id"] for chunk in chunks]),
                    metadata_utf8=np.frombuffer(metadata_bytes, dtype=np.uint8),
                )
        except BaseException:
            output_path.unlink(missing_ok=True)  # Remove only our incomplete new file.
            raise

        # Register only after the NPZ file has been completed.
        #
        # If enterprise artifact registration fails, remove only
        # the newly generated NPZ so file and registry state
        # cannot silently diverge.
        try:
            _register_vector_artifact_if_enterprise(
                document=document,
                prepared_filename=prepared_filename,
                prepared_sha256=embedding_info[
                    "prepared_sha256"
                ],
                output_path=output_path,
                embedding_model=MODEL_NAME,
                embedding_dimension=EMBEDDING_DIMENSION,
                vector_count=len(chunks),
                embedding_created_at_utc=embedding_info[
                    "created_at_utc"
                ],
            )

        except BaseException:
            output_path.unlink(
                missing_ok=True
            )
            raise

        return {
            "document_id": document["document_id"],
            "model_name": MODEL_NAME,
            "total_embeddings": len(chunks),
            "embedding_dimension": EMBEDDING_DIMENSION,
            "embedding_shape": list(vectors.shape),
            "normalized": True,
            "maximum_input_tokens": maximum_tokens,
            "vector_store_filename": output_path.name,
            "saved_location": str(output_path),
        }