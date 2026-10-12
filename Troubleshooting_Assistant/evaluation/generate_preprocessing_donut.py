"""Generate one industrial PPT-ready preprocessing donut chart.

The figure compares the median text size of the raw Siemens PDF pages
with the final semantic retrieval chunks.

All values are calculated from the real project files.
No source data is modified.
"""

from pathlib import Path
from statistics import median
import json

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]

RAW_PDF = (
    ROOT
    / "data"
    / "raw_documents"
    / (
        "212022f0a2614a7b839cc827522c6651_"
        "MC_diagnostics_man_0724_en-US.pdf"
    )
)

PROCESSED_JSON = (
    ROOT
    / "data"
    / "embedding_documents"
    / (
        "212022f0a2614a7b839cc827522c6651_"
        "MC_diagnostics_man_0724_en-US_chunks_ready.json"
    )
)

VECTOR_STORE = (
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

OUTPUT_PNG = (
    OUTPUT_DIR
    / "ppt_preprocessing_donut.png"
)

OUTPUT_METRICS = (
    OUTPUT_DIR
    / "ppt_preprocessing_donut_metrics.json"
)


TEXT_KEYS = {
    "text",
    "content",
    "chunk_text",
    "embedding_text",
    "section_text",
    "source_text",
}


def load_raw_page_lengths():

    try:
        from pypdf import PdfReader

    except ImportError:
        from PyPDF2 import PdfReader

    reader = PdfReader(
        str(RAW_PDF)
    )

    lengths = []

    for page in reader.pages:

        try:
            text = (
                page.extract_text()
                or ""
            )

        except Exception:
            text = ""

        if text.strip():

            lengths.append(
                len(text)
            )

    return lengths


def find_records(data):

    if isinstance(
        data,
        list,
    ):
        return data

    if not isinstance(
        data,
        dict,
    ):
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

        candidate = data.get(
            key
        )

        if isinstance(
            candidate,
            list,
        ):
            return candidate

    candidate_lists = [
        value
        for value
        in data.values()
        if isinstance(
            value,
            list,
        )
    ]

    if not candidate_lists:

        raise RuntimeError(
            "Processed record list was not found."
        )

    return max(
        candidate_lists,
        key=len,
    )


def extract_record_text(record):

    values = []

    def walk(value):

        if isinstance(
            value,
            dict,
        ):

            for key, child in value.items():

                if (
                    key.lower()
                    in TEXT_KEYS
                    and isinstance(
                        child,
                        str,
                    )
                    and child.strip()
                ):

                    values.append(
                        child.strip()
                    )

                else:
                    walk(
                        child
                    )

        elif isinstance(
            value,
            list,
        ):

            for child in value:

                walk(
                    child
                )

    walk(
        record
    )

    # Remove repeated identical text inside a record.
    values = list(
        dict.fromkeys(
            values
        )
    )

    return "\n".join(
        values
    )


# -------------------------------------------
# LOAD REAL DATA
# -------------------------------------------

raw_lengths = (
    load_raw_page_lengths()
)


with PROCESSED_JSON.open(
    "r",
    encoding="utf-8-sig",
) as handle:

    processed_data = json.load(
        handle
    )


records = find_records(
    processed_data
)


processed_texts = [
    extract_record_text(
        record
    )
    for record
    in records
]


processed_lengths = [
    len(text)
    for text
    in processed_texts
    if text
]


empty_chunks = sum(
    1
    for text
    in processed_texts
    if not text
)


usable_texts = [
    text
    for text
    in processed_texts
    if text
]


duplicate_chunks = (
    len(usable_texts)
    - len(
        set(
            usable_texts
        )
    )
)


with np.load(
    VECTOR_STORE,
    allow_pickle=False,
) as archive:

    embedding_rows = int(
        archive[
            "embeddings"
        ].shape[0]
    )

    embedding_dimensions = int(
        archive[
            "embeddings"
        ].shape[1]
    )

    chunk_id_rows = int(
        archive[
            "chunk_ids"
        ].shape[0]
    )


# -------------------------------------------
# CALCULATE BEFORE / AFTER
# -------------------------------------------

raw_median = float(
    median(
        raw_lengths
    )
)

processed_median = float(
    median(
        processed_lengths
    )
)


reduction_percent = (
    (
        raw_median
        - processed_median
    )
    / raw_median
    * 100
)


remaining_percent = (
    processed_median
    / raw_median
    * 100
)


vector_mismatch = abs(
    len(records)
    - embedding_rows
)


alignment_percent = (
    min(
        len(records),
        embedding_rows,
    )
    /
    max(
        len(records),
        embedding_rows,
    )
    * 100
)


# -------------------------------------------
# INDUSTRIAL VISUAL STYLE
# -------------------------------------------

sns.set_theme(
    context="talk",
    style="white",
)


fig, ax = plt.subplots(
    figsize=(
        11.5,
        7.2,
    )
)


# Industrial palette.
reduction_color = "#147D92"
remaining_color = "#DDE4E8"


wedges, _ = ax.pie(
    [
        reduction_percent,
        remaining_percent,
    ],

    startangle=90,

    counterclock=False,

    colors=[
        reduction_color,
        remaining_color,
    ],

    wedgeprops={
        "width":
            0.28,

        "edgecolor":
            "white",

        "linewidth":
            3,
    },
)


# -------------------------------------------
# DONUT CENTRE
# -------------------------------------------

ax.text(
    0,
    0.20,
    f"{reduction_percent:.1f}%",
    ha="center",
    va="center",
    fontsize=34,
    fontweight="bold",
    color="#17324D",
)


ax.text(
    0,
    -0.03,
    "REDUCTION",
    ha="center",
    va="center",
    fontsize=14,
    fontweight="bold",
    color="#147D92",
)


ax.text(
    0,
    -0.20,
    "in median text size",
    ha="center",
    va="center",
    fontsize=11,
    color="#62727B",
)


# -------------------------------------------
# BEFORE / AFTER VALUES
# -------------------------------------------

ax.text(
    -1.43,
    0.35,
    "BEFORE",
    ha="center",
    fontsize=13,
    fontweight="bold",
    color="#5D6D7E",
)


ax.text(
    -1.43,
    0.08,
    f"{raw_median:,.0f}",
    ha="center",
    fontsize=24,
    fontweight="bold",
    color="#17324D",
)


ax.text(
    -1.43,
    -0.13,
    "characters",
    ha="center",
    fontsize=10,
    color="#7B8A93",
)


ax.text(
    -1.43,
    -0.32,
    "Raw PDF page",
    ha="center",
    fontsize=10,
    color="#7B8A93",
)


ax.text(
    1.43,
    0.35,
    "AFTER",
    ha="center",
    fontsize=13,
    fontweight="bold",
    color="#147D92",
)


ax.text(
    1.43,
    0.08,
    f"{processed_median:,.0f}",
    ha="center",
    fontsize=24,
    fontweight="bold",
    color="#17324D",
)


ax.text(
    1.43,
    -0.13,
    "characters",
    ha="center",
    fontsize=10,
    color="#7B8A93",
)


ax.text(
    1.43,
    -0.32,
    "Semantic chunk",
    ha="center",
    fontsize=10,
    color="#7B8A93",
)


# -------------------------------------------
# QUALITY INDICATORS
# -------------------------------------------

quality_text = (
    f"DATA QUALITY AFTER PREPROCESSING\n\n"
    f"Empty chunks                 {empty_chunks}\n"
    f"Duplicate chunks             {duplicate_chunks}\n"
    f"Chunk-vector alignment       {alignment_percent:.0f}%\n"
    f"Vector count mismatch        {vector_mismatch}\n"
    f"Embedding matrix             "
    f"{embedding_rows:,} ? {embedding_dimensions}"
)


fig.text(
    0.50,
    0.095,
    quality_text,
    ha="center",
    va="center",
    fontsize=10.5,
    family="monospace",
    color="#34495E",
    bbox={
        "boxstyle":
            "round,pad=0.8",

        "facecolor":
            "#F6F8F9",

        "edgecolor":
            "#CCD6DB",

        "linewidth":
            1.2,
    },
)


# -------------------------------------------
# TITLE
# -------------------------------------------

fig.suptitle(
    "Industrial Knowledge Preprocessing Impact",
    fontsize=22,
    fontweight="bold",
    y=0.965,
    color="#17324D",
)


fig.text(
    0.5,
    0.905,
    (
        "Siemens diagnostics manual: "
        "raw document pages ? semantic retrieval chunks"
    ),
    ha="center",
    fontsize=11.5,
    color="#62727B",
)


# -------------------------------------------
# DONUT LEGEND
# -------------------------------------------

ax.legend(
    wedges,
    [
        (
            f"Reduced during preprocessing "
            f"({reduction_percent:.1f}%)"
        ),

        (
            f"Relative processed size "
            f"({remaining_percent:.1f}%)"
        ),
    ],

    loc="upper center",

    bbox_to_anchor=(
        0.5,
        -0.02,
    ),

    frameon=False,

    fontsize=10.5,
)


ax.set_aspect(
    "equal"
)


ax.set_xlim(
    -2.0,
    2.0,
)

ax.set_ylim(
    -1.55,
    1.35,
)


plt.tight_layout(
    rect=[
        0.02,
        0.18,
        0.98,
        0.89,
    ]
)


plt.savefig(
    OUTPUT_PNG,
    dpi=300,
    bbox_inches="tight",
    facecolor="white",
)


plt.close(
    fig
)


# -------------------------------------------
# SAVE METRICS
# -------------------------------------------

metrics = {
    "raw_median_characters":
        raw_median,

    "processed_median_characters":
        processed_median,

    "median_reduction_percent":
        round(
            reduction_percent,
            2,
        ),

    "processed_relative_size_percent":
        round(
            remaining_percent,
            2,
        ),

    "processed_chunks":
        len(
            records
        ),

    "empty_chunks":
        empty_chunks,

    "duplicate_chunks":
        duplicate_chunks,

    "embedding_rows":
        embedding_rows,

    "chunk_id_rows":
        chunk_id_rows,

    "embedding_dimensions":
        embedding_dimensions,

    "vector_count_mismatch":
        vector_mismatch,

    "chunk_vector_alignment_percent":
        round(
            alignment_percent,
            2,
        ),
}


OUTPUT_METRICS.write_text(
    json.dumps(
        metrics,
        indent=2,
    ),
    encoding="utf-8",
    newline="\n",
)


print()
print(
    "========== INDUSTRIAL DONUT VISUAL =========="
)

print(
    "Raw median:",
    raw_median
)

print(
    "Processed median:",
    processed_median
)

print(
    "Reduction:",
    f"{reduction_percent:.2f}%"
)

print(
    "Remaining relative size:",
    f"{remaining_percent:.2f}%"
)

print(
    "Processed chunks:",
    len(records)
)

print(
    "Empty chunks:",
    empty_chunks
)

print(
    "Duplicate chunks:",
    duplicate_chunks
)

print(
    "Chunk-vector alignment:",
    f"{alignment_percent:.2f}%"
)

print(
    "Vector mismatch:",
    vector_mismatch
)

print()
print(
    "PPT chart:"
)

print(
    OUTPUT_PNG.relative_to(
        ROOT
    )
)

print()
print(
    "INDUSTRIAL DONUT VISUAL: COMPLETE"
)
