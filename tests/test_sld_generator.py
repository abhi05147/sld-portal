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


# ── _layout: degenerate / single-transformer ─────────────────────────────
def _ss(name="Ulubari", bus_config="single_bus", **kw):
    d = substation_doc(name=name, region="LAR", circle="GEC-II", tnc="T", esd="E",
                       gps_lat=26.1, gps_lon=91.7, sub_type="Conventional",
                       gss_primary="132kV Sishugram GSS", **kw)
    d["_id"] = ObjectId()
    d["topology"]["bus_config"] = bus_config
    return d


def _tr(ss, seq, cap=10.0):
    t = transformer_doc(substation_id=ss["_id"], sequence=seq, capacity_mva=cap,
                        make="BHEL", yom=2015)
    t["_id"] = ObjectId()
    return t


def _fd(ss, seq, name, ftype, volt=11, tr=None):
    f = feeder_doc(substation_id=ss["_id"],
                   transformer_id=(tr["_id"] if tr else None),
                   sequence=seq, name=name, voltage_kv=volt, feeder_type=ftype)
    f["_id"] = ObjectId()
    return f


def _build(ss, feeders, transformers):
    db = FakeDB(substations=[ss], feeders=feeders, transformers=transformers)
    gen = SLDGenerator(db)
    scene = gen._layout(ss, sorted(feeders, key=lambda x: x["sequence"]), transformers)
    return db, gen, scene


def test_layout_single_transformer_scene_shape():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [
        _fd(ss, 1, "33kV UG Incomer-1", "incoming_33kv", 33),
        _fd(ss, 2, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 3, "New Ulubari", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 4, "East", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 5, "Rehabari", "outgoing_11kv", 11, tr=t1),
    ]
    _, _, scene = _build(ss, feeders, [t1])

    assert scene.bus33.coupler_x is None
    assert len(scene.bus33.segments) == 1
    assert scene.couplers11 == []
    assert len(scene.sections11) == 1
    kinds = [b.kind for b in scene.bays33]
    assert kinds.count("incomer_33kv") == 1
    assert kinds.count("transformer") == 1
    assert kinds.count("bus_pt_33") == 1
    assert kinds[-1] == "bus_pt_33"  # pinned rightmost
    sec = scene.sections11[0]
    assert [b.label for b in sec.feeder_bays] == ["New Ulubari", "East", "Rehabari"]
    assert scene.title.name == "Ulubari"
    assert re.match(r"\d{2}\.\d{2}\.\d{4}$", scene.title.last_update_str)


def test_layout_unassigned_11kv_feeders_round_robin_across_sections():
    ss = _ss()
    t1, t2 = _tr(ss, 1), _tr(ss, 2)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 3, "F1", "outgoing_11kv", 11),   # no transformer_id
        _fd(ss, 4, "F2", "outgoing_11kv", 11),
        _fd(ss, 5, "F3", "outgoing_11kv", 11),
    ]
    _, _, scene = _build(ss, feeders, [t1, t2])
    counts = sorted(len(s.feeder_bays) for s in scene.sections11)
    assert counts == [1, 2]  # 3 feeders split 2/1 across 2 sections


def test_layout_transformer_bay_never_reaches_11kv_band():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [_fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
               _fd(ss, 2, "F1", "outgoing_11kv", 11, tr=t1)]
    _, _, scene = _build(ss, feeders, [t1])
    tr_bay = next(b for b in scene.bays33 if b.kind == "transformer")
    assert tr_bay.x == scene.sections11[0].bus[0] or tr_bay.x >= G.LAYOUT["MARGIN"]
    assert G.Y["tr_bot"] < G.Y["bus11"]


# ── _layout: 33 kV outgoing + station transformer ────────────────────────
def test_layout_33kv_outgoing_feeder_gets_full_bay():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [
        _fd(ss, 1, "33kV UG Incomer-1", "incoming_33kv", 33),
        _fd(ss, 2, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 3, "33kV Chandmari O/g", "outgoing_33kv", 33),
        _fd(ss, 4, "33kV Paltanbazar O/g", "outgoing_33kv", 33),
        _fd(ss, 5, "New Ulubari", "outgoing_11kv", 11, tr=t1),
    ]
    _, _, scene = _build(ss, feeders, [t1])
    og = [b for b in scene.bays33 if b.kind == "outgoing_33kv"]
    assert [b.label for b in og] == ["33kV Chandmari O/g", "33kV Paltanbazar O/g"]
    assert [e.kind for e in og[0].equipment][:4] == ["la", "isolator", "vcb", "ct"]
    assert og[0].voltage_kv == 33


def test_layout_station_transformer_single_bay_before_bus_pt():
    ss = _ss()
    t1 = _tr(ss, 1)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "100 kVA 33/0.4kV Station Tr", "station_transformer", 33),
        _fd(ss, 3, "New Ulubari", "outgoing_11kv", 11, tr=t1),
    ]
    _, _, scene = _build(ss, feeders, [t1])
    kinds = [b.kind for b in scene.bays33]
    assert kinds.count("station_transformer") == 1
    assert kinds.index("station_transformer") == len(kinds) - 2  # just before bus_pt_33
    assert kinds[-1] == "bus_pt_33"


def test_layout_ocef_marker_only_when_relay_data_present():
    ss = _ss()
    t1 = _tr(ss, 1)
    f_with = _fd(ss, 1, "33kV A O/g", "outgoing_33kv", 33)
    f_with["switchgear"]["oc_ef_relay_type"] = "Numerical"
    f_without = _fd(ss, 2, "33kV B O/g", "outgoing_33kv", 33)
    _, _, scene = _build(ss, [f_with, f_without, _fd(ss, 3, "Tr-1 HV", "transformer_hv", 33, tr=t1)], [t1])
    a = next(b for b in scene.bays33 if b.label == "33kV A O/g")
    b = next(b for b in scene.bays33 if b.label == "33kV B O/g")
    assert any(e.kind == "ocef" for e in a.equipment)
    assert not any(e.kind == "ocef" for e in b.equipment)


# ── _layout: 33 kV bus coupler ──────────────────────────────────────────
def _ulubari_feeders(ss, trs):
    t1, t2, t3 = trs
    return [
        _fd(ss, 1, "33kV UG Incomer-1", "incoming_33kv", 33),
        _fd(ss, 2, "33kV UG Incomer-2", "incoming_33kv", 33),
        _fd(ss, 3, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 4, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 5, "Tr-3 HV", "transformer_hv", 33, tr=t3),
        _fd(ss, 6, "33kV Chandmari O/g", "outgoing_33kv", 33),
        _fd(ss, 7, "33kV Paltanbazar O/g", "outgoing_33kv", 33),
        _fd(ss, 8, "33kV Kalapahar O/g", "outgoing_33kv", 33),
        _fd(ss, 9, "100 kVA 33/0.4kV Station Tr", "station_transformer", 33),
        _fd(ss, 10, "33kV Bus Coupler", "bus_coupler", 33),
        _fd(ss, 11, "11kV Bus Coupler", "bus_coupler", 11),
        _fd(ss, 12, "New Ulubari", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 13, "East", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 14, "Rehabari", "outgoing_11kv", 11, tr=t2),
        _fd(ss, 15, "Gopinath", "outgoing_11kv", 11, tr=t2),
        _fd(ss, 16, "South Surekha", "outgoing_11kv", 11, tr=t3),
        _fd(ss, 17, "South", "outgoing_11kv", 11, tr=t3),
    ]


def test_layout_no_33kv_coupler_single_segment():
    ss = _ss()
    t1 = _tr(ss, 1)
    _, _, scene = _build(ss, [_fd(ss, 1, "I1", "incoming_33kv", 33),
                              _fd(ss, 2, "Tr-1 HV", "transformer_hv", 33, tr=t1)], [t1])
    assert len(scene.bus33.segments) == 1
    assert scene.bus33.coupler_x is None
    assert all(b.segment == 0 for b in scene.bays33)


def test_layout_33kv_coupler_two_segments_and_split_bays():
    ss = _ss(bus_config="sectionalized_33kv")
    trs = [_tr(ss, 1), _tr(ss, 2), _tr(ss, 3)]
    _, _, scene = _build(ss, _ulubari_feeders(ss, trs), trs)
    assert len(scene.bus33.segments) == 2
    assert scene.bus33.coupler_x is not None
    seg0 = [b for b in scene.bays33 if b.kind != "bus_pt_33" and b.segment == 0]
    seg1 = [b for b in scene.bays33 if b.kind != "bus_pt_33" and b.segment == 1]
    assert len(seg0) >= 1 and len(seg1) >= 1
    assert abs(len(seg0) - len(seg1)) <= 1
    # segments are contiguous and meet at coupler_x
    (a0, a1), (b0, b1) = scene.bus33.segments
    assert a1 <= scene.bus33.coupler_x <= b0 or a1 == b0


# ── _layout: 11 kV bus couplers ─────────────────────────────────────────
def test_layout_two_sections_one_11kv_coupler():
    ss = _ss(bus_config="sectionalized_11kv")
    t1, t2 = _tr(ss, 1), _tr(ss, 2)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 3, "11kV Bus Coupler", "bus_coupler", 11),
        _fd(ss, 4, "F1", "outgoing_11kv", 11, tr=t1),
        _fd(ss, 5, "F2", "outgoing_11kv", 11, tr=t2),
    ]
    _, _, scene = _build(ss, feeders, [t1, t2])
    assert len(scene.couplers11) == 1
    c = scene.couplers11[0]
    assert c.orientation == "h11" and c.between == (0, 1)
    s0x1 = scene.sections11[0].bus[1]
    s1x0 = scene.sections11[1].bus[0]
    assert min(s0x1, s1x0) - 5 <= c.x <= max(s0x1, s1x0) + 5


def test_layout_three_sections_one_coupler_leaves_third_isolated():
    ss = _ss(bus_config="sectionalized_both")
    trs = [_tr(ss, 1), _tr(ss, 2), _tr(ss, 3)]
    _, _, scene = _build(ss, _ulubari_feeders(ss, trs), trs)
    assert len(scene.sections11) == 3
    assert [c.between for c in scene.couplers11] == [(0, 1)]  # sections 1-2 coupled, 3 isolated


def test_layout_more_coupler_records_than_gaps_are_ignored():
    ss = _ss()
    t1, t2 = _tr(ss, 1), _tr(ss, 2)
    feeders = [
        _fd(ss, 1, "Tr-1 HV", "transformer_hv", 33, tr=t1),
        _fd(ss, 2, "Tr-2 HV", "transformer_hv", 33, tr=t2),
        _fd(ss, 3, "11kV Bus Coupler A", "bus_coupler", 11),
        _fd(ss, 4, "11kV Bus Coupler B", "bus_coupler", 11),
    ]
    _, _, scene = _build(ss, feeders, [t1, t2])
    assert len(scene.couplers11) == 1  # only one gap available
