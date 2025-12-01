import os
from PIL import Image
import pygame
import shutil
import tkinter as tk
from tkinter import filedialog
import json
import time


class AssetManager:
    def __init__(self, assets_dir):
        self.assets_dir = os.path.abspath(assets_dir)
        os.makedirs(self.assets_dir, exist_ok=True)
        # assets[name] = {
        #   "path": <absolute file path>,
        #   "surface": pygame.Surface (full image),
        #   "thumb": pygame.Surface (cached thumbnail),
        #   "size": int (bytes),
        #   "date_added": float (timestamp)
        # }
        self.assets = {}
        self.registry_path = os.path.join(self.assets_dir, "registry.json")
        self._load_registry()
        # ensure thumbnails for all loaded assets
        for name in list(self.assets.keys()):
            self._ensure_thumbnail(name)

    def _load_registry(self):
        """Load registry.json and reconstruct assets with surfaces.

        Registry stores path, file size and date_added. Thumbnails are
        not stored on disk; they are (re)generated in memory and cached
        in self.assets[name]["thumb"].
        """
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, meta in data.items():
                    p = meta.get("path")
                    if p and os.path.exists(p):
                        surf = self._load_surface(p)
                        if surf:
                            try:
                                size = meta.get("size")
                                if size is None:
                                    size = os.path.getsize(p)
                            except Exception:
                                size = 0
                            date_added = meta.get("date_added")
                            if date_added is None:
                                date_added = time.time()
                            self.assets[name] = {
                                "path": p,
                                "surface": surf,
                                "size": size,
                                "date_added": date_added,
                            }
            except Exception:
                pass

    def _save_registry(self):
        """Persist registry without thumbnails (only disk info)."""
        data = {}
        for name, m in self.assets.items():
            data[name] = {
                "path": m["path"],
                "size": m.get("size", 0),
                "date_added": m.get("date_added", time.time()),
            }
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_surface(self, path):
        try:
            img = Image.open(path).convert("RGBA")
            mode = img.mode
            size = img.size
            data = img.tobytes()
            return pygame.image.fromstring(data, size, mode).convert_alpha()
        except Exception as e:
            print("Failed load surface:", e)
            return None

    def _ensure_thumbnail(self, name, max_size=(96, 96)):
        """Create and cache thumbnail surface for asset if missing.

        Thumbnails are stored in self.assets[name]["thumb"] as
        pygame.Surface instances. They are created once per asset
        or when the underlying full-size surface changes.
        """
        meta = self.assets.get(name)
        if not meta:
            return
        if meta.get("thumb") is not None and isinstance(meta.get("thumb"), pygame.Surface):
            return
        base = meta.get("surface")
        if base is None:
            return
        w, h = base.get_size()
        if w <= 0 or h <= 0:
            return
        max_w, max_h = max_size
        scale = min(1.0, max_w / float(w), max_h / float(h))
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        try:
            thumb = pygame.transform.smoothscale(base, (new_w, new_h))
        except Exception:
            thumb = pygame.transform.scale(base, (new_w, new_h))
        meta["thumb"] = thumb

    def import_asset_dialog(self):
        root = tk.Tk()
        root.withdraw()
        fp = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp")],
        )
        root.destroy()
        if not fp:
            return None
        try:
            base = os.path.basename(fp)
            dest = os.path.join(self.assets_dir, base)
            if os.path.exists(dest):
                name, ext = os.path.splitext(base)
                i = 1
                while True:
                    new = f"{name}_{i}{ext}"
                    dest = os.path.join(self.assets_dir, new)
                    if not os.path.exists(dest):
                        break
                    i += 1
            shutil.copy(fp, dest)
            surf = self._load_surface(dest)
            if surf:
                size = 0
                try:
                    size = os.path.getsize(dest)
                except Exception:
                    pass
                asset_name = os.path.basename(dest)
                self.assets[asset_name] = {
                    "path": dest,
                    "surface": surf,
                    "size": size,
                    "date_added": time.time(),
                }
                self._ensure_thumbnail(asset_name)
                self._save_registry()
                print("Imported", dest)
                return dest
        except Exception as e:
            print("Import failed:", e)
            return None

    def refresh_assets(self):
        """Rescan assets_dir for image files and update asset list.

        - New files are added.
        - Removed files are dropped.
        - Existing entries update size/path if needed.
        - Thumbnails are cached in self.assets[name]["thumb"] and
          are not recreated every frame.
        """
        exts = (".png", ".jpg", ".jpeg", ".bmp")
        seen_names = set()

        for root_dir, _, files in os.walk(self.assets_dir):
            for fname in files:
                if not fname.lower().endswith(exts):
                    continue
                path = os.path.join(root_dir, fname)
                seen_names.add(fname)
                size = 0
                try:
                    size = os.path.getsize(path)
                except Exception:
                    pass

                if fname in self.assets:
                    meta = self.assets[fname]
                    meta["path"] = path
                    meta["size"] = size
                    if "date_added" not in meta:
                        meta["date_added"] = time.time()
                    if meta.get("surface") is None:
                        surf = self._load_surface(path)
                        if surf:
                            meta["surface"] = surf
                            meta["thumb"] = None
                    self._ensure_thumbnail(fname)
                else:
                    surf = self._load_surface(path)
                    if surf:
                        self.assets[fname] = {
                            "path": path,
                            "surface": surf,
                            "size": size,
                            "date_added": time.time(),
                        }
                        self._ensure_thumbnail(fname)

        # remove entries for files no longer on disk
        to_remove = [name for name in self.assets.keys() if name not in seen_names]
        for name in to_remove:
            self.assets.pop(name, None)

        self._save_registry()

    def get_categories(self):
        """Return list of category names based on subfolders under assets_dir."""
        cats = set()
        for meta in self.assets.values():
            try:
                rel = os.path.relpath(meta["path"], self.assets_dir)
                parts = rel.split(os.sep)
                if len(parts) > 1:
                    cats.add(parts[0])
            except Exception:
                continue
        return sorted(cats)
