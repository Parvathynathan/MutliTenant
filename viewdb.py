from qdrant_client import QdrantClient

# Connect to the local disk storage
client = QdrantClient(path="./qdrant_storage")
collection_name = "multitenant_rag_kb"

print("\n--- Collections Found ---")
print([c.name for c in client.get_collections().collections])

print(f"\n--- Stored Points in '{collection_name}' ---")
records, _ = client.scroll(
    collection_name=collection_name,
    limit=50,
    with_payload=True,
    with_vectors=False
)

if not records:
    print("Database is currently empty.")
else:
    for record in records:
        print(f"ID: {record.id}")
        print(f"Tenant: {record.payload.get('tenant_id')}")
        print(f"File: {record.payload.get('filename')}")
        print(f"Snippet: {record.payload.get('text')[:120]}...")
        print("-" * 50)