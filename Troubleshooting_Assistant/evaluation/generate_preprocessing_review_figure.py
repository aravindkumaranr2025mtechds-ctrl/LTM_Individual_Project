"""Generate one PPT-ready preprocessing comparison figure.

This script compares the canonical Siemens raw PDF pages with
the final embedding-ready semantic chunks.

It does not modify source data.
"""

from pathlib import Path
from statistics import median
import json

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]

RAW = (
    ROOT
    / "data"
    / "raw_documents"
    / (
        "212022f0a2614a7b839cc827522c6651_"
        "MC_diagnostics_man_0724_en-US.pdf"
    )
)

PROCESSED = (
    ROOT
    / "data"
    / "embedding_documents"
    / (
        "212022f0a2614a7b839cc827522c6651_"
        "MC_diagnostics_man_0724_en-US_chunks_ready.json"
    )
)

VECTOR = (
    ROOT
    / "data"
    / "vector_store"
    / (
        "212022f0a2614a7b839cc827522c6651_"
        "MC_diagnostics_man_0724_en-US_chunks_ready_bge_small.npz"
    )
)

OUTPUT_DIR = (
    ROOT
    / "evaluation"
    / "dataset_visualization"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT = (
    OUTPUT_DIR
    / "review_preprocessing_before_after.png"
)

METRICS_OUTPUT = (
    OUTPUT_DIR
    / "review_preprocessing_metrics.json"
)


TEXT_KEYS = {
    "text",
    "content",
    "chunk_text",
    "embedding_text",
    "section_text",
    "source_text",
}


def read_pdf_lengths():

    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader

    reader = PdfReader(
        str(RAW)
    )

    lengths = []

    for page in reader.pages:

        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        if text.strip():
            lengths.append(
                len(text)
            )

    return lengths


def find_records(data):

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        raise RuntimeError(
            "Unexpected processed JSON structure."
        )

    for key in [
        "chunks",
        "records",
        "sections",
        "items",
        "data",
        "documents",
    ]:

        value = data.get(key)

        if isinstance(value, list):
            return value

    lists = [
        value
        for value in data.values()
        if isinstance(value, list)
    ]

    if not lists:
        raise RuntimeError(
            "Could not identify processed records."
        )

    return max(
        lists,
        key=len,
    )


def record_text(record):

    found = []

    def walk(value):

        if isinstance(value, dict):

            for key, child in value.items():

                if (
                    key.lower() in TEXT_KEYS
                    and isinstance(child, str)
                    and child.strip()
                ):
                    found.append(
                        child.strip()
                    )
                else:
                    walk(child)

        elif isinstance(value, list):

            for child in value:
                walk(child)

    walk(record)

    # Remove identical repeated fields inside one record.
    return "\n".join(
        dict.fromkeys(found)
    )


raw_lengths = read_pdf_lengths()

with PROCESSED.open(
    "r",
    encoding="utf-8-sig",
) as handle:

    processed_data = json.load(
        handle
    )


records = find_records(
    processed_data
)

texts = [
    record_text(record)
    for record in records
]

processed_lengths = [
    len(text)
    for text in texts
    if text
]


empty_records = sum(
    1
    for text in texts
    if not text
)

usable_texts = [
    text
    for text in texts
    if text
]

duplicate_records = (
    len(usable_texts)
    - len(set(usable_texts))
)


import numpy as np

with np.load(
    VECTOR,
    allow_pickle=False,
) as archive:

    embedding_rows = int(
        archive["embeddings"].shape[0]
    )

    embedding_dimensions = int(
        archive["embeddings"].shape[1]
    )


raw_median = median(
    raw_lengths
)

processed_median = median(
    processed_lengths
)

raw_max = max(
    raw_lengths
)

processed_max = max(
    processed_lengths
)


median_reduction = (
    100
    * (
        raw_median
        - processed_median
    )
    / raw_median
)

max_reduction = (
    100
    * (
        raw_max
        - processed_max
    )
    / raw_max
)


labels = [
    "Median text size",
    "Maximum text size",
]

before = [
    raw_median,
    raw_max,
]

after = [
    processed_median,
    processed_max,
]


x = np.arange(
    len(labels)
)

width = 0.34


fig, ax = plt.subplots(
    figsize=(11, 6.5)
)


before_bars = ax.bar(
    x - width / 2,
    before,
    width,
    label="Before: raw PDF pages",
)

after_bars = ax.bar(
    x + width / 2,
    after,
    width,
    label="After: semantic chunks",
)


ax.set_title(
    "Impact of Preprocessing on Retrieval-Unit Size",
    fontsize=18,
    pad=18,
)

ax.set_ylabel(
    "Characters per retrieval unit"
)

ax.set_xticks(
    x
)

ax.set_xticklabels(
    labels
)

ax.legend()


for bar in before_bars:

    value = bar.get_height()

    ax.text(
        bar.get_x()
        + bar.get_width() / 2,
        value,
        f"{value:,.1f}",
        ha="center",
        va="bottom",
        fontsize=10,
    )


for index, bar in enumerate(
    after_bars
):

    value = bar.get_height()

    reduction = (
        median_reduction
        if index == 0
        else max_reduction
    )

    ax.text(
        bar.get_x()
        + bar.get_width() / 2,
        value,
        (
            f"{value:,.1f}\n"
            f"? {reduction:.1f}%"
        ),
        ha="center",
        va="bottom",
        fontsize=10,
    )


quality_note = (
    f"Processed quality: "
    f"{len(records):,} chunks | "
    f"{empty_records} empty | "
    f"{duplicate_records} duplicates | "
    f"{embedding_rows:,} embeddings | "
    f"{embedding_dimensions}-D vectors"
)


fig.text(
    0.5,
    0.02,
    quality_note,
    ha="center",
    fontsize=10,
)


fig.text(
    0.5,
    0.955,
    (
        "Raw unit = PDF page    ?    "
        "Processed unit = semantic retrieval chunk"
    ),
    ha="center",
    fontsize=10,
)


plt.tight_layout(
    rect=[
        0,
        0.06,
        1,
        0.93,
    ]
)

plt.savefig(
    OUTPUT,
    dpi=220,
    bbox_inches="tight",
)

plt.close()


metrics = {
    "raw_pages":
        len(raw_lengths),

    "processed_chunks":
        len(records),

    "raw_median_characters":
        raw_median,

    "processed_median_characters":
        processed_median,

    "median_reduction_percent":
        round(
            median_reduction,
            2,
        ),

    "raw_max_characters":
        raw_max,

    "processed_max_characters":
        processed_max,

    "max_reduction_percent":
        round(
            max_reduction,
            2,
        ),

    "empty_processed_chunks":
        empty_records,

    "duplicate_processed_chunks":
        duplicate_records,

    "embedding_rows":
        embedding_rows,

    "embedding_dimensions":
        embedding_dimensions,

    "vector_count_mismatch":
        abs(
            len(records)
            - embedding_rows
        ),
}


METRICS_OUTPUT.write_text(
    json.dumps(
        metrics,
        indent=2,
    ),
    encoding="utf-8",
    newline="\n",
)


print()
print(
    "========== PPT PREPROCESSING FIGURE =========="
)

for key, value in metrics.items():
    print(
        f"{key}: {value}"
    )

print()
print(
    "Chart:",
    OUTPUT.relative_to(ROOT)
)

print(
    "Metrics:",
    METRICS_OUTPUT.relative_to(ROOT)
)

print()
print(
    "PPT PREPROCESSING FIGURE: COMPLETE"
)
