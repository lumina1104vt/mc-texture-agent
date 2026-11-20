"""參考材質：掃描使用者提供的 jar / 材質包 / 資料夾，依檔名建立 Chroma 向量索引並檢索。

只索引 assets/<namespace>/textures/block(s)|item(s)/ 底下的 PNG（核心範圍：方塊與物品），
而且只用檔名做 embedding（16x16 的小圖不適合向量化）。
原版與模組的材質各有版權，所以資料一律由使用者自己提供，不放進 repo。
"""

from __future__ import annotations

import io
import os
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

_TEXTURE_RE = re.compile(
    r"(?:^|/)assets/(?P<ns>[^/]+)/textures/(?P<kind>blocks?|items?)/(?P<rest>.+)\.png$",
    re.IGNORECASE,
)
SOURCE_SUFFIXES = {".jar", ".zip"}
MAX_ENTRY_BYTES = 2 * 1024 * 1024  # 單張材質超過 2MB 一律略過
ADD_BATCH = 256
DELETE_BATCH = 1000
COLLECTION = "textures"
SYMBOLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


@dataclass(frozen=True)
class TextureRef:
    source: str  # 相對於 reference_dir 的路徑（jar / zip 檔，或資料夾）
    entry: str  # jar 內的路徑，或資料夾內的相對路徑（一律用 /）
    ns: str  # 命名空間，例如 minecraft
    kind: str  # "block" 或 "item"
    name: str  # 檔名（不含副檔名），例如 diamond_ore

    @property
    def id(self) -> str:
        return f"{self.source}::{self.entry}"

    @property
    def text(self) -> str:
        """拿去做 embedding 的文字：diamond_ore -> 'diamond ore'。"""
        return re.sub(r"[_\-\s]+", " ", self.name).strip().lower()

    def metadata(self) -> dict[str, str]:
        return {"source": self.source, "entry": self.entry, "ns": self.ns, "kind": self.kind, "name": self.name}


def _match(path: str) -> TextureRef | None:
    m = _TEXTURE_RE.search(path.replace("\\", "/"))
    if not m:
        return None
    kind = "block" if m["kind"].lower().startswith("block") else "item"
    return TextureRef("", path, m["ns"], kind, m["rest"].rsplit("/", 1)[-1])


def discover_sources(reference_dir: Path) -> list[str]:
    """找出 reference_dir 底下所有來源：.jar / .zip 檔，以及直接含有 assets/ 的資料夾。"""
    found: list[str] = []
    for root, dirs, files in os.walk(reference_dir):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        root_path = Path(root)
        if "assets" in dirs and root_path != reference_dir:
            found.append(root_path.relative_to(reference_dir).as_posix())
            dirs[:] = []  # 資料夾本身就是一個來源，不再往下找
            continue
        for f in sorted(files):
            if Path(f).suffix.lower() in SOURCE_SUFFIXES:
                found.append((root_path / f).relative_to(reference_dir).as_posix())
    return found


def scan_source(reference_dir: Path, source: str) -> list[TextureRef]:
    """列出一個來源裡所有的方塊與物品材質。"""
    path = reference_dir / source
    refs: dict[str, TextureRef] = {}
    if path.is_dir():
        for p in sorted(path.rglob("*.png")):
            rel = p.relative_to(path).as_posix()
            ref = _match(rel)
            if ref:
                ref = TextureRef(source, rel, ref.ns, ref.kind, ref.name)
                refs[ref.id] = ref
    else:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir() or info.file_size > MAX_ENTRY_BYTES:
                    continue
                ref = _match(info.filename)
                if ref:
                    ref = TextureRef(source, info.filename, ref.ns, ref.kind, ref.name)
                    refs[ref.id] = ref
    return list(refs.values())


def texture_to_grid(img: Image.Image) -> tuple[list[str], dict[str, str], str]:
    """把材質轉成 16 列字元格子和色票，格式可以直接給 texture_kit 的 from_ascii / stamp_ascii。

    回傳 (rows, palette, note)；'.' 代表透明。
    """
    img = img.convert("RGBA")
    w, h = img.size
    notes = []
    if h > w and h % w == 0:  # 動畫材質是上下疊起來的多格，只取第一格
        img = img.crop((0, 0, w, w))
        h = w
        notes.append("animated texture, first frame only")
    if w != h:
        raise ValueError(f"texture is not square ({w}x{h})")
    if w != 16:
        if w % 16 != 0:
            raise ValueError(f"texture size {w}x{h} is not a multiple of 16")
        img = img.resize((16, 16), Image.Resampling.NEAREST)
        notes.append(f"downscaled from {w}x{w}")

    px = img.load()
    cells = [[px[x, y] for x in range(16)] for y in range(16)]

    def key(c, step):
        r, g, b, a = c
        if a <= 16:
            return None
        return (r // step * step, g // step * step, b // step * step, 255 if a >= 240 else a)

    step = 1
    while True:
        counts = Counter(key(c, step) for row in cells for c in row if key(c, step))
        if len(counts) <= len(SYMBOLS):
            break
        step *= 2  # 顏色太多（高解析度縮小後）就合併相近的顏色
    if step > 1:
        notes.append("colors merged")

    letters = {color: SYMBOLS[i] for i, (color, _) in enumerate(counts.most_common())}
    rows = ["".join(letters[key(c, step)] if key(c, step) else "." for c in row) for row in cells]
    palette = {
        letter: "#%02x%02x%02x" % color[:3] + ("" if color[3] == 255 else "%02x" % color[3])
        for color, letter in letters.items()
    }
    return rows, palette, "; ".join(notes)


class ReferenceIndex:
    """使用者提供的參考材質：同步來源、建立索引、依描述檢索。"""

    def __init__(self, reference_dir, index_dir, embedding_function=None, client=None):
        self.reference_dir = Path(reference_dir)
        self.index_dir = Path(index_dir)
        self.upload_dir = self.reference_dir / "uploads"
        self._ef = embedding_function
        self._client = client
        self._collection = None

    @classmethod
    def from_env(cls) -> "ReferenceIndex":
        return cls(os.environ.get("REFERENCE_DIR", "reference"), os.environ.get("INDEX_DIR", "index"))

    # ---- Chroma ----
    def _col(self):
        if self._collection is None:
            import chromadb
            from chromadb.config import Settings

            if self._client is None:
                self.index_dir.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.index_dir), settings=Settings(anonymized_telemetry=False)
                )
            ef = self._ef
            if ef is None:
                from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

                ef = DefaultEmbeddingFunction()  # all-MiniLM-L6-v2（Chroma 預設）
            self._collection = self._client.get_or_create_collection(COLLECTION, embedding_function=ef)
        return self._collection

    def count(self) -> int:
        return self._col().count()

    # ---- 同步 ----
    def sync(self, progress: Callable[[str], None] | None = None) -> dict:
        """讓索引和 reference_dir 的內容一致：新增沒索引過的、移除已經不存在的。"""
        say = progress or (lambda _msg: None)
        self.reference_dir.mkdir(parents=True, exist_ok=True)
        col = self._col()

        wanted: dict[str, list[TextureRef]] = {}
        errors: list[str] = []
        for source in discover_sources(self.reference_dir):
            try:
                wanted[source] = scan_source(self.reference_dir, source)
            except (zipfile.BadZipFile, OSError) as e:
                errors.append(f"{source}: {e}")

        existing = col.get(include=["metadatas"])
        have: dict[str, set[str]] = defaultdict(set)
        for id_, meta in zip(existing["ids"], existing["metadatas"]):
            have[meta["source"]].add(id_)

        stale: list[str] = []
        for source, ids in have.items():
            keep = {r.id for r in wanted.get(source, [])}
            stale += sorted(ids - keep)
        for i in range(0, len(stale), DELETE_BATCH):
            col.delete(ids=stale[i : i + DELETE_BATCH])

        have_ids = {i for ids in have.values() for i in ids}
        todo = [r for refs in wanted.values() for r in refs if r.id not in have_ids]
        for i in range(0, len(todo), ADD_BATCH):
            batch = todo[i : i + ADD_BATCH]
            col.add(ids=[r.id for r in batch], documents=[r.text for r in batch], metadatas=[r.metadata() for r in batch])
            say(f"indexed {min(i + ADD_BATCH, len(todo))}/{len(todo)}")

        return {"sources": len(wanted), "added": len(todo), "removed": len(stale), "total": col.count(), "errors": errors}

    def add_upload(self, path: str) -> Path:
        """把使用者上傳的 jar / zip 複製進 reference_dir/uploads（同名會覆蓋）。"""
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w\-.]", "_", os.path.basename(path))
        dest = self.upload_dir / name
        shutil.copy(path, dest)
        return dest

    # ---- 檢索 ----
    def search(self, query: str, kind: str | None = None, top_k: int = 3) -> list[dict]:
        col = self._col()
        total = col.count()
        if total == 0 or not query.strip():
            return []
        where = {"kind": kind} if kind in ("block", "item") else None
        res = col.query(query_texts=[query], n_results=min(max(top_k * 5, 10), total), where=where)
        out, seen = [], set()
        for id_, meta, dist in zip(res["ids"][0], res["metadatas"][0], res["distances"][0]):
            key = (meta["ns"], meta["kind"], meta["name"])
            if key in seen:  # 同一個材質出現在多個來源（例如原版 jar 和材質包）只留最近的一個
                continue
            seen.add(key)
            out.append({"id": id_, "distance": dist, **meta})
            if len(out) >= top_k:
                break
        return out

    def load_image(self, meta: dict) -> Image.Image:
        root = self.reference_dir.resolve()
        source = (root / meta["source"]).resolve()
        if root != source and root not in source.parents:
            raise ValueError("source is outside the reference directory")
        if source.is_dir():
            path = (source / meta["entry"]).resolve()
            if source not in path.parents:
                raise ValueError("entry is outside the source folder")
            if path.stat().st_size > MAX_ENTRY_BYTES:
                raise ValueError("texture file is too large")
            data = path.read_bytes()
        else:
            with zipfile.ZipFile(source) as z:
                if z.getinfo(meta["entry"]).file_size > MAX_ENTRY_BYTES:
                    raise ValueError("texture file is too large")
                data = z.read(meta["entry"])
        return Image.open(io.BytesIO(data)).convert("RGBA")

    def describe(self, matches: list[dict]) -> str:
        """把檢索結果整理成給模型看的文字：色票加字元格子，可以直接貼進 from_ascii / stamp_ascii。"""
        blocks = []
        for i, m in enumerate(matches, 1):
            title = f"[{i}] {m['ns']}:{m['kind']}/{m['name']}  (from {Path(m['source']).name})"
            try:
                rows, palette, note = texture_to_grid(self.load_image(m))
            except Exception as e:  # 單張讀不出來不影響其他結果
                blocks.append(f"{title}\n  could not be read: {e}")
                continue
            pal = ", ".join(f'"{k}": "{v}"' for k, v in palette.items())
            grid = ",\n    ".join(f'"{r}"' for r in rows)
            extra = f"  # {note}" if note else ""
            blocks.append(f"{title}{extra}\npalette = {{{pal}}}\nrows = [\n    {grid},\n]")
        return "\n\n".join(blocks)
