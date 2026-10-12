import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIRECTORY = PROJECT_ROOT / "data" / "processed_documents"
CHUNKED_DIRECTORY = PROJECT_ROOT / "data" / "chunked_documents"
STRATEGY = "siemens_alarm_sections_v2"

ALARM_HEADING = re.compile(r"^(0|[1-9]\d{3,5})\s+(.+)$")
ALARM_FIELD = re.compile(r"^(Parameters|Explanation|Reaction|Remedy):")
SECTION_HEADING = re.compile(r"^\d+(?:\.\d+)+\s+\S")
CHAPTER_NAMES = (
    "Introduction", "Fundamental safety instructions", "Explanation of the alarms",
    "NC alarms", "Cycle alarms", "HMI alarms", "I/O alarms", "PLC alarms",
    "System responses", "Appendix",
)
CHAPTER_HEADING = re.compile(
    r"^(?:" + "|".join(re.escape(name) for name in CHAPTER_NAMES)
    + r")\s+[0-9A-Z]+$"
)
MANUAL_FOOTER = re.compile(r"^(?:\d+\s+)?Diagnostics Manual,.*$")


def heading_key(text: str) -> str:
    """Compare headings consistently, including non-breaking spaces."""
    return " ".join(text.split())


def page_content_lines(text: str) -> list[str]:
    """Remove recognizable footer blocks, not arbitrary numbered body lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    removed = set()

    for index in range(max(0, len(lines) - 3), len(lines)):
        if not MANUAL_FOOTER.fullmatch(heading_key(lines[index])):
            continue

        removed.add(index)
        previous = index - 1
        if previous >= 0 and heading_key(lines[previous]) == "Alarms":
            removed.add(previous)
            previous -= 1

        # A running footer can include a chapter name and subsection heading.
        if (
            previous >= 1
            and SECTION_HEADING.match(heading_key(lines[previous]))
            and heading_key(lines[previous - 1]) in CHAPTER_NAMES
        ):
            removed.update((previous - 1, previous))

    return [line for index, line in enumerate(lines) if index not in removed]


def build_chunks(document: dict, chunk_words: int = 180,
                 overlap_words: int = 30) -> dict:
    """Build full alarm sections and word-based children for this Siemens manual."""
    if type(chunk_words) is not int or not 80 <= chunk_words <= 400:
        raise ValueError("chunk_words must be between 80 and 400.")
    if type(overlap_words) is not int or not 0 <= overlap_words < chunk_words:
        raise ValueError("overlap_words must be smaller than chunk_words.")
    if not isinstance(document, dict):
        raise ValueError("The processed document must be a JSON object.")

    for key in ("document_id", "source_filename"):
        if not isinstance(document.get(key), str) or not document[key].strip():
            raise ValueError(f"Missing or invalid {key}.")


    enterprise_metadata = document.get(
        "enterprise_metadata"
    )

    if (
        enterprise_metadata is not None
        and not isinstance(enterprise_metadata, dict)
    ):
        raise ValueError(
            "enterprise_metadata must be an object or null."
        )

    pages = document.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("The processed document has no pages.")

    parents, chunks, lines = [], [], []
    alarm_number = alarm_title = chapter = subsection = None
    previous_page = 0

    def finish_section():
        if not lines:
            return

        full_title = alarm_title
        if alarm_number is not None:
            title_parts = [alarm_title]
            for line, _ in lines[1:]:
                if ALARM_FIELD.match(line):
                    break
                title_parts.append(line)
            full_title = heading_key(" ".join(title_parts))

        parent_id = f"{document['document_id']}_s{len(parents) + 1:05d}"
        metadata = {
            "document_id": document["document_id"],
            "source_filename": document["source_filename"],
            "enterprise_metadata": (
                dict(enterprise_metadata)
                if enterprise_metadata is not None
                else None
            ),
            "alarm_number": alarm_number,
            "alarm_title": full_title,
        }
        parents.append({
            **metadata,
            "parent_id": parent_id,
            "page_numbers": sorted({page for _, page in lines}),
            "text": "\n".join(line for line, _ in lines),
        })

        words = [(word, page) for line, page in lines for word in line.split()]
        for part, start in enumerate(
            range(0, len(words), chunk_words - overlap_words), start=1
        ):
            window = words[start:start + chunk_words]
            chunks.append({
                **metadata,
                "chunk_id": f"{parent_id}_c{part:03d}",
                "parent_id": parent_id,
                "page_numbers": sorted({page for _, page in window}),
                "word_count": len(window),
                "text": " ".join(word for word, _ in window),
            })
            if start + chunk_words >= len(words):
                break
        lines.clear()

    for page in pages:
        if not isinstance(page, dict):
            raise ValueError("Each page must be an object.")
        page_number, text = page.get("page_number"), page.get("text")
        if type(page_number) is not int or page_number <= previous_page:
            raise ValueError("Page numbers must be positive and increasing.")
        if not isinstance(text, str):
            raise ValueError("Every page must contain a text string.")

        if previous_page and page_number != previous_page + 1:
            finish_section()
            alarm_number = alarm_title = chapter = subsection = None
        previous_page = page_number
        page_lines = page_content_lines(text)

        for index, line in enumerate(page_lines):
            key = heading_key(line)
            if index < 3 and CHAPTER_HEADING.fullmatch(key):
                if key != chapter:
                    finish_section()
                    alarm_number = alarm_title = subsection = None
                    chapter = key
                    lines.append((line, page_number))
                continue

            if SECTION_HEADING.match(key):
                if key != subsection:
                    finish_section()
                    alarm_number = alarm_title = None
                    subsection = key
                elif index < 3:
                    continue

            heading = ALARM_HEADING.fullmatch(line)
            following = page_lines[index + 1:index + 7]
            has_field = False
            for item in following:
                if re.match(r"^(Parameters|Explanation):", item):
                    has_field = True
                    break
                if (
                    ALARM_HEADING.fullmatch(item)
                    or SECTION_HEADING.match(heading_key(item))
                ):
                    break

            if heading and has_field:
                finish_section()
                alarm_number, alarm_title = heading.groups()
            lines.append((line, page_number))

    finish_section()
    if not chunks:
        raise ValueError("No text was available for chunking.")

    return {
        "document_id": document["document_id"],
        "source_filename": document["source_filename"],
        "enterprise_metadata": (
            dict(enterprise_metadata)
            if enterprise_metadata is not None
            else None
        ),
        "strategy": STRATEGY,
        "chunk_words": chunk_words,
        "overlap_words": overlap_words,
        "total_sections": len(parents),
        "alarm_sections": sum(item["alarm_number"] is not None for item in parents),
        "total_chunks": len(chunks),
        "parents": parents,
        "chunks": chunks,
    }


def chunk_processed_document(processed_filename: str,
                             chunk_words: int = 180,
                             overlap_words: int = 30) -> dict:
    """Save a new v2 chunk file; do not alter processed data or existing outputs."""
    if (
        not isinstance(processed_filename, str)
        or not processed_filename
        or any(character in processed_filename for character in '/\\:\x00')
        or Path(processed_filename).suffix.lower() != ".json"
    ):
        raise ValueError("Provide only the stored JSON filename, not a folder path.")

    input_path = (PROCESSED_DIRECTORY / processed_filename).resolve()
    if input_path.parent != PROCESSED_DIRECTORY.resolve():
        raise ValueError("The input must be inside processed_documents.")
    if not input_path.is_file():
        raise FileNotFoundError("Document not found in processed_documents.")

    output_path = CHUNKED_DIRECTORY / f"{Path(processed_filename).stem}_chunks_v2.json"
    if output_path.exists():
        raise FileExistsError(f"A v2 chunk file already exists: {output_path.name}")

    with input_path.open(encoding="utf-8") as input_file:
        document = json.load(input_file)
    result = build_chunks(document, chunk_words, overlap_words)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    CHUNKED_DIRECTORY.mkdir(parents=True, exist_ok=True)

    handle = output_path.open("x", encoding="utf-8")
    try:
        with handle:
            handle.write(payload)
    except BaseException:
        output_path.unlink(missing_ok=True)  # Remove only this incomplete new file.
        raise

    summary = {
        key: value for key, value in result.items()
        if key not in ("parents", "chunks")
    }
    return {
        **summary,
        "chunked_filename": output_path.name,
        "saved_location": str(output_path),
    }