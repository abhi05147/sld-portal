from app.models import infer_topology


def _f(feeder_type, voltage_kv=11, name="Feeder"):
    return {"feeder_type": feeder_type, "voltage_kv": voltage_kv, "name": name}


def test_infer_topology_single_bus_no_couplers():
    topo = infer_topology([
        _f("incoming_33kv", 33), _f("transformer_hv", 33), _f("outgoing_11kv", 11),
    ])
    assert topo["bus_config"] == "single_bus"
    assert topo["num_transformers"] == 1
    assert topo["num_11kv_sections"] == 1
    assert topo["has_11kv_bus_coupler"] is False
    assert topo["has_33kv_bus_coupler"] is False


def test_infer_topology_counts_33kv_outgoing_feeders():
    topo = infer_topology([
        _f("outgoing_33kv", 33), _f("outgoing_33kv", 33), _f("outgoing_11kv", 11),
    ])
    assert topo["outgoing_33kv_count"] == 2
    assert topo["outgoing_11kv_count"] == 1


def test_infer_topology_sectionalized_11kv_when_11kv_coupler_present():
    topo = infer_topology([
        _f("transformer_hv", 33), _f("transformer_hv", 33),
        _f("bus_coupler", 11, "11kV Bus Coupler"),
    ])
    assert topo["has_11kv_bus_coupler"] is True
    assert topo["has_33kv_bus_coupler"] is False
    assert topo["bus_config"] == "sectionalized_11kv"
    assert topo["num_11kv_sections"] == 2


def test_infer_topology_sectionalized_both_when_both_couplers_present():
    topo = infer_topology([
        _f("transformer_hv", 33), _f("transformer_hv", 33),
        _f("bus_coupler", 33, "33kV Bus Coupler"),
        _f("bus_coupler", 11, "11kV Bus Coupler"),
    ])
    assert topo["bus_config"] == "sectionalized_both"
    assert topo["has_33kv_bus_coupler"] is True
    assert topo["has_11kv_bus_coupler"] is True


def test_infer_topology_coupler_without_voltage_key_counts_as_11kv():
    topo = infer_topology([
        _f("transformer_hv", 33),
        {"feeder_type": "bus_coupler", "name": "Bus Coupler"},  # no voltage_kv
    ])
    assert topo["has_11kv_bus_coupler"] is True
    assert topo["has_33kv_bus_coupler"] is False


def test_infer_topology_flags_station_transformer():
    topo = infer_topology([
        _f("transformer_hv", 33), _f("station_transformer", 33, "Station Tr"),
    ])
    assert topo["has_station_transformer"] is True
    assert topo["num_transformers"] == 1  # station TR does not count as a power TR
