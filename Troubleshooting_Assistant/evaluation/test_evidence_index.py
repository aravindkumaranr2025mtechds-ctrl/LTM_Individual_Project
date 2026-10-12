"""Standalone contract tests using constructed source fixtures, not diagnoses.

Run from the project root:
    python -m unittest discover -s evaluation -p test_evidence_index.py -v

Only Python's standard library is needed. No model or server is started.
"""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evidence_index_under_test", ROOT / "app/services/evidence_index.py",
)
service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(service)
PREPARED_NAME = "test_ABB_ready.json"
INDEX_NAME = "test_ABB_ready_evidence_v1.json"


def fixture():
    """Small synthetic document in the existing ABB preparer's output format."""
    identity = {
        "document_id": "test_ABB", "source_filename": "test_ABB.pdf",
        "manufacturer": "ABB", "document_reference": "3GZF500730-85",
        "revision": "H", "printed_revision_date": "06-2022",
    }
    usage = {
        "record_type": "manufacturer_possible_cause_and_guidance",
        "condition_annotation_status": "not_reviewed",
        "machine_applicability": "not_assessed",
        "approved_for_automatic_execution": False,
        "note": "Constructed fixture, not a repair instruction.",
    }
    records, parents, chunks, groups = [], [], [], []
    for number, symptom in enumerate(("Repeated wording", "Unicode 🧪 motor"), 1):
        rid, sid = f"test_ABB_r{number:03d}", f"test_ABB_s{number:03d}"
        # Repeated text in different fields catches incorrect str.find offsets.
        # Non-ASCII text catches confusion between characters and UTF-8 bytes.
        cause = symptom
        guidance = f"Quoted source field {number}. Preserve qualifiers."
        cells = {}
        for offset, (cell_name, value) in enumerate((
            ("symptom", symptom), ("cause", cause), ("remedy", guidance),
        )):
            cells[cell_name] = {
                "pdf_page": 25, "printed_page": 25,
                "bbox": [10.0 + offset * 20, 30.0, 25.0 + offset * 20, 45.0],
                "raw_text": value.replace(" ", "\n"),
            }
        record = {
            "record_id": rid, "symptom_id": sid, "symptom": symptom,
            "possible_cause": cause, "manufacturer_guidance": guidance,
            "page_numbers": [25], "row_number_on_page": number,
            "symptom_inherited": False, "source_cells": cells,
            "context_ids": ["test_ABB_context_p005"],
        }
        text = (
            "Source: ABB low voltage motors manual, 3GZF500730-85, Rev H (06-2022).\n"
            f"Symptom: {symptom}\nPossible cause: {cause}\n"
            f"Manufacturer guidance: {guidance}"
        )
        records.append(record)
        parents.append({
            **deepcopy(record), **identity, "parent_id": rid, "text": text,
            "section_type": "troubleshooting_record", "alarm_number": None,
            "alarm_title": None, "usage": deepcopy(usage),
        })
        chunks.append({
            **identity, "chunk_id": f"{rid}_c001", "parent_id": rid,
            "record_id": rid, "symptom_id": sid, "text": text,
            "page_numbers": [25], "page_numbers_scope": "source_record",
            "context_ids": list(record["context_ids"]), "token_count": 64,
        })
        groups.append({"symptom_id": sid, "symptom": symptom, "record_ids": [rid]})
    return {
        **identity, "source_sha256": "a" * 64,
        "preparation": {
            "strategy": "abb_complete_records_v1",
            "one_complete_record_per_chunk": True,
        },
        "usage": usage, "records": records, "parents": parents,
        "chunks": chunks, "symptom_groups": groups,
        "contexts": [{"context_id": "test_ABB_context_p005", "pdf_page": 5,
                      "printed_page": 5, "text_layout": "Constructed context."}],
        "total_records": 2, "total_sections": 2, "total_chunks": 2,
        "total_symptom_groups": 2,
    }


def encode(document):
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


class EvidenceIndexTests(unittest.TestCase):
    def setUp(self):
        self.document = fixture()

    def build(self, document=None):
        return service.build_abb_evidence_index(
            encode(self.document if document is None else document), PREPARED_NAME,
        )

    def test_repeated_text_and_unicode_have_the_correct_field_offsets(self):
        index = self.build()
        for entry, parent in zip(index["entries"], self.document["parents"]):
            starts = []
            for span in entry["spans"]:
                start, end = span["start"], span["end"]
                self.assertEqual(parent["text"][start:end], parent[span["field"]])
                self.assertEqual(span["quote"], parent[span["field"]])
                self.assertEqual(" ".join(span["source_cell"]["raw_text"].split()), span["quote"])
                starts.append(start)
            self.assertEqual(len(set(starts)), 3)
            self.assertEqual(entry["parent_text_sha256"], hashlib.sha256(parent["text"].encode()).hexdigest())

    def test_preserves_contexts_cells_and_unknown_condition_status(self):
        index = self.build()
        self.assertEqual(index["contexts"], self.document["contexts"])
        self.assertEqual(index["symptom_groups"], self.document["symptom_groups"])
        self.assertEqual(index["usage"], self.document["usage"])
        self.assertEqual(index["reviewed_condition_count"], 0)
        for entry in index["entries"]:
            self.assertEqual(entry["condition_annotation_status"], "not_reviewed")
            self.assertEqual(entry["condition_annotations"], [])

    def test_source_fingerprint_binds_raw_bytes_including_bom(self):
        raw = b"\xef\xbb\xbf" + encode(self.document)
        index = service.build_abb_evidence_index(raw, PREPARED_NAME)
        self.assertEqual(index["source"]["prepared_sha256"], hashlib.sha256(raw).hexdigest())

    def test_output_does_not_alias_input(self):
        original = deepcopy(self.document)
        index = self.build()
        index["entries"][0]["spans"][0]["source_cell"]["bbox"][0] = 999
        index["contexts"][0]["text_layout"] = "Changed"
        self.assertEqual(original, self.document)

    def test_wrong_manufacturer_and_preparation_are_rejected(self):
        for mutate in (
            lambda d: d.update(manufacturer="Siemens"),
            lambda d: d["preparation"].update(strategy="different"),
            lambda d: d["preparation"].update(one_complete_record_per_chunk=False),
        ):
            with self.subTest(mutate=mutate):
                document = fixture()
                mutate(document)
                with self.assertRaises(ValueError):
                    self.build(document)

    def test_group_swap_duplicate_and_omission_are_rejected(self):
        for ids in (["test_ABB_r002"], ["test_ABB_r001"] * 2, []):
            with self.subTest(ids=ids):
                document = fixture()
                document["symptom_groups"][0]["record_ids"] = ids
                with self.assertRaises(ValueError):
                    self.build(document)

    def test_duplicate_parent_and_orphan_chunk_are_rejected(self):
        for key in ("parents", "chunks", "records", "contexts"):
            with self.subTest(key=key):
                document = fixture()
                document[key].append(deepcopy(document[key][0]))
                with self.assertRaises(ValueError):
                    self.build(document)
        self.document["chunks"].pop()
        with self.assertRaises(ValueError):
            self.build()

    def test_source_cell_cannot_be_replaced_even_if_parent_matches_record(self):
        self.document["records"][0]["source_cells"]["cause"]["raw_text"] = "A different cause"
        self.document["parents"][0]["source_cells"] = deepcopy(self.document["records"][0]["source_cells"])
        with self.assertRaisesRegex(ValueError, "source cell"):
            self.build()

    def test_changed_or_truncated_parent_and_chunk_text_are_rejected(self):
        for key in ("parents", "chunks"):
            document = fixture()
            document[key][0]["text"] = document[key][0]["text"][:-1]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Prepared text"):
                self.build(document)

    def test_missing_context_and_changed_context_links_are_rejected(self):
        for key in ("parents", "chunks"):
            document = fixture()
            document[key][0]["context_ids"] = ["missing"]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.build(document)

    def test_wrong_page_and_invalid_bbox_are_rejected(self):
        for changes in (
            {"pdf_page": 26}, {"pdf_page": True}, {"printed_page": 0},
            {"bbox": [10, 20, 5, 30]}, {"bbox": [True, 20, 30, 40]},
            {"bbox": [0, 0, float("inf"), 20]},
        ):
            document = fixture()
            for key in ("records", "parents"):
                document[key][0]["source_cells"]["cause"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.build(document)

    def test_changed_usage_and_parent_identity_are_rejected(self):
        for mutate in (
            lambda d: d["usage"].update(approved_for_automatic_execution=True),
            lambda d: d["usage"].update(condition_annotation_status="reviewed"),
            lambda d: d["usage"].update(machine_applicability="assessed"),
            lambda d: d["parents"][0].update(revision="G"),
        ):
            document = fixture()
            mutate(document)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.build(document)

    def test_json_duplicate_keys_and_nonfinite_values_are_rejected(self):
        for raw in (b'{"x": 1, "x": 2}', b'{"x": NaN}', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                service.build_abb_evidence_index(raw, PREPARED_NAME)
        raw = encode(self.document).replace(b'"manufacturer": "ABB"', b'"extra": 1e999, "manufacturer": "ABB"', 1)
        with self.assertRaises(ValueError):
            service.build_abb_evidence_index(raw, PREPARED_NAME)

    def test_input_filename_cannot_contain_paths(self):
        for name in (None, "", "../test.json", "C:\\test.json", "test.txt", " test.json", "test\n.json"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                service.build_abb_evidence_index(encode(self.document), name)


class EvidenceIndexFileTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="evidence_index_test_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.prepared, self.output = self.root / "prepared", self.root / "evidence"
        self.prepared.mkdir()
        self.source = self.prepared / PREPARED_NAME
        self.source.write_bytes(encode(fixture()))
        self.index_path = self.output / INDEX_NAME
        for key, value in (("PREPARED_DIRECTORY", self.prepared), ("OUTPUT_DIRECTORY", self.output)):
            patcher = mock.patch.object(service, key, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def create(self):
        return service.create_abb_evidence_index(PREPARED_NAME)

    def test_roundtrip_is_read_only_and_does_not_overwrite(self):
        original = self.source.read_bytes()
        result = self.create()
        self.assertEqual(result["total_records"], 2)
        self.assertEqual(result["total_spans"], 6)
        original_index = self.index_path.read_bytes()
        loaded = service.load_abb_evidence_index(INDEX_NAME)
        self.assertEqual(loaded["source"]["prepared_filename"], PREPARED_NAME)
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(self.index_path.read_bytes(), original_index)

    def test_changed_prepared_bytes_are_rejected_without_deletion(self):
        self.create()
        original_index = self.index_path.read_bytes()
        self.source.write_bytes(self.source.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            service.load_abb_evidence_index(INDEX_NAME)
        self.assertEqual(self.index_path.read_bytes(), original_index)

    def test_changed_spans_contexts_or_review_status_are_rejected(self):
        self.create()
        original = json.loads(self.index_path.read_text())
        for mutate in (
            lambda d: d["entries"][0]["spans"][0].update(start=0),
            lambda d: d["entries"][0]["spans"][0].update(quote="Changed"),
            lambda d: d["contexts"][0].update(text_layout="Changed"),
            lambda d: d["entries"][0]["condition_annotations"].append({"condition": "invented"}),
            lambda d: d.update(reviewed_condition_count=1),
            lambda d: d.update(schema_version=True),
        ):
            candidate = deepcopy(original)
            mutate(candidate)
            self.index_path.write_bytes(encode(candidate))
            with self.subTest(mutate=mutate), self.assertRaisesRegex(ValueError, "supported draft schema"):
                service.load_abb_evidence_index(INDEX_NAME)

    def test_source_change_during_creation_removes_only_the_new_output(self):
        original_builder = service.build_abb_evidence_index

        def build_and_change(*args):
            result = original_builder(*args)
            self.source.write_bytes(self.source.read_bytes() + b"\n")
            return result

        with mock.patch.object(service, "build_abb_evidence_index", side_effect=build_and_change):
            with self.assertRaisesRegex(ValueError, "Prepared source changed"):
                self.create()
        self.assertFalse(self.index_path.exists())
        self.assertTrue(self.source.exists())

    def test_source_change_during_load_is_detected(self):
        self.create()
        builder = service.build_abb_evidence_index

        def build_and_change(*args):
            result = builder(*args)
            self.source.write_bytes(self.source.read_bytes() + b"\n")
            return result

        with mock.patch.object(service, "build_abb_evidence_index", side_effect=build_and_change):
            with self.assertRaisesRegex(ValueError, "during validation"):
                service.load_abb_evidence_index(INDEX_NAME)

    def test_input_symlink_outside_folder_is_rejected(self):
        external = self.root / "external.json"
        external.write_bytes(self.source.read_bytes())
        self.source.unlink()
        try:
            self.source.symlink_to(external)
        except OSError:
            self.skipTest("Symlink creation is unavailable in this environment.")
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.create()
        self.assertTrue(external.exists())

    def test_missing_input_does_not_create_output(self):
        self.source.unlink()
        with self.assertRaises(FileNotFoundError):
            self.create()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
