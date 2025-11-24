import pygame
import uuid
import json
import math

class Token:
    def __init__(self, asset_name, surface, x=0, y=0):
        self.id = str(uuid.uuid4())[:8]
        self.asset = asset_name
        self.original_surface = surface
        self.surface = surface.copy()
        self.x = x
        self.y = y
        self.w = self.surface.get_width()
        self.h = self.surface.get_height()
        self.dragging = False
        self.offset_x = 0
        self.offset_y = 0
        self.visible = True
        self.rotation = 0
        self.scale = 1.0
        # Advanced properties
        self.name = "Token"
        self.hp = 1
        self.max_hp = 1
        self.notes = ""
        self.gm_only_notes = False
        # tint as (r,g,b) floats 0-1
        self.tint = (1.0, 1.0, 1.0)
        self.border_style = "none"  # options: none, solid, dotted
        # preview
        self.preview_x = None
        self.preview_y = None

    def rect(self):
        return pygame.Rect(self.x, self.y, self.w, self.h)

    def update_transformed_surface(self):
        surf = self.original_surface
        # apply scale
        if self.scale != 1.0:
            new_w = max(1, int(self.original_surface.get_width() * self.scale))
            new_h = max(1, int(self.original_surface.get_height() * self.scale))
            try:
                surf = pygame.transform.smoothscale(self.original_surface, (new_w, new_h))
            except Exception:
                surf = pygame.transform.scale(self.original_surface, (new_w, new_h))
        # apply rotate
        if self.rotation != 0:
            surf = pygame.transform.rotate(surf, self.rotation)
        # apply tint by multiplying channels
        try:
            arr = surf.copy()
            # tint using a simple surface fill with BLEND_MULT
            tint_surf = pygame.Surface(arr.get_size(), flags=pygame.SRCALPHA)
            r = int(self.tint[0]*255)
            g = int(self.tint[1]*255)
            b = int(self.tint[2]*255)
            tint_surf.fill((r,g,b,255))
            arr.blit(tint_surf, (0,0), special_flags=pygame.BLEND_MULT)
            surf = arr
        except Exception:
            pass
        self.surface = surf
        self.w = self.surface.get_width()
        self.h = self.surface.get_height()

    def draw(self, surf):
        if not self.visible:
            return
        surf.blit(self.surface, (self.x, self.y))
        # draw HP bar if hp/max_hp available
        if hasattr(self, "hp") and hasattr(self, "max_hp") and self.max_hp > 0:
            bar_w = min(80, self.w)
            bar_h = 8
            bx = self.x + (self.w - bar_w)//2
            by = self.y + self.h + 4
            # background
            pygame.draw.rect(surf, (40,40,40), (bx,by,bar_w,bar_h), border_radius=3)
            # filled
            frac = max(0.0, min(1.0, self.hp / self.max_hp if self.max_hp else 0))
            fill_w = int(bar_w * frac)
            pygame.draw.rect(surf, (160,50,50), (bx,by,fill_w,bar_h), border_radius=3)
            # border
            pygame.draw.rect(surf, (80,80,80), (bx,by,bar_w,bar_h), 1, border_radius=3)
        # border style
        if self.border_style == "solid":
            pygame.draw.rect(surf, (220,220,220), (self.x-2, self.y-2, self.w+4, self.h+4), 2)
        elif self.border_style == "dotted":
            # simple dotted border
            bx, by, bw, bh = self.x-2, self.y-2, self.w+4, self.h+4
            step = 6
            for i in range(bx, bx + bw, step):
                pygame.draw.line(surf, (200,200,200), (i, by), (i+2, by))
                pygame.draw.line(surf, (200,200,200), (i, by+bh), (i+2, by+bh))
            for j in range(by, by + bh, step):
                pygame.draw.line(surf, (200,200,200), (bx, j), (bx, j+2))
                pygame.draw.line(surf, (200,200,200), (bx+bw, j), (bx+bw, j+2))

    def draw_preview(self, surf):
        if not self.visible or self.preview_x is None or self.preview_y is None:
            return
        temp = self.surface.copy()
        try:
            temp.fill((255,255,255,160), special_flags=pygame.BLEND_RGBA_MULT)
        except Exception:
            pass
        surf.blit(temp, (self.preview_x, self.preview_y))

    def snap_to_grid(self, grid_size):
        if grid_size <= 0:
            return
        nx = round(self.x / grid_size) * grid_size
        ny = round(self.y / grid_size) * grid_size
        self.x, self.y = nx, ny

    def to_dict(self):
        return {
            "id": self.id,
            "asset": self.asset,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "scale": self.scale,
            "visible": self.visible,
            # advanced props
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "notes": self.notes,
            "gm_only_notes": self.gm_only_notes,
            "tint": list(self.tint),
            "border_style": self.border_style
        }

    @staticmethod
    def from_dict(d, asset_surface_lookup):
        surf = asset_surface_lookup.get(d["asset"])
        if not surf:
            return None
        t = Token(d["asset"], surf, d.get("x",0), d.get("y",0))
        t.id = d.get("id", t.id)
        t.visible = d.get("visible", True)
        t.rotation = d.get("rotation", 0)
        t.scale = d.get("scale", 1.0)
        # advanced
        t.name = d.get("name", "Token")
        t.hp = d.get("hp", 1)
        t.max_hp = d.get("max_hp", 1)
        t.notes = d.get("notes", "")
        t.gm_only_notes = d.get("gm_only_notes", False)
        tint = d.get("tint", [1.0,1.0,1.0])
        t.tint = tuple(tint)
        t.border_style = d.get("border_style", "none")
        t.update_transformed_surface()
        return t

class TokenManager:
    def __init__(self, asset_manager):
        self.asset_manager = asset_manager
        self.tokens = []
        self.last_action = None  # used to communicate properties request

    def spawn_token(self, asset_name, x, y):
        meta = self.asset_manager.assets.get(asset_name)
        if not meta:
            print("Asset not found:", asset_name)
            return None
        surf = meta["surface"]
        t = Token(asset_name, surf, x, y)
        # default properties
        t.name = asset_name
        t.hp = 5
        t.max_hp = 5
        self.tokens.append(t)
        return t

    def find_token_at(self, pos):
        mx,my = pos
        for t in reversed(self.tokens):
            if t.rect().collidepoint(mx,my):
                return t
        return None

    def handle_event(self, event, grid_size=32, snap_enabled=True):
        # returns dict when right-click requested (opening any menu)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx,my = event.pos
            for t in reversed(self.tokens):
                if t.rect().collidepoint(mx,my):
                    t.dragging = True
                    t.offset_x = mx - t.x
                    t.offset_y = my - t.y
                    self.tokens.remove(t)
                    self.tokens.append(t)
                    t.preview_x = t.x
                    t.preview_y = t.y
                    break

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for t in self.tokens:
                if t.dragging:
                    t.dragging = False
                    if snap_enabled:
                        if t.preview_x is not None and t.preview_y is not None:
                            t.x = t.preview_x
                            t.y = t.preview_y
                        else:
                            t.snap_to_grid(grid_size)
                    t.preview_x = None
                    t.preview_y = None

        elif event.type == pygame.MOUSEMOTION:
            mx,my = event.pos
            for t in self.tokens:
                if t.dragging:
                    raw_x = mx - t.offset_x
                    raw_y = my - t.offset_y
                    if snap_enabled:
                        sx = round(raw_x / grid_size) * grid_size
                        sy = round(raw_y / grid_size) * grid_size
                        t.preview_x = sx
                        t.preview_y = sy
                    else:
                        t.x = raw_x
                        t.y = raw_y
                        t.preview_x = None
                        t.preview_y = None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            mx,my = event.pos
            t = self.find_token_at((mx,my))
            if t:
                # signal to main to open ContextMenu at pos. ContextMenu will call perform_menu_action
                return {"token": t, "pos": (mx,my)}
        return None

    def perform_menu_action(self, token, action):
        """Called by ContextMenu to perform an action on token.
           If action == 'properties' we set last_action so main can open the properties window.
        """
        if action == "rotate_cw":
            token.rotation = (token.rotation - 45) % 360
            token.update_transformed_surface()
        elif action == "rotate_ccw":
            token.rotation = (token.rotation + 45) % 360
            token.update_transformed_surface()
        elif action == "scale_up":
            token.scale = round(token.scale * 1.1, 3)
            token.update_transformed_surface()
        elif action == "scale_down":
            token.scale = round(token.scale / 1.1, 3)
            token.update_transformed_surface()
        elif action == "delete":
            try:
                self.tokens.remove(token)
            except ValueError:
                pass
        elif action == "properties":
            self.last_action = {"action": "properties", "token": token}

    def apply_token_properties(self, token, newdata):
        """Apply properties dict to token. Called by PropertiesWindow on Apply."""
        token.name = newdata.get("name", token.name)
        token.hp = int(max(0, min(newdata.get("max_hp", token.max_hp), newdata.get("hp", token.hp))))
        token.max_hp = int(max(1, newdata.get("max_hp", token.max_hp)))
        token.notes = newdata.get("notes", token.notes)
        token.gm_only_notes = bool(newdata.get("gm_only_notes", token.gm_only_notes))
        tint = newdata.get("tint", token.tint)
        token.tint = tuple(max(0.0, min(1.0, c)) for c in tint)
        token.border_style = newdata.get("border_style", token.border_style)
        token.update_transformed_surface()

    def update(self, dt):
        pass

    def draw(self, screen, grid_size=32, show_snap_preview=True):
        for t in self.tokens:
            if t.dragging and show_snap_preview and t.preview_x is not None:
                t.draw_preview(screen)
            else:
                t.draw(screen)

    def to_json(self):
        return [t.to_dict() for t in self.tokens]

    def load_from_json(self, data):
        self.tokens = []
        lookup = {name:meta["surface"] for name,meta in self.asset_manager.assets.items()}
        for d in data:
            t = Token.from_dict(d, lookup)
            if t:
                self.tokens.append(t)
