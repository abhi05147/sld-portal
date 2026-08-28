"""PDF report — SVG snapshot page happy path + graceful fallback. Fake DB."""
from bson import ObjectId
from app.services.pdf_generator import PDFReportGenerator
from app.models import substation_doc, transformer_doc, feeder_doc


class FakeCursor(list):
    def sort(self, *a, **k): return self


class FakeCollection:
    def __init__(self, docs=None): self.docs = docs or []
    def find_one(self, filt):
        return next((d for d in self.docs
                     if all(d.get(k) == v for k, v in filt.items())), None)
    def find(self, filt):
        return FakeCursor([d for d in self.docs
                           if all(d.get(k) == v for k, v in filt.items())])


class FakeDB:
    def __init__(self, ss, feeders, trs):
        self.substations = FakeCollection([ss])
        self.feeders = FakeCollection(feeders)
        self.transformers = FakeCollection(trs)


def _fixture():
    ss = substation_doc(name="Ulubari", region="LAR", circle="GEC-II", tnc="T", esd="E",
                        gps_lat=26.1, gps_lon=91.7, sub_type="Conventional",
                        gss_primary="132kV Sishugram GSS")
    ss["_id"] = ObjectId()
    t1 = transformer_doc(substation_id=ss["_id"], sequence=1, capacity_mva=10,
                         make="BHEL", yom=2015)
    t1["_id"] = ObjectId()
    f1 = feeder_doc(substation_id=ss["_id"], sequence=1, name="Feeder A",
                    voltage_kv=11, feeder_type="outgoing_11kv")
    f1["_id"] = ObjectId()
    return FakeDB(ss, [f1], [t1]), str(ss["_id"])


VALID_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120" '
             'width="200" height="120"><rect width="200" height="120" fill="#fff"/>'
             '<text x="10" y="60" font-size="10">SLD</text></svg>')


def test_generate_with_valid_svg_produces_pdf_bytes():
    db, sid = _fixture()
    out = PDFReportGenerator(db).generate(sid, VALID_SVG)
    assert isinstance(out, (bytes, bytearray)) and out[:4] == b"%PDF"


def test_generate_with_broken_svg_still_produces_pdf():
    db, sid = _fixture()
    out = PDFReportGenerator(db).generate(sid, "<svg>not really <valid")
    assert out[:4] == b"%PDF"


def test_generate_with_no_svg_still_produces_pdf():
    db, sid = _fixture()
    out = PDFReportGenerator(db).generate(sid, None)
    assert out[:4] == b"%PDF"


def test_snapshot_adds_a_page_compared_to_the_no_svg_report():
    """B5: the SVG snapshot really becomes an extra page."""
    db, sid = _fixture()
    with_svg = PDFReportGenerator(db).generate(sid, VALID_SVG)
    without   = PDFReportGenerator(db).generate(sid, None)
    assert with_svg.count(b"/Type /Page\n") > without.count(b"/Type /Page\n")


def test_real_sld_svg_round_trips_through_the_pdf_generator():
    """B5: the actual SLDGenerator output must survive svglib, not just a toy SVG."""
    from app.services.sld_generator import SLDGenerator
    db, sid = _fixture()
    svg = SLDGenerator(db).generate(sid)
    out = PDFReportGenerator(db).generate(sid, svg)
    assert out[:4] == b"%PDF"
    baseline = PDFReportGenerator(db).generate(sid, None)
    assert out.count(b"/Type /Page\n") > baseline.count(b"/Type /Page\n")


def test_valid_svg_is_passed_through_svg2rlg(monkeypatch):
    import app.services.pdf_generator as P
    calls = []
    real = P.svg2rlg
    def spy(arg):
        calls.append(arg)
        return real(arg)
    monkeypatch.setattr(P, "svg2rlg", spy)
    db, sid = _fixture()
    P.PDFReportGenerator(db).generate(sid, VALID_SVG)
    assert len(calls) == 1
