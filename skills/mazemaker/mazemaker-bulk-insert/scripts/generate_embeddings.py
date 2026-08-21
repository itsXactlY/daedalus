#!/usr/bin/env python3
"""Generate embeddings for neural memories that don't have them.

Usage:
  cd ~/.hermes/plugins/memory/neural
  python3 ~/.hermes/skills/neural-memory-bulk-insert/scripts/generate_embeddings.py [--since-id ID]

Without --since-id, processes ALL memories without embeddings.
With --since-id, only processes memories with id >= since_id.
"""
import sqlite3
import os
import sys
import struct
import argparse

sys.path.insert(0, os.path.expanduser("~/.hermes/plugins/memory/neural"))
from embed_provider import EmbeddingProvider

def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for memories")
    parser.add_argument("--db", default=os.path.expanduser("~/.mazemaker/memory.db"))
    parser.add_argument("--since-id", type=int, default=None, help="Only process memories with id >= this value")
    parser.add_argument("--limit", type=int, default=None, help="Max memories to process")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    if args.since_id:
        cur.execute("SELECT id, content FROM memories WHERE embedding IS NULL AND id >= ? ORDER BY id", (args.since_id,))
    else:
        cur.execute("SELECT id, content FROM memories WHERE embedding IS NULL ORDER BY id")
    
    rows = cur.fetchall()
    if args.limit:
        rows = rows[:args.limit]
    
    print(f"Found {len(rows)} memories without embeddings")
    if not rows:
        conn.close()
        return

    try:
        embedder = EmbeddingProvider(backend="auto")
        print(f"Backend: {embedder.backend.__class__.__name__} ({embedder.dim}d)")
    except Exception as e:
        print(f"Failed to init embedder: {e}")
        conn.close()
        sys.exit(1)

    count = 0
    errors = 0
    for mid, content in rows:
        if not content:
            continue
        try:
            vec = embedder.embed(content[:2000])
            blob = struct.pack(f'{len(vec)}f', *vec)
            cur.execute("UPDATE memories SET embedding = ? WHERE id = ?", (blob, mid))
            count += 1
            if count % 20 == 0:
                print(f"  Processed {count}/{len(rows)}")
                conn.commit()
        except Exception as e:
            errors += 1
            print(f"  Error on {mid}: {e}")

    conn.commit()
    conn.close()
    print(f"Done! Generated {count} embeddings, {errors} errors")

if __name__ == "__main__":
    main()
