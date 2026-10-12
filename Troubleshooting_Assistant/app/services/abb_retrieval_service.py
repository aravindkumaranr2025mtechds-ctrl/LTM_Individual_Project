"""ABB-specific, read-only retrieval built on the validated shared retriever."""

from copy import deepcopy

import numpy as np

from app.services import retrieval_service as shared_retrieval


EXPECTED_STRATEGY = "abb_complete_records_v1"
EXPECTED_MANUFACTURER = "ABB"
LABEL_WEIGHT = 0.65
RECORD_WEIGHT = 0.35
AMBIGUITY_MARGIN = 0.02


def _nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_abb_metadata(metadata, parents):
    """Reject non-ABB or incomplete stores before returning domain records."""
    preparation = metadata.get("preparation")
    usage = metadata.get("usage")
    if (
        metadata.get("manufacturer") != EXPECTED_MANUFACTURER
        or not isinstance(preparation, dict)
        or preparation.get("strategy") != EXPECTED_STRATEGY
    ):
        raise ValueError(
            "The selected vector store is not the reviewed ABB record store."
        )
    if (
        not isinstance(usage, dict)
        or usage.get("approved_for_automatic_execution") is not False
    ):
        raise ValueError("ABB usage restrictions are missing or changed.")

    contexts = metadata.get("contexts")
    if not isinstance(contexts, list) or not contexts:
        raise ValueError("ABB source contexts are missing.")
    context_by_id = {}
    for context in contexts:
        context_id = (
            context.get("context_id") if isinstance(context, dict) else None
        )
        if not _nonempty_text(context_id) or context_id in context_by_id:
            raise ValueError("ABB context IDs are missing or duplicated.")
        if not _nonempty_text(context.get("text_layout")):
            raise ValueError(
                f"ABB source context text is missing: {context_id}"
            )
        context_by_id[context_id] = context

    records = metadata.get("records")
    if (
        not isinstance(records, list)
        or len(records) != metadata.get("total_records")
    ):
        raise ValueError("ABB source-record counts do not match.")
    record_by_id = {}
    for record in records:
        record_id = (
            record.get("record_id") if isinstance(record, dict) else None
        )
        if not _nonempty_text(record_id) or record_id in record_by_id:
            raise ValueError("ABB record IDs are missing or duplicated.")
        record_by_id[record_id] = record

    if len(parents) != len(record_by_id):
        raise ValueError(
            "ABB parents and source records are not one-to-one."
        )
    required = ("symptom", "possible_cause", "manufacturer_guidance")
    for parent_id, parent in parents.items():
        record_id = parent.get("record_id")
        if parent_id != record_id or record_id not in record_by_id:
            raise ValueError(
                f"ABB parent-to-record link is invalid: {parent_id}"
            )
        record = record_by_id[record_id]
        for field in required:
            if (
                not _nonempty_text(parent.get(field))
                or parent.get(field) != record.get(field)
            ):
                raise ValueError(
                    f"ABB record field changed: {record_id}.{field}"
                )
        context_ids = parent.get("context_ids")
        if (
            not isinstance(context_ids, list)
            or not context_ids
            or any(
                context_id not in context_by_id
                for context_id in context_ids
            )
        ):
            raise ValueError(
                f"ABB context link is invalid: {record_id}"
            )

    chunks = metadata.get("chunks")
    if (
        not isinstance(chunks, list)
        or len(chunks) != len(record_by_id)
    ):
        raise ValueError(
            "ABB requires one searchable chunk per source record."
        )
    chunk_by_parent = {}
    for chunk in chunks:
        parent_id = (
            chunk.get("parent_id") if isinstance(chunk, dict) else None
        )
        if parent_id not in parents or parent_id in chunk_by_parent:
            raise ValueError(
                "ABB chunk-to-record links are missing or duplicated."
            )
        parent = parents[parent_id]
        if (
            chunk.get("record_id") != parent.get("record_id")
            or chunk.get("symptom_id") != parent.get("symptom_id")
        ):
            raise ValueError(
                f"ABB chunk metadata changed: {parent_id}"
            )
        chunk_by_parent[parent_id] = chunk

    groups = metadata.get("symptom_groups")
    if (
        not isinstance(groups, list)
        or len(groups) != metadata.get("total_symptom_groups")
    ):
        raise ValueError("ABB symptom-group counts do not match.")
    symptom_ids = set()
    for group in groups:
        symptom_id = (
            group.get("symptom_id") if isinstance(group, dict) else None
        )
        if (
            not _nonempty_text(symptom_id)
            or symptom_id in symptom_ids
            or not _nonempty_text(group.get("symptom"))
            or not isinstance(group.get("record_ids"), list)
            or not group["record_ids"]
        ):
            raise ValueError(
                "ABB symptom groups are incomplete or duplicated."
            )
        symptom_ids.add(symptom_id)
        expected_ids = {
            record_id
            for record_id, record in record_by_id.items()
            if record.get("symptom_id") == symptom_id
        }
        if (
            len(group["record_ids"]) != len(set(group["record_ids"]))
            or set(group["record_ids"]) != expected_ids
        ):
            raise ValueError(
                f"ABB symptom-group record links changed: {symptom_id}"
            )

    if set(chunk_by_parent) != set(record_by_id):
        raise ValueError("Some ABB records have no searchable chunk.")

    return context_by_id, chunk_by_parent, groups


def _encode_query_and_symptoms(query, groups):
    with shared_retrieval.EMBEDDING_LOCK:
        query_tokens = shared_retrieval.count_tokens(
            shared_retrieval.QUERY_PREFIX + query,
            shared_retrieval.get_tokenizer(),
        )
        if query_tokens > shared_retrieval.MODEL_TOKEN_LIMIT:
            raise ValueError(
                "Query plus search instruction exceeds 512 tokens. "
                "Shorten the query."
            )
        model = shared_retrieval.get_embedding_model()
        query_vector = shared_retrieval.validate_vectors(
            model.encode(
                [query],
                prompt=shared_retrieval.QUERY_PREFIX,
                batch_size=1,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
            1,
        )[0]
        symptom_vectors = shared_retrieval.validate_vectors(
            model.encode(
                [group["symptom"] for group in groups],
                prompt="",
                batch_size=16,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ),
            len(groups),
        )
    return query_tokens, query_vector, symptom_vectors


def _source_record_result(parent, rank, chunk=None, score=None):
    return {
        "rank": rank,
        "record_id": parent["record_id"],
        "symptom_id": parent["symptom_id"],
        "symptom": parent["symptom"],
        "possible_cause": parent["possible_cause"],
        "manufacturer_guidance": parent["manufacturer_guidance"],
        "page_numbers": list(parent["page_numbers"]),
        "row_number_on_page": parent["row_number_on_page"],
        "symptom_inherited": parent["symptom_inherited"],
        "context_ids": list(parent["context_ids"]),
        "source_cells": deepcopy(parent["source_cells"]),
        "cosine_similarity": (
            None
            if score is None
            else round(float(np.clip(score, -1, 1)), 6)
        ),
        "matched_chunk_id": None if chunk is None else chunk["chunk_id"],
        "matched_chunk_text": None if chunk is None else chunk["text"],
    }


def retrieve_confirmed_abb_symptom(
    vector_store_filename,
    symptom_id,
    top_k=10,
):
    """Return records for an explicitly selected ABB symptom ID only."""
    if (
        not isinstance(symptom_id, str)
        or not symptom_id.strip()
        or len(symptom_id) > 255
        or any(ord(character) < 32 for character in symptom_id)
    ):
        raise ValueError(
            "symptom_id must be a nonempty string of at most 255 characters."
        )
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError("top_k must be an integer between 1 and 10.")
    symptom_id = symptom_id.strip()

    _, metadata, parents = shared_retrieval.load_vector_store(
        vector_store_filename
    )
    context_by_id, _, groups = _validate_abb_metadata(metadata, parents)
    group = next(
        (
            candidate
            for candidate in groups
            if candidate["symptom_id"] == symptom_id
        ),
        None,
    )
    base = {
        "document_id": metadata["document_id"],
        "source_filename": metadata["source_filename"],
        "manufacturer": metadata["manufacturer"],
        "document_reference": metadata["document_reference"],
        "revision": metadata["revision"],
        "mode": "exact_abb_symptom",
        "confirmed_symptom_id": symptom_id,
        "usage": deepcopy(metadata["usage"]),
    }
    if group is None:
        return {
            **base,
            "status": "not_found",
            "selected_symptom_id": None,
            "selected_symptom": None,
            "total_matching_records": 0,
            "has_more": False,
            "results_count": 0,
            "results": [],
            "contexts": [],
            "message": (
                "The symptom ID was not found in this ABB store. "
                "No semantic fallback was used."
            ),
        }

    all_record_ids = list(group["record_ids"])
    chosen_ids = all_record_ids[:top_k]
    results = [
        _source_record_result(parents[record_id], rank)
        for rank, record_id in enumerate(chosen_ids, start=1)
    ]
    used_context_ids = []
    for result in results:
        for context_id in result["context_ids"]:
            if context_id not in used_context_ids:
                used_context_ids.append(context_id)
    return {
        **base,
        "status": "confirmed_selection",
        "selected_symptom_id": group["symptom_id"],
        "selected_symptom": group["symptom"],
        "total_matching_records": len(all_record_ids),
        "has_more": len(all_record_ids) > len(results),
        "results_count": len(results),
        "results": results,
        "contexts": [
            deepcopy(context_by_id[context_id])
            for context_id in used_context_ids
        ],
        "message": (
            "Exact technician-selected ABB symptom; no semantic fallback was used. "
            "Manufacturer records are not confirmed diagnoses, and guidance is "
            "not approved for automatic execution."
        ),
    }


def retrieve_abb_records(vector_store_filename, query, top_k=5):
    """Route by symptom, then rank its complete ABB source records."""
    if not isinstance(query, str) or len(query) > 4000:
        raise ValueError(
            "query must be a string of at most 4000 characters."
        )
    if type(top_k) is not int or not 1 <= top_k <= 10:
        raise ValueError(
            "top_k must be an integer between 1 and 10."
        )
    query = query.strip()
    if not query:
        raise ValueError("Provide a nonempty ABB symptom query.")

    vectors, metadata, parents = (
        shared_retrieval.load_vector_store(vector_store_filename)
    )
    context_by_id, chunk_by_parent, groups = (
        _validate_abb_metadata(metadata, parents)
    )
    query_tokens, query_vector, symptom_vectors = (
        _encode_query_and_symptoms(query, groups)
    )

    record_scores = vectors @ query_vector
    label_scores = symptom_vectors @ query_vector
    record_index = {
        chunk["record_id"]: index
        for index, chunk in enumerate(metadata["chunks"])
    }

    routing = []
    for group_index, group in enumerate(groups):
        group_indices = [
            record_index[record_id]
            for record_id in group["record_ids"]
        ]
        maximum_record_score = max(
            float(record_scores[index])
            for index in group_indices
        )
        label_score = float(label_scores[group_index])
        routing.append(
            {
                "symptom_id": group["symptom_id"],
                "symptom": group["symptom"],
                "record_ids": list(group["record_ids"]),
                "label_cosine_similarity": label_score,
                "maximum_record_cosine_similarity": (
                    maximum_record_score
                ),
                "routing_score": (
                    LABEL_WEIGHT * label_score
                    + RECORD_WEIGHT * maximum_record_score
                ),
            }
        )

    routing.sort(key=lambda item: -item["routing_score"])
    selected = routing[0]
    routing_margin = (
        float(selected["routing_score"] - routing[1]["routing_score"])
        if len(routing) > 1
        else 1.0
    )
    needs_clarification = routing_margin < AMBIGUITY_MARGIN
    selected_records = []
    if not needs_clarification:
        selected_records = sorted(
            selected["record_ids"],
            key=lambda record_id: -float(
                record_scores[record_index[record_id]]
            ),
        )[:top_k]

    results = []
    used_context_ids = []

    for rank, record_id in enumerate(selected_records, start=1):
        parent = parents[record_id]
        chunk = chunk_by_parent[record_id]
        context_ids = list(parent["context_ids"])

        for context_id in context_ids:
            if context_id not in used_context_ids:
                used_context_ids.append(context_id)

        results.append(
            _source_record_result(
                parent,
                rank,
                chunk=chunk,
                score=record_scores[record_index[record_id]],
            )
        )

    symptom_candidates = []
    for rank, item in enumerate(routing[:3], start=1):
        symptom_candidates.append(
            {
                "rank": rank,
                "symptom_id": item["symptom_id"],
                "symptom": item["symptom"],
                "label_cosine_similarity": round(
                    float(
                        np.clip(
                            item["label_cosine_similarity"],
                            -1,
                            1,
                        )
                    ),
                    6,
                ),
                "maximum_record_cosine_similarity": round(
                    float(
                        np.clip(
                            item["maximum_record_cosine_similarity"],
                            -1,
                            1,
                        )
                    ),
                    6,
                ),
                "routing_score": round(
                    float(item["routing_score"]),
                    6,
                ),
            }
        )

    return {
        "document_id": metadata["document_id"],
        "source_filename": metadata["source_filename"],
        "manufacturer": metadata["manufacturer"],
        "document_reference": metadata["document_reference"],
        "revision": metadata["revision"],
        "query": query,
        "mode": "abb_symptom_routed_records",
        "status": (
            "needs_clarification"
            if needs_clarification
            else "candidates"
        ),
        "query_tokens": query_tokens,
        "routing_margin": round(routing_margin, 6),
        "ambiguity_margin": AMBIGUITY_MARGIN,
        "selected_symptom_id": (
            None if needs_clarification else selected["symptom_id"]
        ),
        "selected_symptom": (
            None if needs_clarification else selected["symptom"]
        ),
        "symptom_candidates": symptom_candidates,
        "clarification": (
            {
                "required": True,
                "reason": (
                    "The leading symptom candidates are too close to "
                    "select one safely from this description."
                ),
                "question": (
                    "Which candidate best matches the observed motor behavior?"
                ),
                "options": [
                    {
                        "symptom_id": item["symptom_id"],
                        "symptom": item["symptom"],
                    }
                    for item in symptom_candidates
                ],
            }
            if needs_clarification
            else {"required": False}
        ),
        "message": (
            (
                "Clarification is required before returning a single "
                "symptom group's causes or guidance."
                if needs_clarification
                else "The selected symptom and ranked manufacturer records "
                "are retrieval candidates, not confirmed diagnoses."
            )
            + " Routing and similarity scores are not confidence, and "
            "guidance is not approved for automatic execution."
        ),
        "usage": deepcopy(metadata["usage"]),
        "results_count": len(results),
        "results": results,
        "contexts": [
            deepcopy(context_by_id[context_id])
            for context_id in used_context_ids
        ],
    }
