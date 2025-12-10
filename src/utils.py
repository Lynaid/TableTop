import random
import json
import os
import hashlib
from datetime import datetime


def roll_dice(sides=6):
    return random.randint(1, sides)


def _sha256_of_file(path):
    """
    Return SHA256 checksum in format 'sha256:<hex>' or None on error.
    """
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return None
    return "sha256:" + h.hexdigest()


def save_campaign(
    path,
    asset_mgr,
    token_mgr,
    background_state=None,
    tilemap=None,
    engine_version="0.6",
    rules_engine=None,
):
    """
    Save full campaign (version 2) to JSON.

    path: full path to .json chosen via OS dialog.
    background_state: optional dict with keys "path" and "camera".
    tilemap: optional TileMap instance.
    rules_engine: optional RulesEngine instance (for global scripts).
    """
    if not path:
        return

    campaign_name = os.path.splitext(os.path.basename(path))[0]
    saved_at = datetime.utcnow().isoformat(timespec="seconds")

    # assets block with checksum + mtime
    assets_block = {}
    for name, meta in asset_mgr.assets.items():
        apath = meta.get("path", "")
        checksum = _sha256_of_file(apath) if apath and os.path.exists(apath) else None
        try:
            mtime = int(os.path.getmtime(apath)) if apath and os.path.exists(apath) else 0
        except OSError:
            mtime = 0
        assets_block[name] = {
            "path": apath,
            "checksum": checksum,
            "last_modified": mtime,
        }

    # tokens
    tokens_raw = token_mgr.to_json()
    tokens_block = []
    for d in tokens_raw:
        t = dict(d)
        tint = t.get("tint", [1.0, 1.0, 1.0])
        if isinstance(tint, (list, tuple)) and len(tint) == 3:
            vals = []
            for v in tint:
                if v is None:
                    vals.append(255)
                    continue
                if v > 1.0:
                    vals.append(int(max(0, min(255, v))))
                else:
                    vals.append(int(max(0, min(255, v * 255.0))))
            t["tint"] = vals
        tokens_block.append(t)

    data = {
        "version": 2,
        "metadata": {
            "campaign_name": campaign_name,
            "saved_at": saved_at,
            "engine_version": engine_version,
        },
        "assets": assets_block,
        "tokens": tokens_block,
        "background": None,
        "tilemap": None,
        "rules": None,
    }

    if background_state:
        bg_path = background_state.get("path", "")
        cam = background_state.get("camera", {}) or {}
        data["background"] = {
            "path": bg_path,
            "camera": {
                "x": float(cam.get("x", 0.0)),
                "y": float(cam.get("y", 0.0)),
                "zoom": float(cam.get("zoom", 1.0)),
            },
        }

    if tilemap is not None:
        data["tilemap"] = tilemap.to_json()

    if rules_engine is not None:
        data["rules"] = rules_engine.to_json()

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Saved campaign: {os.path.basename(path)}")


def load_campaign(path, asset_mgr, token_mgr, tilemap=None, rules_engine=None):
    """
    Load campaign (v1 or v2) from JSON.

    tilemap: optional TileMap instance; if provided and JSON contains "tilemap",
             tilemap.load_from_json(...) is called.

    rules_engine: optional RulesEngine instance; if provided and JSON contains "rules",
                  rules_engine.load_from_json(...) is called.

    Returns background_state or None:
    {
        "path": str or "",
        "camera": { "x": float, "y": float, "zoom": float }
    }
    """
    if not path or not os.path.exists(path):
        print(f"[ERROR] Campaign file not found: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load campaign JSON: {e}")
        return None

    version = data.get("version", 1)

    # --- ASSETS BLOCK (v2) ---
    assets_block = data.get("assets", {})
    placeholder_surf = asset_mgr.ensure_placeholder_asset()

    if isinstance(assets_block, dict):
        for name, info in assets_block.items():
            apath = info.get("path", "")
            if not apath or not os.path.exists(apath):
                print(f"[ERROR] Missing asset: {apath or name}")
                asset_mgr.assets[name] = asset_mgr.assets.get(
                    "__missing__",
                    {
                        "path": "",
                        "surface": placeholder_surf,
                        "thumb": None,
                        "size": 0,
                        "last_modified": 0,
                        "date_added": 0,
                    },
                )
                continue

            expected = info.get("checksum")
            current = _sha256_of_file(apath)
            if expected and current and expected != current:
                print(f"[WARNING] Asset checksum mismatch: {name}")

            asset_mgr.load_or_get_asset(name, apath)

    # For version 1, also ensure any referenced assets are present
    if version == 1:
        for name, m in data.get("assets", {}).items():
            apath = m.get("path")
            if apath and os.path.exists(apath):
                asset_mgr.load_or_get_asset(name, apath)
            else:
                print(f"[ERROR] Missing asset: {apath or name}")
                asset_mgr.ensure_placeholder_asset()

    # --- TOKENS BLOCK ---
    tokens_raw = data.get("tokens", [])
    fixed_tokens = []
    if isinstance(tokens_raw, list):
        for idx, td in enumerate(tokens_raw):
            if not isinstance(td, dict):
                continue
            t = dict(td)
            if "asset" not in t:
                print(f"[ERROR] Missing key tokens[{idx}]/asset – using placeholder")
                t["asset"] = "__missing__"

            tint = t.get("tint")
            if isinstance(tint, (list, tuple)) and len(tint) == 3:
                vals = list(tint)
                if any(v is not None and v > 1.0 for v in vals):
                    new_vals = []
                    for v in vals:
                        if v is None:
                            new_vals.append(1.0)
                        else:
                            new_vals.append(max(0.0, min(1.0, v / 255.0)))
                    t["tint"] = new_vals
            fixed_tokens.append(t)

    token_mgr.load_from_json(fixed_tokens)

    # --- TILEMAP BLOCK ---
    tilemap_state = data.get("tilemap")
    if tilemap is not None:
        tilemap.load_from_json(tilemap_state)

    # --- RULES BLOCK ---
    rules_state = data.get("rules")
    if rules_engine is not None and isinstance(rules_state, dict):
        rules_engine.load_from_json(rules_state)

    # --- BACKGROUND STATE ---
    bg_state = None
    bg_block = data.get("background")
    if isinstance(bg_block, dict):
        cam = bg_block.get("camera", {}) or {}
        bg_state = {
            "path": bg_block.get("path", ""),
            "camera": {
                "x": float(cam.get("x", 0.0)),
                "y": float(cam.get("y", 0.0)),
                "zoom": float(cam.get("zoom", 1.0)),
            },
        }

    print(f"[INFO] Loaded campaign: {os.path.basename(path)} (v{version})")
    return bg_state


def export_token(path, token):
    """
    Export a single token as JSON:
    {
      "version": 1,
      "asset": "<asset name>",
      "data": { ... full token dict ... }
    }
    """
    if not path or token is None:
        return

    token_dict = token.to_dict()
    tint = token_dict.get("tint", [1.0, 1.0, 1.0])
    if isinstance(tint, (list, tuple)) and len(tint) == 3:
        vals = []
        for v in tint:
            if v is None:
                vals.append(255)
                continue
            if v > 1.0:
                vals.append(int(max(0, min(255, v))))
            else:
                vals.append(int(max(0, min(255, v * 255.0))))
        token_dict["tint"] = vals

    data = {
        "version": 1,
        "asset": token.asset,
        "data": token_dict,
    }

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Exported token {token.id} to {os.path.basename(path)}")


def import_token(path, asset_mgr, token_mgr):
    """
    Import a single token JSON file and instantiate it.
    Returns the created Token or None.
    """
    if not path or not os.path.exists(path):
        print(f"[ERROR] Token file not found: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load token JSON: {e}")
        return None

    if not isinstance(data, dict):
        print("[ERROR] Token JSON has invalid structure.")
        return None

    asset_name = data.get("asset")
    token_data = data.get("data")
    if not isinstance(token_data, dict):
        print("[ERROR] Token JSON missing 'data' dict.")
        return None

    if "asset" not in token_data:
        token_data["asset"] = asset_name or "__missing__"

    if asset_name and asset_name in asset_mgr.assets:
        token_data["asset"] = asset_name
    else:
        print(f"[WARNING] Imported token asset missing: {asset_name} – using placeholder")
        asset_mgr.ensure_placeholder_asset()
        token_data["asset"] = "__missing__"

    tint = token_data.get("tint")
    if isinstance(tint, (list, tuple)) and len(tint) == 3:
        vals = list(tint)
        if any(v is not None and v > 1.0 for v in vals):
            new_vals = []
            for v in vals:
                if v is None:
                    new_vals.append(1.0)
                else:
                    new_vals.append(max(0.0, min(1.0, v / 255.0)))
            token_data["tint"] = new_vals

    t = token_mgr.create_token_from_dict(token_data)
    if t:
        print(f"[INFO] Imported token {t.id} from {os.path.basename(path)}")
    return t
