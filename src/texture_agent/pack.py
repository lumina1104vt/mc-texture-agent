"""把已生成的材質（每個名稱取最新版本）整理成 Minecraft 資源包的資料夾結構並打包成 zip。"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

from .tools import load_manifest, versions_of

PACK_FORMAT = 34  # Minecraft 1.21.1
_MOD_ID = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_mod_id(mod_id: str) -> str:
    if not _MOD_ID.match(mod_id):
        raise ValueError(f"Invalid mod id {mod_id!r}: start with a letter, then lowercase letters, digits and underscores.")
    return mod_id


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def export_pack(output_dir: str | Path, mod_id: str) -> tuple[Path, list[str]]:
    """回傳 (zip 路徑, 匯出的材質清單)。沒有任何材質時丟出錯誤。"""
    output_dir = Path(output_dir)
    mod_id = validate_mod_id(mod_id)
    manifest = load_manifest(output_dir)

    chosen: list[tuple[str, str, Path, int]] = []
    for base, info in sorted(manifest.items()):
        found = versions_of(output_dir, base)
        if found:
            latest = max(found)
            chosen.append((base, info.get("kind", "block"), found[latest], latest))
    if not chosen:
        raise ValueError("No saved textures to export yet. Generate at least one texture first.")

    pack_dir = output_dir / f"{mod_id}_resourcepack"
    if pack_dir.exists():
        shutil.rmtree(pack_dir)  # 每次重建，避免殘留已經不要的檔案
    _write_json(pack_dir / "pack.mcmeta", {"pack": {"pack_format": PACK_FORMAT, "description": f"{mod_id} textures"}})

    assets = pack_dir / "assets" / mod_id
    names: list[str] = []
    for base, kind, src, version in chosen:
        dest = assets / "textures" / kind / f"{base}.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if kind == "block":
            _write_json(assets / "models" / "block" / f"{base}.json", {"parent": "minecraft:block/cube_all", "textures": {"all": f"{mod_id}:block/{base}"}})
            _write_json(assets / "models" / "item" / f"{base}.json", {"parent": f"{mod_id}:block/{base}"})
            _write_json(assets / "blockstates" / f"{base}.json", {"variants": {"": {"model": f"{mod_id}:block/{base}"}}})
        else:
            _write_json(assets / "models" / "item" / f"{base}.json", {"parent": "minecraft:item/generated", "textures": {"layer0": f"{mod_id}:item/{base}"}})
        names.append(f"{kind}/{base} ({src.name})")

    zip_path = output_dir / f"{mod_id}_resourcepack.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(pack_dir.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(pack_dir).as_posix())
    return zip_path, names
