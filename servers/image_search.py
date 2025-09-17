import os, glob, hashlib, sqlite3
from datetime import datetime
from typing import List, Dict, Tuple
from PIL import Image
import numpy as np
import torch
from tqdm import tqdm
import chromadb
from transformers import AutoProcessor, AutoModel

MODEL_NAME = "google/siglip-base-patch16-224"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

processor = AutoProcessor.from_pretrained(MODEL_NAME)
model = AutoModel.from_pretrained(MODEL_NAME).to(DEVICE).eval()

# Chroma (collection will be created if absent)
chroma_client = chromadb.PersistentClient(path="database/chroma_store")
chroma_coll = chroma_client.get_or_create_collection(
    name="siglip_images", embedding_function=None
)

# SQLite
SQLITE_PATH = "database/images.sqlite"
con = sqlite3.connect(SQLITE_PATH)
cur = con.cursor()
cur.execute(
    """
CREATE TABLE IF NOT EXISTS images (
    hash TEXT PRIMARY KEY,
    path TEXT,
    added_at TEXT,
    updated_at TEXT
)"""
)
con.commit()


def sha256_file(fp: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def list_images(paths: List[str]) -> List[str]:
    images = []
    for p in paths:
        if os.path.isdir(p):
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                images += glob.glob(os.path.join(p, "**", ext), recursive=True)
        elif os.path.isfile(p) and p.lower().endswith((".jpg", ".jpeg", ".png")):
            images.append(p)
    return images


def embed(paths: List[str], batch: int = 32) -> np.ndarray:
    embs = []
    for i in range(0, len(paths), batch):
        imgs = [Image.open(p).convert("RGB") for p in paths[i : i + batch]]
        inputs = processor(images=imgs, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            vec = model.get_image_features(**inputs).cpu().numpy()
        embs.append(vec)
    return np.vstack(embs)


def incremental_scan(scan_paths: List[str]) -> None:
    found = list_images(scan_paths)
    print(f"Scanning {len(found)} images…")

    # Fast look-up of hashes already seen
    cur.execute("SELECT hash, path FROM images")
    known: Dict[str, str] = dict(cur.fetchall())

    new_paths, new_hashes = [], []
    updated = 0

    for fp in tqdm(found):
        h = sha256_file(fp)
        abs_fp = os.path.abspath(fp)  # Use absolute path for consistency
        if h in known:
            if abs_fp != known[h]:
                # Moved/renamed file → update SQLite only
                cur.execute(
                    "UPDATE images SET path=?, updated_at=? WHERE hash=?",
                    (abs_fp, datetime.utcnow().isoformat(), h),
                )
                updated += 1
        else:
            new_paths.append(fp)
            new_hashes.append(h)

    # Embed & insert new images (no metadata in Chroma)
    if new_paths:
        vecs = embed(new_paths)
        chroma_coll.add(ids=new_hashes, embeddings=vecs)  # No metadatas

        now = datetime.utcnow().isoformat()
        cur.executemany(
            "INSERT INTO images VALUES (?,?,?,?)",
            [(h, os.path.abspath(p), now, now) for h, p in zip(new_hashes, new_paths)],
        )
        print(f"Added {len(new_paths)} new images.")

    if updated:
        print(f"Updated {updated} paths in SQLite.")

    con.commit()

    # Detect deletions (optional cleanup)
    existing_files = set(map(os.path.abspath, found))
    cur.execute("SELECT hash, path FROM images")
    deletions = []
    for h, p in cur.fetchall():
        if p not in existing_files and not os.path.exists(p):
            deletions.append(h)
    if deletions:
        chroma_coll.delete(ids=deletions)
        cur.executemany("DELETE FROM images WHERE hash=?", [(h,) for h in deletions])
        print(f"Deleted {len(deletions)} missing images from both databases.")
    con.commit()


# Updated search utilities (lookup paths from SQLite)
def search_by_text(query: str, top_k: int = 5):
    # Embed text with SigLIP
    inputs = processor(text=[query], return_tensors="pt", padding="max_length").to(
        DEVICE
    )
    with torch.no_grad():
        vec = model.get_text_features(**inputs).cpu().numpy()
    res = chroma_coll.query(query_embeddings=vec, n_results=top_k)

    hashes = res["ids"][0]
    distances = res["distances"][0]

    # Lookup current paths from SQLite
    placeholders = ",".join(["?"] * len(hashes))
    cur.execute(f"SELECT hash, path FROM images WHERE hash IN ({placeholders})", hashes)
    path_dict = dict(cur.fetchall())

    results = []
    for h, dist in zip(hashes, distances):
        path = path_dict.get(h, "Path not found (可能 deleted)")
        results.append((h, dist, path))
    return results


def search_by_image(path: str, top_k: int = 5):
    vec = embed([path])  # Single image
    res = chroma_coll.query(query_embeddings=vec, n_results=top_k)

    hashes = res["ids"][0]
    distances = res["distances"][0]

    # Lookup current paths from SQLite
    placeholders = ",".join(["?"] * len(hashes))
    cur.execute(f"SELECT hash, path FROM images WHERE hash IN ({placeholders})", hashes)
    path_dict = dict(cur.fetchall())

    results = []
    for h, dist in zip(hashes, distances):
        path = path_dict.get(h, "Path not found (deleted)")
        results.append((h, dist, path))
    return results


if __name__ == "__main__":
    import argparse, pprint

    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", nargs="+", help="Paths to files/dirs to (re)scan")
    ap.add_argument("--text", help="Text query")
    ap.add_argument("--image", help="Image query path")
    args = ap.parse_args()

    if args.scan:
        incremental_scan(args.scan)
    if args.text:
        pprint.pp(search_by_text(args.text))
    if args.image:
        pprint.pp(search_by_image(args.image))
