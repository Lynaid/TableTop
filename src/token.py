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
        # world-space position
        self.x = float(x)
        self.y = float(y)
        self.w = self.surface.get_width()
        self.h = self.surface.get_height()
        # dragging / movement
        self.dragging = False
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.preview_x = None
        self.preview_y = None
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
        # locking
        self.locked = False
        # grouping
        self.group_id = None  # uuid string or None
        # z-index (render order)
        self.z_index = 0

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

    def _world_to_screen_rect(self, camera_x, camera_y, camera_zoom, board_rect):
        sx = (self.x - camera_x) * camera_zoom + board_rect.x
        sy = (self.y - camera_y) * camera_zoom + board_rect.y
        sw = self.w * camera_zoom
        sh = self.h * camera_zoom
        return pygame.Rect(int(sx), int(sy), int(sw), int(sh))

    def draw(self, surf, camera_x, camera_y, camera_zoom, board_rect, selected=False):
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

        # HP bar
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

        # border style
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

        # selection highlight
        if selected:
            r = self._world_to_screen_rect(camera_x, camera_y, camera_zoom, board_rect)
            pygame.draw.rect(
                surf,
                (255, 255, 0),
                r.inflate(4, 4),
                max(1, int(2 * camera_zoom)),
            )

        # lock indicator
        if self.locked:
            r = self._world_to_screen_rect(camera_x, camera_y, camera_zoom, board_rect)
            sz = max(8, int(10 * camera_zoom))
            pad = max(2, int(3 * camera_zoom))
            lock_rect = pygame.Rect(
                r.right - sz - pad,
                r.y + pad,
                sz,
                sz,
            )
            pygame.draw.rect(surf, (40, 40, 40), lock_rect, border_radius=3)
            pygame.draw.rect(surf, (200, 200, 200), lock_rect, 1, border_radius=3)
            shackle_rect = pygame.Rect(
                lock_rect.x + sz // 4,
                lock_rect.y - sz // 2,
                sz // 2,
                sz // 2,
            )
            pygame.draw.rect(surf, (40, 40, 40), shackle_rect, border_radius=sz // 4)
            pygame.draw.rect(surf, (200, 200, 200), shackle_rect, 1, border_radius=sz // 4)

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
            "locked": self.locked,
            "group_id": self.group_id,
            "z_index": self.z_index,
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
        t.locked = d.get("locked", False)
        t.group_id = d.get("group_id", None)
        t.z_index = d.get("z_index", 0)
        t.update_transformed_surface()
        return t


class TokenManager:
    def __init__(self, asset_manager):
        self.asset_manager = asset_manager
        self.tokens = []
        self.last_action = None
        # selection / grouping
        self.selected_tokens = []  # list of Token
        self.selection_dragging = False
        self.selection_start_world = (0.0, 0.0)
        self.selection_end_world = (0.0, 0.0)

    # ---------- Z-INDEX HELPERS ----------

    def _max_z_index(self):
        if not self.tokens:
            return 0
        return max(t.z_index for t in self.tokens)

    def _min_z_index(self):
        if not self.tokens:
            return 0
        return min(t.z_index for t in self.tokens)

    def _sorted_by_z(self, reverse=False):
        return sorted(self.tokens, key=lambda t: t.z_index, reverse=reverse)

    # ---------- SPAWN ----------

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
        t.z_index = self._max_z_index() + 1
        self.tokens.append(t)
        return t

    # ---------- PICKING (PIXEL PERFECT) ----------

    def _pick_token_at_world(self, wx, wy):
        for t in self._sorted_by_z(reverse=True):
            if not t.visible:
                continue
            # rough rect check
            lx = int(wx - t.x)
            ly = int(wy - t.y)
            if lx < 0 or ly < 0 or lx >= t.w or ly >= t.h:
                continue
            try:
                col = t.surface.get_at((lx, ly))
            except Exception:
                continue
            if len(col) == 4:
                if col[3] > 0:
                    return t
            else:
                return t
        return None

    # ---------- SELECTION UTILS ----------

    def _is_selected(self, token):
        return token in self.selected_tokens

    def _set_single_selection(self, token):
        self.selected_tokens = [token] if token else []

    def _toggle_selection(self, token):
        if token in self.selected_tokens:
            self.selected_tokens.remove(token)
        else:
            self.selected_tokens.append(token)

    def _clear_selection(self):
        self.selected_tokens = []

    def _select_in_rect_world(self, x1, y1, x2, y2):
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        self.selected_tokens = []
        for t in self.tokens:
            r = t.rect()
            if r.right < left or r.left > right or r.bottom < top or r.top > bottom:
                continue
            self.selected_tokens.append(t)

    # ---------- GROUP HELPERS ----------

    def _tokens_in_group(self, group_id):
        if group_id is None:
            return []
        return [t for t in self.tokens if t.group_id == group_id]

    def _group_selected(self):
        # only group if multiple selected
        if len(self.selected_tokens) < 2:
            return
        gid = str(uuid.uuid4())
        for t in self.selected_tokens:
            t.group_id = gid
        # align z_index group: all take max z of group
        max_z = max(t.z_index for t in self.selected_tokens)
        for t in self.selected_tokens:
            t.z_index = max_z

    def _ungroup_token_or_selection(self, token):
        # if selection has multiple grouped tokens, ungroup all selection
        if self.selected_tokens and any(t.group_id for t in self.selected_tokens):
            for t in self.selected_tokens:
                t.group_id = None
            return
        # else, ungroup clicked token's group
        if token.group_id:
            gid = token.group_id
            for t in self._tokens_in_group(gid):
                t.group_id = None

    # ---------- Z-INDEX ACTIONS ----------

    def _bring_to_front(self, token):
        max_z = self._max_z_index()
        if token.group_id:
            group_tokens = self._tokens_in_group(token.group_id)
            for t in group_tokens:
                t.z_index = max_z + 1
        else:
            token.z_index = max_z + 1

    def _send_to_back(self, token):
        min_z = self._min_z_index()
        if token.group_id:
            group_tokens = self._tokens_in_group(token.group_id)
            for t in group_tokens:
                t.z_index = min_z - 1
        else:
            token.z_index = min_z - 1

    def _move_up_one(self, token):
        if not self.tokens:
            return
        if token.group_id:
            group_tokens = self._tokens_in_group(token.group_id)
            max_group_z = max(t.z_index for t in group_tokens)
            above = [t for t in self.tokens if t.z_index > max_group_z]
            if not above:
                return
            target = min(above, key=lambda t: t.z_index)
            dz = target.z_index - max_group_z
            for t in group_tokens:
                t.z_index += dz
        else:
            above = [t for t in self.tokens if t.z_index > token.z_index]
            if not above:
                return
            target = min(above, key=lambda t: t.z_index)
            token.z_index, target.z_index = target.z_index, token.z_index

    def _move_down_one(self, token):
        if not self.tokens:
            return
        if token.group_id:
            group_tokens = self._tokens_in_group(token.group_id)
            min_group_z = min(t.z_index for t in group_tokens)
            below = [t for t in self.tokens if t.z_index < min_group_z]
            if not below:
                return
            target = max(below, key=lambda t: t.z_index)
            dz = min_group_z - target.z_index
            for t in group_tokens:
                t.z_index -= dz
        else:
            below = [t for t in self.tokens if t.z_index < token.z_index]
            if not below:
                return
            target = max(below, key=lambda t: t.z_index)
            token.z_index, target.z_index = target.z_index, token.z_index

    # ---------- HANDLE EVENTS ----------

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

        mods = pygame.key.get_mods()
        ctrl_down = bool(mods & pygame.KMOD_CTRL)

        # LEFT MOUSE DOWN
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not board_rect.collidepoint(event.pos):
                return None
            wx, wy = to_world(event.pos)
            clicked_token = self._pick_token_at_world(wx, wy)

            # selection logic
            if ctrl_down:
                if clicked_token:
                    self._toggle_selection(clicked_token)
            else:
                if clicked_token:
                    if not self._is_selected(clicked_token):
                        self._set_single_selection(clicked_token)
                else:
                    # start drag-select box
                    self.selection_dragging = True
                    self.selection_start_world = (wx, wy)
                    self.selection_end_world = (wx, wy)
                    return None

            # start dragging (single/group/selection) if token and not locked
            if clicked_token and not clicked_token.locked:
                # determine drag set
                drag_set = []
                if clicked_token.group_id:
                    drag_set = [t for t in self._tokens_in_group(clicked_token.group_id) if not t.locked]
                elif self.selected_tokens and clicked_token in self.selected_tokens and len(self.selected_tokens) > 1:
                    drag_set = [t for t in self.selected_tokens if not t.locked]
                else:
                    drag_set = [clicked_token]

                for t in drag_set:
                    t.dragging = True
                    t.offset_x = wx - t.x
                    t.offset_y = wy - t.y
                    t.preview_x = t.x
                    t.preview_y = t.y

            return None

        # LEFT MOUSE UP
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # finish drag-select
            if self.selection_dragging:
                wx, wy = to_world(event.pos)
                self.selection_end_world = (wx, wy)
                self._select_in_rect_world(
                    self.selection_start_world[0],
                    self.selection_start_world[1],
                    self.selection_end_world[0],
                    self.selection_end_world[1],
                )
                self.selection_dragging = False

            # finish dragging tokens
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

        # MOUSE MOVE
        elif event.type == pygame.MOUSEMOTION:
            wx, wy = to_world(event.pos)

            # update drag-select box
            if self.selection_dragging:
                self.selection_end_world = (wx, wy)

            # dragging tokens
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

        # RIGHT CLICK: context menu source
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if not board_rect.collidepoint(event.pos):
                return None
            wx, wy = to_world(event.pos)
            t = self._pick_token_at_world(wx, wy)
            if t:
                # ensure right-clicked token becomes primary selection
                if not self._is_selected(t):
                    self._set_single_selection(t)
                return {"token": t, "pos": event.pos}
        return None

    # ---------- CONTEXT MENU ACTIONS ----------

    def perform_menu_action(self, token, action):
        if action == "rotate_cw":
            if token.locked:
                return
            token.rotation = (token.rotation - 45) % 360
            token.update_transformed_surface()
        elif action == "rotate_ccw":
            if token.locked:
                return
            token.rotation = (token.rotation + 45) % 360
            token.update_transformed_surface()
        elif action == "scale_up":
            if token.locked:
                return
            token.scale = round(token.scale * 1.1, 3)
            token.update_transformed_surface()
        elif action == "scale_down":
            if token.locked:
                return
            token.scale = round(token.scale / 1.1, 3)
            token.update_transformed_surface()
        elif action == "delete":
            try:
                self.tokens.remove(token)
            except ValueError:
                pass
            if token in self.selected_tokens:
                self.selected_tokens.remove(token)
        elif action == "properties":
            self.last_action = {"action": "properties", "token": token}
        elif action == "lock":
            token.locked = True
        elif action == "unlock":
            token.locked = False
        elif action == "group_selected":
            self._group_selected()
        elif action == "ungroup":
            self._ungroup_token_or_selection(token)
        elif action == "z_front":
            self._bring_to_front(token)
        elif action == "z_back":
            self._send_to_back(token)
        elif action == "z_up":
            self._move_up_one(token)
        elif action == "z_down":
            self._move_down_one(token)

    # ---------- UPDATE / DRAW / SERIALIZE ----------

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
        # tokens
        for t in self._sorted_by_z():
            if t.dragging and show_snap_preview and t.preview_x is not None:
                t.draw_preview(screen, camera_x, camera_y, camera_zoom, board_rect)
            else:
                t.draw(
                    screen,
                    camera_x,
                    camera_y,
                    camera_zoom,
                    board_rect,
                    selected=self._is_selected(t),
                )

        # selection rectangle overlay
        if self.selection_dragging:
            x1, y1 = self.selection_start_world
            x2, y2 = self.selection_end_world
            left = min(x1, x2)
            right = max(x1, x2)
            top = min(y1, y2)
            bottom = max(y1, y2)

            sx1 = (left - camera_x) * camera_zoom + board_rect.x
            sy1 = (top - camera_y) * camera_zoom + board_rect.y
            sx2 = (right - camera_x) * camera_zoom + board_rect.x
            sy2 = (bottom - camera_y) * camera_zoom + board_rect.y

            rect = pygame.Rect(
                int(sx1),
                int(sy1),
                int(sx2 - sx1),
                int(sy2 - sy1),
            )
            pygame.draw.rect(screen, (255, 255, 0), rect, 1)
            inner = rect.inflate(-2, -2)
            pygame.draw.rect(screen, (255, 255, 0), inner, 1)

    def to_json(self):
        return [t.to_dict() for t in self.tokens]

    def load_from_json(self, data):
        self.tokens = []
        self.selected_tokens = []
        self.selection_dragging = False
        lookup = {name: meta["surface"] for name, meta in self.asset_manager.assets.items()}
        for d in data:
            t = Token.from_dict(d, lookup)
            if t:
                self.tokens.append(t)
