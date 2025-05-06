import os
import firebase_admin
from firebase_admin import credentials, db
from functools import lru_cache

@lru_cache()
def get_db_reference(path="/"):
    if not firebase_admin._apps:
        cred_path = os.path.join(os.path.dirname(__file__), "klarbill_admin_key.json")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://klarbill-3de73-default-rtdb.europe-west1.firebasedatabase.app/'
        })
    return db.reference(path)