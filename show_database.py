"""Print the local Qdrant data in a terminal-friendly format."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from qdrant_client import QdrantClient


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_STORAGE = PROJECT_ROOT / "qdrant_test_storage"
DEFAULT_COLLECTION = "multitenant_rag_kb"


def shorten(value: object, limit: int = 220) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else f"{text[:limit]}..."


def print_database(storage_path: Path, collection_name: str, tenant_id: str | None) -> None:
    try:
        client = QdrantClient(path=str(storage_path))
    except RuntimeError as error:
        if "already accessed by another instance" in str(error):
            print("Qdrant storage is currently locked by the running API.")
            print("Stop the FastAPI server, then run this viewer again.")
            return
        raise
    try:
        collections = [collection.name for collection in client.get_collections().collections]
        print("\n=== Qdrant Database Overview ===")
        print(f"Storage:    {storage_path}")
        print(f"Collections: {', '.join(collections) if collections else '(none)'}")

        if collection_name not in collections:
            print(f"\nCollection '{collection_name}' was not found.")
            return

        records, _ = client.scroll(
            collection_name=collection_name,
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
        if tenant_id:
            records = [
                record
                for record in records
                if record.payload and record.payload.get("tenant_id") == tenant_id
            ]

        tenant_counts = Counter(
            record.payload.get("tenant_id", "unknown")
            for record in records
            if record.payload
        )
        file_counts = Counter(
            record.payload.get("filename", "unknown")
            for record in records
            if record.payload
        )

        print(f"\n=== Collection: {collection_name} ===")
        print(f"Records: {len(records)}")
        if tenant_id:
            print(f"Tenant filter: {tenant_id}")
        print(f"Tenants: {dict(tenant_counts) or '(none)'}")
        print(f"Files:   {dict(file_counts) or '(none)'}")

        if not records:
            print("\nNo records found.")
            return

        print("\n=== Stored Records ===")
        for number, record in enumerate(records, start=1):
            payload = record.payload or {}
            print(f"\n[{number}] Point ID: {record.id}")
            print(f"Tenant:  {payload.get('tenant_id', '(missing)')}")
            print(f"File:    {payload.get('filename', '(missing)')}")
            print(f"Text:    {shorten(payload.get('text', '(missing)'))}")
            print("-" * 72)
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Show local Qdrant records and payload values.")
    parser.add_argument(
        "--storage",
        type=Path,
        default=DEFAULT_STORAGE,
        help=f"Qdrant storage folder (default: {DEFAULT_STORAGE})",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: {DEFAULT_COLLECTION})",
    )
    parser.add_argument("--tenant", help="Only show records for this tenant ID.")
    args = parser.parse_args()
    print_database(args.storage, args.collection, args.tenant)


if __name__ == "__main__":
    main()
