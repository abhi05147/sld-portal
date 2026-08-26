import io
import os
import pytest
from bson import ObjectId

from app.services.importer import (
    ExcelImporter,
    _resolve_columns,
    _resolve_feeder_type,
    _norm_enum,
    STATUS_VALUES,
)
from app.services.template_generator import generate_template

SAMPLE_FILE = "/Users/abhijitdas/Downloads/GEC - I substation master data compiled.xlsx"


# ── _resolve_columns ──────────────────────────────────────────────────────

def test_resolve_columns_maps_known_headers_regardless_of_order():
    header_row = ["Feeder Name", "Substation Name", "Feeder Type"]
    col_map = _resolve_columns(header_row)
    assert col_map["feeder_name"] == 0
    assert col_map["ss_name"] == 1
    assert col_map["feeder_type_raw"] == 2


def test_resolve_columns_raises_on_missing_required_headers():
    header_row = ["Region", "Circle"]
    with pytest.raises(ValueError, match="Substation Name|Feeder Name"):
        _resolve_columns(header_row)


# ── _resolve_feeder_type ──────────────────────────────────────────────────

def test_resolve_feeder_type_bus_coupler_name_overrides_column_value():
    # Source file mislabels many "Bus Coupler" rows as "Transformer Outgoing"
    ftype = _resolve_feeder_type("Bus Coupler", "Transformer Outgoing", "11kV")
    assert ftype == "bus_coupler"


def test_resolve_feeder_type_uses_mapped_column_value():
    assert _resolve_feeder_type("Kamakhya GSS Incomer", "Substation Incomer", "33kV") == "incoming_33kv"
    assert _resolve_feeder_type("Tr-1 Incomer", "Transformer Incomer", "33kV") == "transformer_hv"
    assert _resolve_feeder_type("11KV I/C-1", "Transformer Outgoing", "11kV") == "incomer_11kv"
    assert _resolve_feeder_type("Some Feeder", "Outgoing Feeder", "11kV") == "outgoing_11kv"


def test_resolve_feeder_type_falls_back_to_heuristic_when_column_blank():
    # "Spare" row has no Feeder Type value in the real file
    assert _resolve_feeder_type("Spare", None, "33kV") == "incoming_33kv"


# ── _norm_enum ─────────────────────────────────────────────────────────────

def test_norm_enum_snaps_known_casing_variants_to_canonical():
    assert _norm_enum(" working", STATUS_VALUES) == "Working"
    assert _norm_enum("DEFECTIVE", STATUS_VALUES) == "Defective"
    assert _norm_enum("Not Available", STATUS_VALUES) == "Not Available"


def test_norm_enum_passes_through_unknown_values_unchanged():
    assert _norm_enum("IED (IEC 61850 compliant)", STATUS_VALUES) == "IED (IEC 61850 compliant)"


def test_norm_enum_returns_none_for_blank():
    assert _norm_enum(None, STATUS_VALUES) is None
    assert _norm_enum("   ", STATUS_VALUES) is None


# ── ExcelImporter integration (real sample file, fake db) ─────────────────

class FakeCollection:
    def __init__(self):
        self.docs = []

    def find_one(self, filt):
        for d in self.docs:
            if all(d.get(k) == v for k, v in filt.items()):
                return d
        return None

    def find_one_and_update(self, filt, update, upsert=False, return_document=False):
        doc = self.find_one(filt)
        if doc is None:
            if not upsert:
                return None
            doc = dict(filt)
            doc["_id"] = ObjectId()
            self.docs.append(doc)
        doc.update(update.get("$set", {}))
        return doc

    def update_one(self, filt, update, upsert=False):
        doc = self.find_one(filt)
        if doc is None and upsert:
            doc = dict(filt)
            doc.update(update.get("$setOnInsert", {}))
            doc["_id"] = ObjectId()
            self.docs.append(doc)
        elif doc is not None:
            doc.update(update.get("$set", {}))

    def insert_one(self, doc):
        doc = dict(doc)
        doc["_id"] = ObjectId()
        self.docs.append(doc)
        return type("Result", (), {"inserted_id": doc["_id"]})()

    def delete_many(self, filt):
        self.docs = [d for d in self.docs if not all(d.get(k) == v for k, v in filt.items())]


class FakeDB:
    def __init__(self):
        self.substations = FakeCollection()
        self.transformers = FakeCollection()
        self.feeders = FakeCollection()
        self.grid_substations = FakeCollection()


@pytest.fixture(scope="module")
def imported():
    if not os.path.exists(SAMPLE_FILE):
        pytest.skip(f"sample file not available at {SAMPLE_FILE}")
    db = FakeDB()
    importer = ExcelImporter(db)
    summary = importer.import_file(SAMPLE_FILE, user_id="000000000000000000000000")
    return db, summary


def test_import_creates_distinct_substations_for_duplicate_names(imported):
    db, summary = imported
    names = [d["name"] for d in db.substations.docs]
    assert names.count("Jail Road") == 2
    assert names.count("Jorabat") == 2
    assert names.count("Barsapara") == 2
    assert len(db.substations.docs) == 38


def test_import_marks_bus_coupler_rows_correctly(imported):
    db, summary = imported
    coupler_feeders = [f for f in db.feeders.docs if f["feeder_type"] == "bus_coupler"]
    assert len(coupler_feeders) == 36


def test_import_populates_pt_fields(imported):
    db, summary = imported
    with_pt = [f for f in db.feeders.docs if f["meter"].get("pt_type")]
    assert len(with_pt) > 0


# ── Template round-trip: guards against importer/template header drift ────

def test_generated_template_imports_cleanly():
    db = FakeDB()
    importer = ExcelImporter(db)
    summary = importer.import_file(io.BytesIO(generate_template()), user_id="000000000000000000000000")
    assert summary["substations"] == 1
    assert summary["feeders"] == 1
    assert db.feeders.docs[0]["feeder_type"] == "incoming_33kv"
    assert db.feeders.docs[0]["meter"]["pt_type"] == "Panel Mounted"
