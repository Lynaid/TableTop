import random
import json
import os


def roll_dice(sides=6):
    return random.randint(1, sides)


def save_campaign(path, asset_mgr, token_mgr, background_state=None):
    data = {
        "assets": {name: {"path": meta["path"]} for name, meta in asset_mgr.assets.items()},
        "tokens": token_mgr.to_json(),
    }
    if background_state is not None:
        data["background"] = background_state
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_campaign(path, asset_mgr, token_mgr):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for name, m in data.get("assets", {}).items():
        p = m.get("path")
        if p and os.path.exists(p) and name not in asset_mgr.assets:
            surf = asset_mgr._load_surface(p)
            if surf:
                asset_mgr.assets[name] = {"path": p, "surface": surf}
    token_mgr.load_from_json(data.get("tokens", []))
    return data.get("background", None)
