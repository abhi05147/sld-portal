from bson import ObjectId
from bson.errors import InvalidId
from flask import jsonify

from app import mongo
from app.models import infer_topology, utcnow


def parse_object_id(value, label="ID"):
    try:
        return ObjectId(value), None
    except (InvalidId, TypeError):
        return None, (jsonify(error=f"Invalid {label}"), 400)


def refresh_substation_topology(substation_id):
    feeders = list(mongo.db.feeders.find({"substation_id": substation_id}))
    topo = infer_topology(feeders)
    mongo.db.substations.update_one(
        {"_id": substation_id},
        {"$set": {"topology": topo, "updated_at": utcnow()}},
    )
    return topo


def feeder_substation_id(feeder_id):
    feeder = mongo.db.feeders.find_one({"_id": feeder_id}, {"substation_id": 1})
    return feeder.get("substation_id") if feeder else None


def transformer_substation_id(transformer_id):
    transformer = mongo.db.transformers.find_one({"_id": transformer_id}, {"substation_id": 1})
    return transformer.get("substation_id") if transformer else None
