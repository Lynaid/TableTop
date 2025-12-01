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
        # world-space position (board space, not screen)
        self.x = float(x)
        self.y = float(y)
        self.w = self.surface.get_width()
        self.h = self.surface.get_height()
        self.dragging = False
        self.offset_x = 0.0
        self.offset_y = 0.0
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
        self.border_style = "none"  # none, solid, dotted
        # preview world position
        self.preview_x = None
        self.preview_y = None

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update_transformed_surface(self):
        surf = self.original_surface
        if self.scale != 1.0:
            new_w = max(1, int(self.original_surface.get_width() * self.scale))
            new_h = max(1, int(self.original_surface.get_height() * self.scale))
            try:
                surf = pygame.transform.smoothscale(self.original_surface, (new_w, new_h))
            except Exception:
                surf = pygame.transform.scale(self.original_surface, (new_w, new_h))
        if self.rotation != 0:
            surf = pygame.transform.rotate(surf, self.rotation)
        try:
            arr = surf.copy()
            tint_surf = pygame.Surface(arr.get_size(), flags=pygame.SRCALPHA)
            r = int(self.tint[0] * 255)
            g = int(self.tint[1] * 255)
            b = int(self.tint[2] * 255)
            tint_surf.fill((r, g, b, 255))
            arr.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_MULT)
            surf = arr
        except Exception:
            pass
        self.surface = surf
        self.w = self.surface.get_width()
        self.h = self.surface.get_height()

    def draw(self, surf, camera_x, camera_y, camera_zoom, board_rect):
        if not self.visible:
            return

        wx = self.preview_x if self.preview_x is not None else self.x
        wy = self.preview_y if self.preview_y is not None else self.y

        sx = (wx - camera_x) * camera_zoom + board_rect.x
        sy = (wy - camera_y) * camera_zoom + board_rect.y

        try:
            tmp = pygame.transform.smoothscale(
                self.surface,
                (int(self.w * camera_zoom), int(self.h * camera_zoom)),
            )
        except Exception:
            tmp = pygame.transform.scale(
                self.surface,
                (max(1, int(self.w * camera_zoom)), max(1, int(self.h * camera_zoom))),
            )

        surf.blit(tmp, (int(sx), int(sy)))

        if hasattr(self, "hp") and hasattr(self, "max_hp") and self.max_hp > 0:
            bar_w_world = min(80, self.w)
            bar_h_world = 8
            bx_world = self.x + (self.w - bar_w_world) / 2.0
            by_world = self.y + self.h + 4

            bx = (bx_world - camera_x) * camera_zoom + board_rect.x
            by = (by_world - camera_y) * camera_zoom + board_rect.y
            bw = bar_w_world * camera_zoom
            bh = bar_h_world * camera_zoom

            pygame.draw.rect(
                surf,
                (40, 40, 40),
                pygame.Rect(int(bx), int(by), int(bw), int(bh)),
                border_radius=3,
            )
            frac = max(0.0, min(1.0, self.hp / self.max_hp if self.max_hp else 0))
            fill_w = int(bw * frac)
            pygame.draw.rect(
                surf,
                (160, 50, 50),
                pygame.Rect(int(bx), int(by), fill_w, int(bh)),
                border_radius=3,
            )
            pygame.draw.rect(
                surf,
                (80, 80, 80),
                pygame.Rect(int(bx), int(by), int(bw), int(bh)),
                1,
                border_radius=3,
            )

        if self.border_style == "solid":
            bx = (self.x - 2 - camera_x) * camera_zoom + board_rect.x
            by = (self.y - 2 - camera_y) * camera_zoom + board_rect.y
            bw = (self.w + 4) * camera_zoom
            bh = (self.h + 4) * camera_zoom
            pygame.draw.rect(
                surf,
                (220, 220, 220),
                pygame.Rect(int(bx), int(by), int(bw), int(bh)),
                int(max(1, 2 * camera_zoom)),
            )
        elif self.border_style == "dotted":
            bx_world = self.x - 2
            by_world = self.y - 2
            bw_world = self.w + 4
            bh_world = self.h + 4
            step_world = 6
            # top/bottom
            x = bx_world
            while x < bx_world + bw_world:
                x2 = min(x + 2, bx_world + bw_world)
                sx1 = (x - camera_x) * camera_zoom + board_rect.x
                sx2 = (x2 - camera_x) * camera_zoom + board_rect.x
                sy_top = (by_world - camera_y) * camera_zoom + board_rect.y
                sy_bottom = (by_world + bh_world - camera_y) * camera_zoom + board_rect.y
                pygame.draw.line(
                    surf,
                    (200, 200, 200),
                    (int(sx1), int(sy_top)),
                    (int(sx2), int(sy_top)),
                )
                pygame.draw.line(
                    surf,
                    (200, 200, 200),
                    (int(sx1), int(sy_bottom)),
                    (int(sx2), int(sy_bottom)),
                )
                x += step_world
            y = by_world
            while y < by_world + bh_world:
                y2 = min(y + 2, by_world + bh_world)
                sy1 = (y - camera_y) * camera_zoom + board_rect.y
                sy2 = (y2 - camera_y) * camera_zoom + board_rect.y
                sx_left = (bx_world - camera_x) * camera_zoom + board_rect.x
                sx_right = (bx_world + bw_world - camera_x) * camera_zoom + board_rect.x
                pygame.draw.line(
                    surf,
                    (200, 200, 200),
                    (int(sx_left), int(sy1)),
                    (int(sx_left), int(sy2)),
                )
                pygame.draw.line(
                    surf,
                    (200, 200, 200),
                    (int(sx_right), int(sy1)),
                    (int(sx_right), int(sy2)),
                )
                y += step_world

    def draw_preview(self, surf, camera_x, camera_y, camera_zoom, board_rect):
        if not self.visible or self.preview_x is None or self.preview_y is None:
            return
        wx, wy = self.preview_x, self.preview_y
        sx = (wx - camera_x) * camera_zoom + board_rect.x
        sy = (wy - camera_y) * camera_zoom + board_rect.y
        try:
            temp = pygame.transform.smoothscale(
                self.surface,
                (int(self.w * camera_zoom), int(self.h * camera_zoom)),
            )
        except Exception:
            temp = pygame.transform.scale(
                self.surface,
                (max(1, int(self.w * camera_zoom)), max(1, int(self.h * camera_zoom))),
            )
        try:
            temp = temp.copy()
            temp.fill((255, 255, 255, 160), special_flags=pygame.BLEND_RGBA_MULT)
        except Exception:
            pass
        surf.blit(temp, (int(sx), int(sy)))

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
            "name": self.name,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "notes": self.notes,
            "gm_only_notes": self.gm_only_notes,
            "tint": list(self.tint),
            "border_style": self.border_style,
        }

    @staticmethod
    def from_dict(d, asset_surface_lookup):
        surf = asset_surface_lookup.get(d["asset"])
        if not surf:
            return None
        t = Token(d["asset"], surf, d.get("x", 0), d.get("y", 0))
        t.id = d.get("id", t.id)
        t.visible = d.get("visible", True)
        t.rotation = d.get("rotation", 0)
        t.scale = d.get("scale", 1.0)
        t.name = d.get("name", "Token")
        t.hp = d.get("hp", 1)
        t.max_hp = d.get("max_hp", 1)
        t.notes = d.get("notes", "")
        t.gm_only_notes = d.get("gm_only_notes", False)
        tint = d.get("tint", [1.0, 1.0, 1.0])
        t.tint = tuple(tint)
        t.border_style = d.get("border_style", "none")
        t.update_transformed_surface()
        return t


class TokenManager:
    def __init__(self, asset_manager):
        self.asset_manager = asset_manager
        self.tokens = []
        self.last_action = None

    def spawn_token(self, asset_name, x, y):
        meta = self.asset_manager.assets.get(asset_name)
        if not meta:
            print("Asset not found:", asset_name)
            return None
        surf = meta["surface"]
        t = Token(asset_name, surf, x, y)
        t.name = asset_name
        t.hp = 5
        t.max_hp = 5
        self.tokens.append(t)
        return t

    def find_token_at_world(self, wx, wy):
        for t in reversed(self.tokens):
            if t.rect().collidepoint(int(wx), int(wy)):
                return t
        return None

    def handle_event(
        self,
        event,
        grid_size=32,
        snap_enabled=True,
        camera_x=0.0,
        camera_y=0.0,
        camera_zoom=1.0,
        board_rect=None,
    ):
        if board_rect is None:
            board_rect = pygame.Rect(0, 0, 0, 0)

        def to_world(pos):
            sx, sy = pos
            local_x = sx - board_rect.x
            local_y = sy - board_rect.y
            wx = local_x / camera_zoom + camera_x
            wy = local_y / camera_zoom + camera_y
            return wx, wy

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not board_rect.collidepoint(event.pos):
                return None
            wx, wy = to_world(event.pos)
            for t in reversed(self.tokens):
                if t.rect().collidepoint(int(wx), int(wy)):
                    t.dragging = True
                    t.offset_x = wx - t.x
                    t.offset_y = wy - t.y
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
            wx, wy = to_world(event.pos)
            for t in self.tokens:
                if t.dragging:
                    raw_x = wx - t.offset_x
                    raw_y = wy - t.offset_y
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
            if not board_rect.collidepoint(event.pos):
                return None
            wx, wy = to_world(event.pos)
            t = self.find_token_at_world(wx, wy)
            if t:
                return {"token": t, "pos": event.pos}
        return None

    def perform_menu_action(self, token, action):
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
        token.name = newdata.get("name", token.name)
        max_hp_new = int(max(1, newdata.get("max_hp", token.max_hp)))
        hp_new = int(newdata.get("hp", token.hp))
        hp_new = max(0, min(max_hp_new, hp_new))
        token.max_hp = max_hp_new
        token.hp = hp_new
        token.notes = newdata.get("notes", token.notes)
        token.gm_only_notes = bool(newdata.get("gm_only_notes", token.gm_only_notes))
        tint = newdata.get("tint", token.tint)
        token.tint = tuple(max(0.0, min(1.0, c)) for c in tint)
        token.border_style = newdata.get("border_style", token.border_style)
        token.update_transformed_surface()

    def update(self, dt):
        pass

    def draw(
        self,
        screen,
        camera_x,
        camera_y,
        camera_zoom,
        board_rect,
        grid_size=32,
        show_snap_preview=True,
    ):
        for t in self.tokens:
            if t.dragging and show_snap_preview and t.preview_x is not None:
                t.draw_preview(screen, camera_x, camera_y, camera_zoom, board_rect)
            else:
                t.preview_x = None if not t.dragging else t.preview_x
                t.preview_y = None if not t.dragging else t.preview_y
                t.draw(screen, camera_x, camera_y, camera_zoom, board_rect)

    def to_json(self):
        return [t.to_dict() for t in self.tokens]

    def load_from_json(self, data):
        self.tokens = []
        lookup = {name: meta["surface"] for name, meta in self.asset_manager.assets.items()}
        for d in data:
            t = Token.from_dict(d, lookup)
            if t:
                self.tokens.append(t)
