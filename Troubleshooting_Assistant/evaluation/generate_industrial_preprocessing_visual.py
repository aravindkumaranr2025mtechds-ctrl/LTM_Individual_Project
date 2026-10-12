"""Generate one PPT-ready industrial preprocessing visualization.

The figure compares actual Siemens raw PDF page sizes with the final
semantic retrieval chunks and displays data-integrity evidence.

This script is read-only with respect to project source data.
"""

from pathlib import Path
from statistics import median
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
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
    / "industrial_preprocessing_before_after.png"
)

OUTPUT_METRICS = (
    OUTPUT_DIR
    / "industrial_preprocessing_metrics.json"
)


TEXT_KEYS = {
    "text",
    "content",
    "chunk_text",
    "embedding_text",
    "section_text",
    "source_text",
}


def load_pdf_page_lengths():

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

    preferred = [
        "chunks",
        "records",
        "sections",
        "items",
        "data",
        "documents",
    ]

    for key in preferred:

        candidate = data.get(
            key
        )

        if isinstance(
            candidate,
            list,
        ):
            return candidate

    candidates = [
        value
        for value
        in data.values()
        if isinstance(
            value,
            list,
        )
    ]

    if not candidates:

        raise RuntimeError(
            "No processed record list found."
        )

    return max(
        candidates,
        key=len,
    )


def extract_record_text(
    record,
):

    values = []

    def walk(value):

        if isinstance(
            value,
            dict,
        ):

            for key, child in (
                value.items()
            ):

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

    # Remove repeated identical fields
    # inside the same record.
    values = list(
        dict.fromkeys(
            values
        )
    )

    return "\n".join(
        values
    )


# -------------------------------------------------
# LOAD REAL PROJECT DATA
# -------------------------------------------------

raw_lengths = (
    load_pdf_page_lengths()
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

    embeddings = archive[
        "embeddings"
    ]

    chunk_ids = archive[
        "chunk_ids"
    ]

    embedding_rows = int(
        embeddings.shape[0]
    )

    embedding_dimensions = int(
        embeddings.shape[1]
    )

    chunk_id_rows = int(
        chunk_ids.shape[0]
    )


vector_mismatch = abs(
    len(records)
    - embedding_rows
)


# -------------------------------------------------
# STATISTICS
# -------------------------------------------------

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


raw_mean = float(
    np.mean(
        raw_lengths
    )
)

processed_mean = float(
    np.mean(
        processed_lengths
    )
)


raw_max = int(
    max(
        raw_lengths
    )
)

processed_max = int(
    max(
        processed_lengths
    )
)


median_reduction = (
    (
        raw_median
        - processed_median
    )
    / raw_median
    * 100
)


maximum_reduction = (
    (
        raw_max
        - processed_max
    )
    / raw_max
    * 100
)


alignment_percent = (
    min(
        len(records),
        embedding_rows,
    )
    / max(
        len(records),
        embedding_rows,
    )
    * 100
)


# -------------------------------------------------
# DATAFRAME FOR SEABORN
# -------------------------------------------------

raw_label = (
    f"Before preprocessing\n"
    f"Raw PDF pages (n={len(raw_lengths):,})"
)

processed_label = (
    f"After preprocessing\n"
    f"Semantic chunks (n={len(processed_lengths):,})"
)


df = pd.DataFrame(
    {
        "Characters": (
            raw_lengths
            + processed_lengths
        ),

        "Stage": (
            [
                raw_label
            ]
            * len(
                raw_lengths
            )
            +
            [
                processed_label
            ]
            * len(
                processed_lengths
            )
        ),
    }
)


# -------------------------------------------------
# INDUSTRIAL PPT VISUAL
# -------------------------------------------------

sns.set_theme(
    style="whitegrid",
    context="talk",
)


fig, ax = plt.subplots(
    figsize=(
        12.8,
        7.2,
    )
)


palette = {
    raw_label:
        "#576574",

    processed_label:
        "#138D90",
}


# Main statistical distribution.
sns.violinplot(
    data=df,
    y="Stage",
    x="Characters",
    hue="Stage",
    palette=palette,
    inner=None,
    cut=0,
    density_norm="width",
    linewidth=1.2,
    saturation=0.85,
    legend=False,
    ax=ax,
)


# Embedded box plot:
# median + interquartile range.
sns.boxplot(
    data=df,
    y="Stage",
    x="Characters",
    hue="Stage",
    palette=palette,
    width=0.16,
    showfliers=False,
    linewidth=1.5,
    legend=False,
    boxprops={
        "alpha":
            0.75
    },
    ax=ax,
)


# Median markers.
ax.scatter(
    [
        raw_median
    ],
    [
        0
    ],
    s=90,
    marker="D",
    color="white",
    edgecolor="black",
    linewidth=1.3,
    zorder=10,
)


ax.scatter(
    [
        processed_median
    ],
    [
        1
    ],
    s=90,
    marker="D",
    color="white",
    edgecolor="black",
    linewidth=1.3,
    zorder=10,
)


# Median labels.
ax.annotate(
    (
        f"Median = "
        f"{raw_median:,.0f}"
    ),
    xy=(
        raw_median,
        0,
    ),
    xytext=(
        raw_median + 350,
        -0.22,
    ),
    fontsize=11,
    fontweight="bold",
    arrowprops={
        "arrowstyle":
            "->",

        "linewidth":
            1.2,
    },
)


ax.annotate(
    (
        f"Median = "
        f"{processed_median:,.0f}"
    ),
    xy=(
        processed_median,
        1,
    ),
    xytext=(
        processed_median + 650,
        1.18,
    ),
    fontsize=11,
    fontweight="bold",
    arrowprops={
        "arrowstyle":
            "->",

        "linewidth":
            1.2,
    },
)


# -------------------------------------------------
# MAIN INSIGHT CALLOUT
# -------------------------------------------------

insight = (
    "PREPROCESSING IMPACT\n"
    f"Median retrieval-unit size reduced "
    f"by {median_reduction:.1f}%\n"
    f"{raw_median:,.0f} ? "
    f"{processed_median:,.0f} characters"
)


ax.text(
    0.985,
    0.955,
    insight,
    transform=ax.transAxes,
    ha="right",
    va="top",
    fontsize=12,
    fontweight="bold",
    bbox={
        "boxstyle":
            "round,pad=0.7",

        "facecolor":
            "#EEF4F5",

        "edgecolor":
            "#AAB7B8",

        "linewidth":
            1.2,
    },
)


# -------------------------------------------------
# DATA QUALITY / VECTOR INTEGRITY
# -------------------------------------------------

quality_summary = (
    "POST-PREPROCESSING DATA QUALITY\n"
    f"Empty chunks: {empty_chunks}    |    "
    f"Duplicate chunks: {duplicate_chunks}\n"
    f"Chunk ? embedding alignment: "
    f"{alignment_percent:.0f}%    |    "
    f"Vector mismatch: {vector_mismatch}\n"
    f"Embedding matrix: "
    f"{embedding_rows:,} ? "
    f"{embedding_dimensions}"
)


ax.text(
    0.985,
    0.055,
    quality_summary,
    transform=ax.transAxes,
    ha="right",
    va="bottom",
    fontsize=10.8,
    bbox={
        "boxstyle":
            "round,pad=0.65",

        "facecolor":
            "#F7F8F8",

        "edgecolor":
            "#CCD1D1",

        "linewidth":
            1,
    },
)


# -------------------------------------------------
# LABELS
# -------------------------------------------------

ax.set_title(
    "Industrial Knowledge Preprocessing: Before vs After",
    fontsize=21,
    fontweight="bold",
    pad=18,
)


fig.text(
    0.5,
    0.925,
    (
        "Siemens diagnostics manual transformed "
        "from page-level text into controlled "
        "semantic retrieval units"
    ),
    ha="center",
    fontsize=11.5,
)


ax.set_xlabel(
    "Text size per retrieval unit (characters)",
    fontsize=13,
)

ax.set_ylabel(
    ""
)


ax.tick_params(
    axis="y",
    labelsize=12,
)


# Highlight useful range.
ax.axvline(
    processed_max,
    linestyle="--",
    linewidth=1.1,
    color="#707B7C",
    alpha=0.75,
)


ax.text(
    processed_max + 35,
    0.53,
    (
        "Maximum processed\n"
        f"chunk = {processed_max:,}"
    ),
    fontsize=9.5,
    color="#566573",
)


sns.despine(
    ax=ax,
    left=True,
)


fig.text(
    0.5,
    0.015,
    (
        "Interpretation: preprocessing created smaller, "
        "more controlled retrieval units while preserving "
        "one-to-one vector-index integrity."
    ),
    ha="center",
    fontsize=10,
)


plt.tight_layout(
    rect=[
        0.03,
        0.07,
        0.98,
        0.91,
    ]
)


plt.savefig(
    OUTPUT_PNG,
    dpi=300,
    bbox_inches="tight",
)


plt.close(
    fig
)


# -------------------------------------------------
# SAVE REPRODUCIBLE METRICS
# -------------------------------------------------

metrics = {
    "raw_pdf_pages":
        len(
            raw_lengths
        ),

    "processed_semantic_chunks":
        len(
            processed_lengths
        ),

    "raw_median_characters":
        raw_median,

    "processed_median_characters":
        processed_median,

    "median_size_reduction_percent":
        round(
            median_reduction,
            2,
        ),

    "raw_mean_characters":
        round(
            raw_mean,
            2,
        ),

    "processed_mean_characters":
        round(
            processed_mean,
            2,
        ),

    "raw_max_characters":
        raw_max,

    "processed_max_characters":
        processed_max,

    "maximum_size_reduction_percent":
        round(
            maximum_reduction,
            2,
        ),

    "empty_processed_chunks":
        empty_chunks,

    "duplicate_processed_chunks":
        duplicate_chunks,

    "processed_record_count":
        len(
            records
        ),

    "embedding_rows":
        embedding_rows,

    "chunk_id_rows":
        chunk_id_rows,

    "embedding_dimensions":
        embedding_dimensions,

    "vector_count_mismatch":
        vector_mismatch,

    "chunk_embedding_alignment_percent":
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
    "========== INDUSTRIAL PREPROCESSING VISUAL =========="
)

print(
    "Raw PDF pages:",
    len(
        raw_lengths
    )
)

print(
    "Processed chunks:",
    len(
        processed_lengths
    )
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
    "Median reduction:",
    f"{median_reduction:.2f}%"
)

print(
    "Raw maximum:",
    raw_max
)

print(
    "Processed maximum:",
    processed_max
)

print(
    "Maximum reduction:",
    f"{maximum_reduction:.2f}%"
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
    "Embedding rows:",
    embedding_rows
)

print(
    "Vector mismatch:",
    vector_mismatch
)

print(
    "Chunk-vector alignment:",
    f"{alignment_percent:.2f}%"
)

print()
print(
    "PPT figure:"
)

print(
    OUTPUT_PNG.relative_to(
        ROOT
    )
)

print()
print(
    "Metrics:"
)

print(
    OUTPUT_METRICS.relative_to(
        ROOT
    )
)

print()
print(
    "INDUSTRIAL PREPROCESSING VISUAL: COMPLETE"
)


if __name__ == "__main__":
    pass
