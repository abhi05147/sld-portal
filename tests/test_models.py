from app.models import infer_topology


def _feeder(feeder_type, name="Feeder"):
    return {"feeder_type": feeder_type, "name": name}


def test_infer_topology_counts_lilo_33kv_feeders():
    feeders = [
        _feeder("incoming_33kv"),
        _feeder("transformer_hv"),
        _feeder("outgoing_11kv"),
        _feeder("lilo_33kv"),
        _feeder("lilo_33kv"),
    ]
    topo = infer_topology(feeders)
    assert topo["lilo_33kv_count"] == 2
