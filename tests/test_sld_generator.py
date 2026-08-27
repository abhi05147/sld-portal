"""SLD generator tests — symbol helpers, then _layout Scene structure, then
render smoke tests. Uses in-memory fakes; no MongoDB."""
import re
import pytest
from bson import ObjectId

from app.services import sld_generator as G
from app.services.sld_generator import SLDGenerator
from app.models import substation_doc, transformer_doc, feeder_doc


# ── Fakes ────────────────────────────────────────────────────────────────
class FakeCursor:
    def __init__(self, docs): self._docs = docs
    def sort(self, key, direction=1):
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0), reverse=direction < 0)
        return self
    def __iter__(self): return iter(self._docs)


class FakeCollection:
    def __init__(self, docs=None): self.docs = docs or []
    def find_one(self, filt):
        for d in self.docs:
            if all(d.get(k) == v for k, v in filt.items()):
                return d
        return None
    def find(self, filt):
        return FakeCursor([d for d in self.docs if all(d.get(k) == v for k, v in filt.items())])


class FakeDB:
    def __init__(self, substations=None, feeders=None, transformers=None):
        self.substations = FakeCollection(substations or [])
        self.feeders = FakeCollection(feeders or [])
        self.transformers = FakeCollection(transformers or [])


# ── Symbol helpers ───────────────────────────────────────────────────────
def test_ratings_dict_has_all_keys():
    for k in ("vcb_33", "vcb_11", "iso_33", "iso_11", "la", "ct"):
        assert isinstance(G.RATINGS[k], str) and G.RATINGS[k]


def test_sym_station_transformer_renders_group_and_label():
    out = G.sym_station_transformer(100, 200, label="100 kVA 33/0.4kV Station Tr")
    assert "<g" in out and "</g>" in out
    assert "translate(100,200)" in out
    assert "Station Tr" in out
    assert "#006600" in out  # earth


def test_sym_ocef_marker_contains_text():
    out = G.sym_ocef_marker(0, 0)
    assert "OC/EF" in out
    assert "<g" in out


def test_sym_bus_coupler_horizontal_has_breaker_and_isolators():
    out = G.sym_bus_coupler_horizontal(300, 330)
    assert out.count("<line") >= 3   # iso - vcb - iso across the break
    assert "translate(300" in out or 'x1="300' in out
