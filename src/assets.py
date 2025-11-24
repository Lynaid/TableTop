import os
from PIL import Image
import pygame
import shutil
import tkinter as tk
from tkinter import filedialog
import json

class AssetManager:
    def __init__(self, assets_dir):
        self.assets_dir = os.path.abspath(assets_dir)
        os.makedirs(self.assets_dir, exist_ok=True)
        self.assets = {}  # name -> {'path':..., 'surface':pygame.Surface}
        self.registry_path = os.path.join(self.assets_dir, "registry.json")
        self._load_registry()

    def _load_registry(self):
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, meta in data.items():
                    p = meta.get("path")
                    if p and os.path.exists(p):
                        surf = self._load_surface(p)
                        if surf:
                            self.assets[name] = {"path":p, "surface":surf}
            except Exception:
                pass

    def _save_registry(self):
        data = {name: {"path":m["path"]} for name,m in self.assets.items()}
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def import_asset_dialog(self):
        root = tk.Tk()
        root.withdraw()
        fp = filedialog.askopenfilename(title="Select image", filetypes=[("Images","*.png;*.jpg;*.jpeg;*.bmp")])
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
                self.assets[os.path.basename(dest)] = {"path": dest, "surface": surf}
                self._save_registry()
                print("Imported", dest)
                return dest
        except Exception as e:
            print("Import failed:", e)
            return None

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
