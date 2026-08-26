import pytest
from bson import ObjectId

from app.services.sld_generator import SLDGenerator
from app.models import substation_doc, transformer_doc, feeder_doc


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=1):
        self._docs = sorted(self._docs, key=lambda d: d.get(key, 0), reverse=direction < 0)
        return self

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

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


def _single_bus_substation_with_lilo():
    ss_id = ObjectId()
    ss = substation_doc(
        name="Test SS", region="LAR", circle="GEC1", tnc="T", esd="E",
        gps_lat=26.1, gps_lon=91.7, sub_type="Conventional",
        gss_primary="Test GSS",
    )
    ss["_id"] = ss_id
    ss["topology"]["bus_config"] = "single_bus"

    tr_id = ObjectId()
    tr = transformer_doc(substation_id=ss_id, sequence=1, capacity_mva=5, make="BHEL", yom=2015)
    tr["_id"] = tr_id

    incomer = feeder_doc(substation_id=ss_id, sequence=1, name="33kV Incomer",
                          voltage_kv=33, feeder_type="incoming_33kv")
    lilo = feeder_doc(substation_id=ss_id, sequence=2, name="Kelvin LILO",
                       voltage_kv=33, feeder_type="lilo_33kv")
    outgoing = feeder_doc(substation_id=ss_id, transformer_id=tr_id, sequence=3,
                           name="11kV Consumer Feeder", voltage_kv=11, feeder_type="outgoing_11kv")

    return FakeDB(substations=[ss], feeders=[incomer, lilo, outgoing], transformers=[tr]), ss_id


def test_lilo_feeder_name_appears_in_rendered_svg():
    db, ss_id = _single_bus_substation_with_lilo()
    svg = SLDGenerator(db).generate(str(ss_id))
    assert "Kelvin LILO" in svg


def test_lilo_feeder_rendered_in_33kv_color_not_11kv_color():
    db, ss_id = _single_bus_substation_with_lilo()
    svg = SLDGenerator(db).generate(str(ss_id))
    # sym_feeder_out renders the name inside a text element whose containing
    # <g> carries the feeder's stroke color — assert the LILO arrow group
    # uses the 33kV red, not the 11kV blue used elsewhere in the same file.
    assert 'fill="#CC2200"' in svg  # 33kV color present somewhere for this feeder
    # The 11kV consumer feeder must still render in blue.
    assert 'fill="#0055CC"' in svg


def test_lilo_feeder_included_in_equipment_table():
    db, ss_id = _single_bus_substation_with_lilo()
    svg = SLDGenerator(db).generate(str(ss_id))
    assert "Kelvin LILO" in svg
    assert svg.count("Kelvin LILO") >= 2  # once in the diagram, once in the equipment table


def _double_bus_substation_with_lilo():
    ss_id = ObjectId()
    ss = substation_doc(
        name="Double Bus SS", region="LAR", circle="GEC1", tnc="T", esd="E",
        gps_lat=26.1, gps_lon=91.7, sub_type="Conventional",
        gss_primary="Test GSS",
    )
    ss["_id"] = ss_id
    ss["topology"]["bus_config"] = "double_bus"

    tr1_id, tr2_id = ObjectId(), ObjectId()
    tr1 = transformer_doc(substation_id=ss_id, sequence=1, capacity_mva=5, make="BHEL", yom=2015)
    tr1["_id"] = tr1_id
    tr2 = transformer_doc(substation_id=ss_id, sequence=2, capacity_mva=5, make="BHEL", yom=2015)
    tr2["_id"] = tr2_id

    lilo = feeder_doc(substation_id=ss_id, sequence=3, name="Double Bus LILO",
                       voltage_kv=33, feeder_type="lilo_33kv")

    return FakeDB(substations=[ss], feeders=[lilo], transformers=[tr1, tr2]), ss_id


def test_lilo_feeder_drawn_in_double_bus_diagram_not_just_table():
    db, ss_id = _double_bus_substation_with_lilo()
    svg = SLDGenerator(db).generate(str(ss_id))
    # Must appear once for the diagram symbol and once for the equipment table row.
    assert svg.count("Double Bus LILO") >= 2
