import os, glob, hashlib, sqlite3, threading, torch, chromadb
import warnings
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict
from PIL import Image
import numpy as np
from tqdm import tqdm
from transformers import AutoProcessor, AutoModel
from transformers.utils import logging as hf_logging

MODEL_NAME = "google/siglip-base-patch16-224"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

BASE_DIR = Path(__file__).parent.parent
DB_DIR = BASE_DIR / "database"


LOCAL_MODEL_PATH = BASE_DIR / "models" / "siglip-base-patch16-224"
CHROMADB_PATH = DB_DIR / "chroma_store"
SQLITE_PATH = str(DB_DIR / "images.sqlite")

DB_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_MODEL_PATH.mkdir(parents=True, exist_ok=True)

hf_logging.set_verbosity_error()
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
warnings.filterwarnings("ignore", message=".*slow image processor.*")


def load_model():
    if LOCAL_MODEL_PATH.exists():
        processor = AutoProcessor.from_pretrained(LOCAL_MODEL_PATH)
        model = AutoModel.from_pretrained(LOCAL_MODEL_PATH).to(DEVICE).eval()
    else:
        processor = AutoProcessor.from_pretrained(MODEL_NAME)
        model = AutoModel.from_pretrained(MODEL_NAME).to(DEVICE).eval()
        LOCAL_MODEL_PATH.mkdir(parents=True, exist_ok=True)
        processor.save_pretrained(LOCAL_MODEL_PATH)
        model.save_pretrained(LOCAL_MODEL_PATH)
    return processor, model


processor, model = load_model()

chroma_client = chromadb.PersistentClient(path=str(CHROMADB_PATH))
chroma_coll = chroma_client.get_or_create_collection(
    name="siglip_images", embedding_function=None
)

chroma_lock = threading.Lock()


class SQLiteDB:
    def __init__(self, path: str, timeout: int = 30):
        self.path = path
        self.timeout = timeout
        self.local = threading.local()

    def _create_conn(self):
        conn = sqlite3.connect(self.path, timeout=self.timeout)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def get_conn(self):
        conn = getattr(self.local, "conn", None)
        if conn is None:
            conn = self._create_conn()
            self.local.conn = conn
        return conn

    @contextmanager
    def cursor(self):
        con = self.get_conn()
        cur = con.cursor()
        try:
            yield cur
            con.commit()
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def close_thread_conn(self):
        conn = getattr(self.local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self.local.conn = None


db = SQLiteDB(SQLITE_PATH)

with db.cursor() as cur:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            hash TEXT PRIMARY KEY,
            path TEXT,
            added_at TEXT,
            updated_at TEXT
        )"""
    )


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
        for im in imgs:
            try:
                im.close()
            except Exception:
                pass
    if embs:
        return np.vstack(embs)
    hidden = getattr(model, "config", None)
    hidden_size = getattr(hidden, "hidden_size", 0) if hidden else 0
    return np.zeros((0, hidden_size))


def incremental_scan(scan_paths: List[str]) -> None:
    found = list_images(scan_paths)
    with db.cursor() as cur:
        cur.execute("SELECT hash, path FROM images")
        known: Dict[str, str] = dict(cur.fetchall())

        new_paths, new_hashes = [], []
        updated = 0

        for fp in tqdm(found):
            h = sha256_file(fp)
            abs_fp = os.path.abspath(fp)
            if h in known:
                if abs_fp != known[h]:
                    cur.execute(
                        "UPDATE images SET path=?, updated_at=? WHERE hash=?",
                        (abs_fp, datetime.utcnow().isoformat(), h),
                    )
                    updated += 1
            else:
                new_paths.append(fp)
                new_hashes.append(h)

        if new_paths:
            vecs = embed(new_paths)
            if vecs.shape[0] != 0:
                with chroma_lock:
                    chroma_coll.add(ids=new_hashes, embeddings=vecs)
            now = datetime.now(timezone.utc).isoformat()
            cur.executemany(
                "INSERT INTO images VALUES (?,?,?,?)",
                [
                    (h, os.path.abspath(p), now, now)
                    for h, p in zip(new_hashes, new_paths)
                ],
            )

        existing_files = set(map(os.path.abspath, found))
        cur.execute("SELECT hash, path FROM images")
        deletions = []
        for h, p in cur.fetchall():
            if p not in existing_files and not os.path.exists(p):
                deletions.append(h)

        if deletions:
            with chroma_lock:
                chroma_coll.delete(ids=deletions)
            cur.executemany(
                "DELETE FROM images WHERE hash=?", [(h,) for h in deletions]
            )


def incremental_scan_silent(scan_paths: List[str]):
    found = list_images(scan_paths)
    new_paths, new_hashes = [], []
    updated = 0
    deletions = []

    with db.cursor() as cur:
        cur.execute("SELECT hash, path FROM images")
        known: Dict[str, str] = dict(cur.fetchall())

        for fp in found:
            h = sha256_file(fp)
            abs_fp = os.path.abspath(fp)
            if h in known:
                if abs_fp != known[h]:
                    cur.execute(
                        "UPDATE images SET path=?, updated_at=? WHERE hash=?",
                        (abs_fp, datetime.utcnow().isoformat(), h),
                    )
                    updated += 1
            else:
                new_paths.append(fp)
                new_hashes.append(h)

        if new_paths:
            vecs = embed(new_paths)
            if vecs.shape[0] != 0:
                with chroma_lock:
                    chroma_coll.add(ids=new_hashes, embeddings=vecs)
            now = datetime.now(timezone.utc).isoformat()
            cur.executemany(
                "INSERT INTO images VALUES (?,?,?,?)",
                [
                    (h, os.path.abspath(p), now, now)
                    for h, p in zip(new_hashes, new_paths)
                ],
            )

        existing_files = set(map(os.path.abspath, found))
        cur.execute("SELECT hash, path FROM images")
        for h, p in cur.fetchall():
            if p not in existing_files and not os.path.exists(p):
                deletions.append(h)

        if deletions:
            with chroma_lock:
                chroma_coll.delete(ids=deletions)
            cur.executemany(
                "DELETE FROM images WHERE hash=?", [(h,) for h in deletions]
            )

    return {
        "success": True,
        "total_media_count": len(found),
        "new_media_count": len(new_paths),
        "updated_media_count": updated,
        "deleted_media_count": len(deletions),
    }


def search_by_text(query: str, top_k: int = 5):
    inputs = processor(text=[query], return_tensors="pt", padding="max_length").to(
        DEVICE
    )
    with torch.no_grad():
        vec = model.get_text_features(**inputs).cpu().numpy()
    with chroma_lock:
        res = chroma_coll.query(query_embeddings=vec, n_results=top_k)
    ids = res.get("ids", [[]])[0]
    distances = res.get("distances", [[]])[0]
    if not ids:
        return []
    placeholders = ",".join(["?"] * len(ids))
    with db.cursor() as cur:
        cur.execute(
            f"SELECT hash, path FROM images WHERE hash IN ({placeholders})", ids
        )
        path_dict = dict(cur.fetchall())
    results = []
    for h, dist in zip(ids, distances):
        path = path_dict.get(h, "Path not found (可能 deleted)")
        results.append((h, dist, path))
    return results


def search_by_image(path: str, top_k: int = 5):
    vec = embed([path])
    if vec.shape[0] == 0:
        return []
    with chroma_lock:
        res = chroma_coll.query(query_embeddings=vec, n_results=top_k)
    ids = res.get("ids", [[]])[0]
    distances = res.get("distances", [[]])[0]
    if not ids:
        return []
    placeholders = ",".join(["?"] * len(ids))
    with db.cursor() as cur:
        cur.execute(
            f"SELECT hash, path FROM images WHERE hash IN ({placeholders})", ids
        )
        path_dict = dict(cur.fetchall())
    results = []
    for h, dist in zip(ids, distances):
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
