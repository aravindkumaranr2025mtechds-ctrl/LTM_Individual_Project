"""Prepare token-safe text for embeddings; do not generate vectors yet."""

import json
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNKED_DIRECTORY = PROJECT_ROOT / "data" / "chunked_documents"
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "embedding_documents"
MODEL_DIRECTORY = PROJECT_ROOT / "models" / "bge-small-en-v1.5"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
MODEL_TOKEN_LIMIT = 512


@lru_cache(maxsize=1)
def get_tokenizer():
    from transformers import AutoTokenizer

    settings = json.loads(
        (MODEL_DIRECTORY / "sentence_bert_config.json").read_text(encoding="utf-8")
    )
    if settings.get("max_seq_length") != MODEL_TOKEN_LIMIT:
        raise ValueError("The local model's token limit has changed. Review settings.")
    tokenizer = AutoTokenizer.from_pretrained(
        str(MODEL_DIRECTORY), local_files_only=True,
        trust_remote_code=False, use_fast=True,
    )
    if not tokenizer.is_fast:
        raise ValueError("A fast tokenizer is required for character offsets.")
    return tokenizer


def count_tokens(text, tokenizer):
    return len(tokenizer.encode(
        text, add_special_tokens=True, truncation=False, verbose=False,
    ))


def split_text(text, tokenizer, max_tokens, overlap_tokens):
    """Return original-text spans; token counts include special tokens."""
    token_count = count_tokens(text, tokenizer)
    if token_count <= max_tokens:
        return [(0, len(text), token_count)]

    encoded = tokenizer(
        text, add_special_tokens=False, truncation=False,
        return_offsets_mapping=True, verbose=False,
    )
    offsets = encoded["offset_mapping"]
    if not offsets or any(
        not (0 <= left < right <= len(text)) for left, right in offsets
    ) or any(a[0] >= b[0] for a, b in zip(offsets, offsets[1:])):
        raise ValueError("Unsupported token offsets; cannot safely split this text.")

    budget = max_tokens - tokenizer.num_special_tokens_to_add(pair=False)
    spans = []
    start = 0
    while start < len(offsets):
        end = min(start + budget, len(offsets))
        char_start = 0 if start == 0 else offsets[start][0]

        # Re-tokenize each slice: cutting a word can change its tokenization.
        while end > start:
            char_end = len(text) if end == len(offsets) else offsets[end][0]
            token_count = count_tokens(text[char_start:char_end], tokenizer)
            if token_count <= max_tokens:
                break
            end -= 1
        if end == start:
            raise ValueError("Cannot fit a text segment within the token limit.")

        spans.append((char_start, char_end, token_count))
        if end == len(offsets):
            break
        # Overlap uses tokens from the source text; always make progress.
        start = max(start + 1, end - overlap_tokens)
    return spans


def build_prepared_document(document, tokenizer, max_tokens=512, overlap_tokens=48):
    if type(max_tokens) is not int or not 8 <= max_tokens <= MODEL_TOKEN_LIMIT:
        raise ValueError("max_tokens must be an integer between 8 and 512.")
    budget = max_tokens - tokenizer.num_special_tokens_to_add(pair=False)
    if budget <= 0 or type(overlap_tokens) is not int or not 0 <= overlap_tokens < budget:
        raise ValueError("overlap_tokens must be smaller than the content-token budget.")
    if not isinstance(document, dict):
        raise ValueError("The chunked document must be a JSON object.")
    for key in ("document_id", "source_filename"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise ValueError(f"Missing or invalid {key}.")
    parents, chunks = document.get("parents"), document.get("chunks")
    if not isinstance(parents, list) or not parents or not isinstance(chunks, list) or not chunks:
        raise ValueError("The document must contain nonempty parents and chunks lists.")

    parent_ids = set()
    for parent in parents:
        parent_id = parent.get("parent_id") if isinstance(parent, dict) else None
        if not isinstance(parent_id, str) or not parent_id.strip() or parent_id in parent_ids:
            raise ValueError("Missing or duplicate parent_id.")
        parent_ids.add(parent_id)

    source_ids, output_ids = set(), set()
    prepared, oversized = [], 0
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("Every chunk must be a JSON object.")
        chunk_id, text = chunk.get("chunk_id"), chunk.get("text")
        if not isinstance(chunk_id, str) or not chunk_id.strip() or chunk_id in source_ids:
            raise ValueError("Missing or duplicate source chunk_id.")
        source_ids.add(chunk_id)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Empty or invalid text in {chunk_id}.")
        if not isinstance(chunk.get("parent_id"), str) or chunk["parent_id"] not in parent_ids:
            raise ValueError(f"Missing parent for {chunk_id}.")
        for key in ("document_id", "source_filename"):
            if chunk.get(key) != document[key]:
                raise ValueError(f"Mismatched {key} in {chunk_id}.")
        pages = chunk.get("page_numbers")
        if not isinstance(pages, list) or not pages or any(type(p) is not int or p < 1 for p in pages):
            raise ValueError(f"Invalid page_numbers in {chunk_id}.")

        spans = split_text(text, tokenizer, max_tokens, overlap_tokens)
        oversized += len(spans) > 1
        for part, (start, end, token_count) in enumerate(spans, start=1):
            new_id = chunk_id if len(spans) == 1 else f"{chunk_id}_t{part:03d}"
            if new_id in output_ids:
                raise ValueError(f"Duplicate prepared chunk_id: {new_id}")
            output_ids.add(new_id)
            prepared.append({
                **chunk,
                "chunk_id": new_id,
                "source_chunk_id": chunk_id,
                "text": text[start:end],
                "word_count": len(text[start:end].split()),
                "token_count": token_count,
                "source_char_start": start,
                "source_char_end": end,
                "split_index": part,
                "split_count": len(spans),
                "page_numbers_scope": "source_chunk",
            })

    return {
        **document,
        "total_chunks": len(prepared),
        "chunks": prepared,
        "preparation": {
            "strategy": "token_safe_original_spans_v1",
            "embedding_model": MODEL_NAME,
            "max_tokens": max_tokens,
            "overlap_tokens": overlap_tokens,
            "overlap_basis": "source_text_tokens",
            "token_counts_include_special_tokens": True,
            "input_chunks": len(chunks),
            "oversized_input_chunks": oversized,
            "output_chunks": len(prepared),
            "maximum_output_tokens": max(c["token_count"] for c in prepared),
        },
    }


def prepare_embedding_document(chunked_filename, max_tokens=512, overlap_tokens=48):
    """Save a separate embedding-ready JSON; never overwrite an existing file."""
    if (
        not isinstance(chunked_filename, str)
        or any(c in chunked_filename for c in '/\\:\x00')
        or Path(chunked_filename).suffix.lower() != ".json"
    ):
        raise ValueError("Provide only the chunked JSON filename, not a folder path.")
    input_path = (CHUNKED_DIRECTORY / chunked_filename).resolve()
    if input_path.parent != CHUNKED_DIRECTORY.resolve():
        raise ValueError("The input must be inside chunked_documents.")
    if not input_path.is_file():
        raise FileNotFoundError("Document not found in chunked_documents.")

    output_path = OUTPUT_DIRECTORY / f"{Path(chunked_filename).stem}_ready.json"
    if output_path.exists():
        raise FileExistsError(f"Prepared file already exists: {output_path.name}")
    document = json.loads(input_path.read_text(encoding="utf-8"))
    result = build_prepared_document(document, get_tokenizer(), max_tokens, overlap_tokens)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    handle = output_path.open("x", encoding="utf-8")
    try:
        with handle:
            handle.write(payload)
    except BaseException:
        output_path.unlink(missing_ok=True)  # Remove only our incomplete new output.
        raise

    return {
        "document_id": result["document_id"],
        **result["preparation"],
        "prepared_filename": output_path.name,
        "saved_location": str(output_path),
    }