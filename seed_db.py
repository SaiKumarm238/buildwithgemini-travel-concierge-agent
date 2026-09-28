# seed_db.py
from google.cloud import firestore

FIRESTORE_PROJECT = "qwiklabs-gcp-01-6346f35ae90a"
FIRESTORE_DATABASE = "destinations-db"

DESTINATIONS = [
    {
        "id": "dest_001",
        "name": "Arashiyama Bamboo Grove & Tenryu-ji",
        "city": "Kyoto",
        "country": "Japan",
        "category": "Culture & Nature",
        "description": "Towering bamboo stalks with serene walking paths and an ancient Zen temple with traditional garden landscapes.",
        "best_season": "Spring / Autumn",
        "estimated_daily_budget_usd": 140.0,
        "rating": 4.9,
    },
    {
        "id": "dest_002",
        "name": "Amalfi Coast Scenic Drive & Positano",
        "city": "Amalfi",
        "country": "Italy",
        "category": "Coastline & Romance",
        "description": "Dramatic cliffside villages, pastel-colored houses overlooking the Mediterranean Sea, and world-class seafood.",
        "best_season": "Late Spring / Early Autumn",
        "estimated_daily_budget_usd": 250.0,
        "rating": 4.8,
    },
    {
        "id": "dest_003",
        "name": "Banff National Park & Lake Louise",
        "city": "Banff",
        "country": "Canada",
        "category": "Adventure & Wildlife",
        "description": "Turquoise glacial lakes, majestic Rocky Mountain peaks, canoeing, hiking trails, and abundant wildlife.",
        "best_season": "Summer / Winter",
        "estimated_daily_budget_usd": 180.0,
        "rating": 4.95,
    },
    {
        "id": "dest_004",
        "name": "Santorini Sunset Views & Oia Cliffside",
        "city": "Santorini",
        "country": "Greece",
        "category": "Island & Romance",
        "description": "Iconic white-washed buildings with blue domes, volcanic beaches, and breathtaking Aegean sunsets.",
        "best_season": "May - October",
        "estimated_daily_budget_usd": 220.0,
        "rating": 4.85,
    },
]

def seed():
    print(f"Connecting to Firestore project: {FIRESTORE_PROJECT}, database: {FIRESTORE_DATABASE}...")
    db = firestore.Client(project=FIRESTORE_PROJECT, database=FIRESTORE_DATABASE)
    collection_ref = db.collection("destinations")

    for item in DESTINATIONS:
        doc_id = item["id"]
        collection_ref.document(doc_id).set(item)
        print(f"Seeded destination '{item['name']}' ({doc_id}) into 'destinations' collection.")

    print("\nFirestore seeding complete! ✅")

if __name__ == "__main__":
    seed()
