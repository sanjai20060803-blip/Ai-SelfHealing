import pymongo
from config import MONGO_URI, MONGO_DB

client = pymongo.MongoClient(MONGO_URI)
db = client[MONGO_DB]

metrics_collection = db["network_metrics"]
predictions_collection = db["predictions"]
recovery_records_collection = db["recovery_records"]
notifications_collection = db["notifications"]
forecasts_collection = db["forecasts"]
counters_collection = db["counters"]

def get_next_id(sequence_name: str) -> int:
    """Returns an auto-incrementing integer ID starting at 1, matching relational DB primary keys."""
    counter = counters_collection.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER
    )
    return counter["seq"]

def clean_doc(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    d = dict(doc)
    d.pop("_id", None)
    return d

def clean_docs(cursor) -> list[dict]:
    return [clean_doc(d) for d in cursor]

def init_db():
    try:
        metrics_collection.create_index([("id", -1)])
        predictions_collection.create_index([("id", -1)])
        predictions_collection.create_index([("metricId", -1)])
        recovery_records_collection.create_index([("id", -1)])
        notifications_collection.create_index([("id", -1)])
        forecasts_collection.create_index([("id", -1)])
    except Exception as e:
        print(f"Index initialization warning: {e}")
