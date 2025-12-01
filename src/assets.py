import os
import pygame
import shutil
import tkinter as tk
from tkinter import filedialog
from PIL import Image


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")


class AssetManager:
    """
    Asset manager with thumbnail + metadata caching.

    self.assets[name] = {
        "path": full_path,
        "surface": pygame.Surface,
        "thumb": pygame.Surface (thumbnail),
        "size": file_size_bytes,
        "last_modified": mtime_int,
        "date_added": int_timestamp (first time seen)
    }

    Thumbnails are only rebuilt when the file changes on disk.
    """

    def __init__(self, assets_dir):
        self.assets_dir = os.path.abspath(assets_dir)
        os.makedirs(self.assets_dir, exist_ok=True)
        self.assets = {}
        self._placeholder_surface = None
        self.refresh_assets()

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

    def _make_thumb(self, surface, max_dim=64):
        w = surface.get_width()
        h = surface.get_height()
        if w <= 0 or h <= 0:
            return None
        scale = min(max_dim / float(w), max_dim / float(h), 1.0)
        tw = max(1, int(w * scale))
        th = max(1, int(h * scale))
        try:
            thumb = pygame.transform.smoothscale(surface, (tw, th))
        except Exception:
            thumb = pygame.transform.scale(surface, (tw, th))
        return thumb

    def refresh_assets(self):
        """
        Rescan the assets directory (including subfolders) and rebuild metadata.
        Existing cached surfaces/thumbnails are reused if file path + mtime match.
        """
        old = self.assets
        new_assets = {}

        for root, _, files in os.walk(self.assets_dir):
            for fn in files:
                if not fn.lower().endswith(IMAGE_EXTS):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, self.assets_dir)
                name = rel.replace("\\", "/")

                try:
                    mtime = int(os.path.getmtime(full))
                    size = os.path.getsize(full)
                except OSError:
                    continue

                prev = old.get(name)
                if (
                    prev
                    and prev.get("path") == full
                    and prev.get("last_modified") == mtime
                    and "surface" in prev
                    and "thumb" in prev
                ):
                    new_assets[name] = prev
                    continue

                surf = self._load_surface(full)
                if not surf:
                    continue
                thumb = self._make_thumb(surf)
                new_assets[name] = {
                    "path": full,
                    "surface": surf,
                    "thumb": thumb,
                    "size": size,
                    "last_modified": mtime,
                    "date_added": prev.get("date_added", mtime) if prev else mtime,
                }

        self.assets = new_assets

    def get_categories(self):
        """
        Return a sorted list of top-level subfolder names under assets_dir
        present in current assets.
        """
        cats = set()
        for meta in self.assets.values():
            rel = os.path.relpath(meta["path"], self.assets_dir)
            rel_dir = os.path.dirname(rel)
            if rel_dir and rel_dir != ".":
                top = rel_dir.replace("\\", "/").split("/")[0]
                cats.add(top)
        return sorted(cats)

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
            self.refresh_assets()
            print("Imported", dest)
            return dest
        except Exception as e:
            print("Import failed:", e)
            return None

    def ensure_placeholder_asset(self):
        """
        Ensure a global "__missing__" asset exists and return its surface.
        Used when campaign/token references assets that do not exist.
        """
        if self._placeholder_surface is None:
            surf = pygame.Surface((72, 72), pygame.SRCALPHA)
            surf.fill((180, 0, 0))
            try:
                font = pygame.font.SysFont(None, 18)
                txt = font.render("MISSING", True, (255, 255, 255))
                tx = (surf.get_width() - txt.get_width()) // 2
                ty = (surf.get_height() - txt.get_height()) // 2
                surf.blit(txt, (tx, ty))
            except Exception:
                pass
            self._placeholder_surface = surf
            self.assets["__missing__"] = {
                "path": "",
                "surface": self._placeholder_surface,
                "thumb": self._make_thumb(self._placeholder_surface),
                "size": 0,
                "last_modified": 0,
                "date_added": 0,
            }
        return self._placeholder_surface

    def load_or_get_asset(self, name, path):
        """
        Ensure an asset 'name' for 'path' is loaded and registered.
        Returns surface or None.
        """
        meta = self.assets.get(name)
        if meta and meta.get("path") == path and "surface" in meta:
            return meta["surface"]

        surf = self._load_surface(path)
        if not surf:
            return None
        thumb = self._make_thumb(surf)
        try:
            mtime = int(os.path.getmtime(path))
            size = os.path.getsize(path)
        except OSError:
            mtime = 0
            size = 0
        self.assets[name] = {
            "path": path,
            "surface": surf,
            "thumb": thumb,
            "size": size,
            "last_modified": mtime,
            "date_added": mtime,
        }
        return surf
