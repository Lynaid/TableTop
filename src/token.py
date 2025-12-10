import pygame
import uuid


class Token:
    def __init__(self, asset_name, surface, x=0, y=0):
        self.id = str(uuid.uuid4())[:8]
        self.asset = asset_name
        self.original_surface = surface
        self.surface = surface.copy()

        # world position
        self.x = float(x)
        self.y = float(y)

        self.w = self.surface.get_width()
        self.h = self.surface.get_height()

        # dragging
        self.dragging = False
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.preview_x = None
        self.preview_y = None
        self.drag_start_x = float(self.x)
        self.drag_start_y = float(self.y)

        # visibility / transform
        self.visible = True
        self.rotation = 0
        self.scale = 1.0

        # properties
        self.name = "Token"
        self.hp = 1
        self.max_hp = 1
        self.notes = ""
        self.gm_only_notes = False

        # tint 0–1 floats
        self.tint = (1.0, 1.0, 1.0)
        self.border_style = "none"

        # lock
        self.locked = False

        # grouping
        self.group_id = None

        # z-order
        self.z_index = 0

        # scripts per event_type, e.g. "onMove", "onRightClick", "onTurn", etc.
        self.scripts = {}

    # -----------------------------------------------------------
    # INTERNAL HELPERS
    # -----------------------------------------------------------

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def update_transformed_surface(self):
        surf = self.original_surface

        # scale
        if self.scale != 1.0:
            new_w = max(1, int(self.original_surface.get_width() * self.scale))
            new_h = max(1, int(self.original_surface.get_height() * self.scale))
            try:
                surf = pygame.transform.smoothscale(self.original_surface, (new_w, new_h))
            except Exception:
                surf = pygame.transform.scale(self.original_surface, (new_w, new_h))

        # rotate
        if self.rotation != 0:
            surf = pygame.transform.rotate(surf, self.rotation)

        # tint
        try:
            arr = surf.copy()
            tint_surf = pygame.Surface(arr.get_size(), pygame.SRCALPHA)
            r = int(self.tint[0] * 255)
            g = int(self.tint[1] * 255)
            b = int(self.tint[2] * 255)
            tint_surf.fill((r, g, b, 255))
            arr.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_MULT)
            surf = arr
        except Exception:
            pass

        self.surface = surf
        self.w = surf.get_width()
        self.h = surf.get_height()

    def _world_to_screen_rect(self, camera_x, camera_y, camera_zoom, board_rect):
        sx = (self.x - camera_x) * camera_zoom + board_rect.x
        sy = (self.y - camera_y) * camera_zoom + board_rect.y
        sw = self.w * camera_zoom
        sh = self.h * camera_zoom
        return pygame.Rect(int(sx), int(sy), int(sw), int(sh))

    # -----------------------------------------------------------
    # DRAWING
    # -----------------------------------------------------------

    def draw(
        self, surf, camera_x, camera_y, camera_zoom, board_rect, selected=False
    ):
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
        if self.max_hp > 0:
            bar_w_world = min(80, self.w)
            bar_h_world = 8

            bx_world = self.x + (self.w - bar_w_world) / 2
            by_world = self.y + self.h + 4

            bx = (bx_world - camera_x) * camera_zoom + board_rect.x
            by = (by_world - camera_y) * camera_zoom + board_rect.y
            bw = bar_w_world * camera_zoom
            bh = bar_h_world * camera_zoom

            pygame.draw.rect(
                surf, (40, 40, 40), (int(bx), int(by), int(bw), int(bh)), border_radius=3
            )

            frac = max(0.0, min(1.0, self.hp / self.max_hp))
            fw = int(bw * frac)

            pygame.draw.rect(
                surf, (160, 50, 50), (int(bx), int(by), fw, int(bh)), border_radius=3
            )

            pygame.draw.rect(
                surf,
                (80, 80, 80),
                (int(bx), int(by), int(bw), int(bh)),
                1,
                border_radius=3,
            )

        # border
        if self.border_style == "solid":
            r = self._world_to_screen_rect(camera_x, camera_y, camera_zoom, board_rect)
            pygame.draw.rect(surf, (220, 220, 220), r.inflate(4, 4), 2)
        elif self.border_style == "dotted":
            r = self._world_to_screen_rect(camera_x, camera_y, camera_zoom, board_rect)
            step = 6
            for x in range(r.x, r.x + r.w, step):
                surf.fill((200, 200, 200), (x, r.y, 2, 2))
                surf.fill((200, 200, 200), (x, r.y + r.h - 2, 2, 2))
            for y in range(r.y, r.y + r.h, step):
                surf.fill((200, 200, 200), (r.x, y, 2, 2))
                surf.fill((200, 200, 200), (r.x + r.w - 2, y, 2, 2))

        # selection
        if selected:
            r = self._world_to_screen_rect(camera_x, camera_y, camera_zoom, board_rect)
            pygame.draw.rect(surf, (255, 255, 0), r.inflate(4, 4), 2)

        # lock indicator
        if self.locked:
            r = self._world_to_screen_rect(camera_x, camera_y, camera_zoom, board_rect)
            s = max(8, int(12 * camera_zoom))
            icon = pygame.Rect(r.right - s - 4, r.y + 4, s, s)
            pygame.draw.rect(surf, (40, 40, 40), icon)
            pygame.draw.rect(surf, (200, 200, 200), icon, 1)

    def draw_preview(self, surf, camera_x, camera_y, camera_zoom, board_rect):
        if self.preview_x is None or self.preview_y is None:
            return
        wx, wy = self.preview_x, self.preview_y
        sx = (wx - camera_x) * camera_zoom + board_rect.x
        sy = (wy - camera_y) * camera_zoom + board_rect.y

        try:
            img = pygame.transform.smoothscale(
                self.surface,
                (int(self.w * camera_zoom), int(self.h * camera_zoom)),
            )
        except Exception:
            img = pygame.transform.scale(
                self.surface,
                (max(1, int(self.w * camera_zoom)), max(1, int(self.h * camera_zoom))),
            )

        img = img.copy()
        try:
            img.fill((255, 255, 255, 160), special_flags=pygame.BLEND_RGBA_MULT)
        except Exception:
            pass

        surf.blit(img, (int(sx), int(sy)))

    # -----------------------------------------------------------
    # SAVE/LOAD
    # -----------------------------------------------------------

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
            "scripts": dict(self.scripts),
        }

    @staticmethod
    def from_dict(d, asset_surface_lookup):
        asset_name = d.get("asset")
        if not asset_name:
            return None

        surf = asset_surface_lookup.get(asset_name)
        if not surf:
            return None

        t = Token(asset_name, surf, d.get("x", 0), d.get("y", 0))

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
        if any(v > 1 for v in tint):
            t.tint = tuple(max(0, min(1, v / 255.0)) for v in tint)
        else:
            t.tint = tuple(max(0, min(1, float(v))) for v in tint)

        t.border_style = d.get("border_style", "none")
        t.locked = d.get("locked", False)
        t.group_id = d.get("group_id", None)
        t.z_index = d.get("z_index", 0)
        t.scripts = dict(d.get("scripts", {}))

        t.update_transformed_surface()
        return t


class TokenManager:
    def __init__(self, asset_manager):
        self.asset_manager = asset_manager
        self.tokens = []
        self.last_action = None

        # selection
        self.selected_tokens = []
        self.selection_dragging = False
        self.selection_start_world = (0.0, 0.0)
        self.selection_end_world = (0.0, 0.0)

        # move events (for rule engine)
        self.pending_move_events = []

    # -----------------------------------------------------------
    # APPLY PROPERTIES (from PropertiesWindow)
    # -----------------------------------------------------------

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
        token.tint = tuple(max(0.0, min(1.0, float(v))) for v in tint)

        token.border_style = newdata.get("border_style", token.border_style)

        token.update_transformed_surface()

    # -----------------------------------------------------------
    # Z-INDEX HELPERS
    # -----------------------------------------------------------

    def _max_z(self):
        return max((t.z_index for t in self.tokens), default=0)

    def _min_z(self):
        return min((t.z_index for t in self.tokens), default=0)

    def _tokens_sorted_by_z(self, reverse=False):
        return sorted(self.tokens, key=lambda t: t.z_index, reverse=reverse)

    # -----------------------------------------------------------
    # SPAWN
    # -----------------------------------------------------------

    def spawn_token(self, asset_name, x, y):
        meta = self.asset_manager.assets.get(asset_name)
        if not meta:
            return None

        surf = meta["surface"]
        t = Token(asset_name, surf, x, y)
        t.name = asset_name
        t.hp = 5
        t.max_hp = 5
        t.z_index = self._max_z() + 1

        self.tokens.append(t)
        return t

    def create_token_from_dict(self, d):
        lookup = {n: m["surface"] for n, m in self.asset_manager.assets.items()}
        t = Token.from_dict(d, lookup)
        if not t:
            return None
        t.z_index = self._max_z() + 1
        self.tokens.append(t)
        return t

    # -----------------------------------------------------------
    # PIXEL-PERFECT PICKING
    # -----------------------------------------------------------

    def _pick_token_at_world(self, wx, wy):
        for t in self._tokens_sorted_by_z(reverse=True):
            if not t.visible:
                continue

            lx = int(wx - t.x)
            ly = int(wy - t.y)
            if lx < 0 or ly < 0 or lx >= t.w or ly >= t.h:
                continue

            try:
                col = t.surface.get_at((lx, ly))
            except Exception:
                continue

            if len(col) == 4 and col[3] > 0:
                return t
        return None

    # -----------------------------------------------------------
    # SELECTION HELPERS
    # -----------------------------------------------------------

    def _is_selected(self, t):
        return t in self.selected_tokens

    def _set_single_selection(self, t):
        self.selected_tokens = [t] if t else []

    def _toggle_selection(self, t):
        if t in self.selected_tokens:
            self.selected_tokens.remove(t)
        else:
            self.selected_tokens.append(t)

    def _select_rect(self, x1, y1, x2, y2):
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)
        sel = []
        for t in self.tokens:
            r = t.rect()
            if r.right >= left and r.left <= right and r.bottom >= top and r.top <= bottom:
                sel.append(t)
        self.selected_tokens = sel

    # -----------------------------------------------------------
    # GROUP HELPERS
    # -----------------------------------------------------------

    def _tokens_in_group(self, gid):
        return [t for t in self.tokens if t.group_id == gid]

    def _group_selected(self):
        if len(self.selected_tokens) < 2:
            return
        gid = str(uuid.uuid4())
        max_z = max(t.z_index for t in self.selected_tokens)
        for t in self.selected_tokens:
            t.group_id = gid
            t.z_index = max_z

    def _ungroup(self, token):
        if token.group_id:
            gid = token.group_id
            for t in self._tokens_in_group(gid):
                t.group_id = None
        else:
            for t in self.selected_tokens:
                t.group_id = None

    # -----------------------------------------------------------
    # Z-INDEX OPERATIONS
    # -----------------------------------------------------------

    def _bring_to_front(self, token):
        max_z = self._max_z()
        if token.group_id:
            for t in self._tokens_in_group(token.group_id):
                t.z_index = max_z + 1
        else:
            token.z_index = max_z + 1

    def _send_to_back(self, token):
        min_z = self._min_z()
        if token.group_id:
            for t in self._tokens_in_group(token.group_id):
                t.z_index = min_z - 1
        else:
            token.z_index = min_z - 1

    def _move_up_one(self, token):
        if token.group_id:
            group = self._tokens_in_group(token.group_id)
            max_g = max(t.z_index for t in group)
            above = [t for t in self.tokens if t.z_index > max_g]
            if not above:
                return
            target = min(above, key=lambda t: t.z_index)
            delta = target.z_index - max_g
            for t in group:
                t.z_index += delta
        else:
            above = [t for t in self.tokens if t.z_index > token.z_index]
            if not above:
                return
            target = min(above, key=lambda t: t.z_index)
            token.z_index, target.z_index = target.z_index, token.z_index

    def _move_down_one(self, token):
        if token.group_id:
            group = self._tokens_in_group(token.group_id)
            min_g = min(t.z_index for t in group)
            below = [t for t in self.tokens if t.z_index < min_g]
            if not below:
                return
            target = max(below, key=lambda t: t.z_index)
            delta = min_g - target.z_index
            for t in group:
                t.z_index -= delta
        else:
            below = [t for t in self.tokens if t.z_index < token.z_index]
            if not below:
                return
            target = max(below, key=lambda t: t.z_index)
            token.z_index, target.z_index = target.z_index, token.z_index

    # -----------------------------------------------------------
    # EVENT HANDLING
    # -----------------------------------------------------------

    def handle_event(
        self,
        event,
        grid_size,
        snap_enabled,
        camera_x,
        camera_y,
        camera_zoom,
        board_rect,
    ):
        def to_world(pos):
            sx, sy = pos
            local_x = sx - board_rect.x
            local_y = sy - board_rect.y
            return (local_x / camera_zoom + camera_x, local_y / camera_zoom + camera_y)

        ctrl = bool(pygame.key.get_mods() & pygame.KMOD_CTRL)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not board_rect.collidepoint(event.pos):
                return None

            wx, wy = to_world(event.pos)
            t = self._pick_token_at_world(wx, wy)

            if ctrl:
                if t:
                    self._toggle_selection(t)
                return None

            if t:
                if not self._is_selected(t):
                    self._set_single_selection(t)
            else:
                self.selection_dragging = True
                self.selection_start_world = (wx, wy)
                self.selection_end_world = (wx, wy)
                return None

            if not t.locked:
                if t.group_id:
                    drag_set = [x for x in self._tokens_in_group(t.group_id) if not x.locked]
                elif len(self.selected_tokens) > 1 and t in self.selected_tokens:
                    drag_set = [x for x in self.selected_tokens if not x.locked]
                else:
                    drag_set = [t]

                for u in drag_set:
                    u.dragging = True
                    u.offset_x = wx - u.x
                    u.offset_y = wy - u.y
                    u.preview_x = u.x
                    u.preview_y = u.y
                    u.drag_start_x = u.x
                    u.drag_start_y = u.y

            return None

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.selection_dragging:
                wx, wy = to_world(event.pos)
                self.selection_end_world = (wx, wy)
                self._select_rect(
                    self.selection_start_world[0],
                    self.selection_start_world[1],
                    self.selection_end_world[0],
                    self.selection_end_world[1],
                )
                self.selection_dragging = False

            # drop dragged tokens and queue onMove events
            for t in self.tokens:
                if t.dragging:
                    from_x = t.drag_start_x
                    from_y = t.drag_start_y

                    t.dragging = False
                    if snap_enabled:
                        if t.preview_x is not None:
                            t.x = t.preview_x
                            t.y = t.preview_y
                        else:
                            self._snap_token_to_grid(t, grid_size)
                    else:
                        if t.preview_x is not None:
                            t.x = t.preview_x
                            t.y = t.preview_y

                    t.preview_x = None
                    t.preview_y = None

                    if from_x != t.x or from_y != t.y:
                        self.pending_move_events.append(
                            {
                                "type": "onMove",
                                "token": t,
                                "from": (from_x, from_y),
                                "to": (t.x, t.y),
                            }
                        )

            return None

        if event.type == pygame.MOUSEMOTION:
            wx, wy = to_world(event.pos)

            if self.selection_dragging:
                self.selection_end_world = (wx, wy)
                return None

            for t in self.tokens:
                if t.dragging:
                    nx = wx - t.offset_x
                    ny = wy - t.offset_y

                    if snap_enabled:
                        t.preview_x = round(nx / grid_size) * grid_size
                        t.preview_y = round(ny / grid_size) * grid_size
                    else:
                        t.x = nx
                        t.y = ny
                        t.preview_x = None
                        t.preview_y = None

            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if not board_rect.collidepoint(event.pos):
                return None

            wx, wy = to_world(event.pos)
            t = self._pick_token_at_world(wx, wy)
            if t:
                if not self._is_selected(t):
                    self._set_single_selection(t)
                return {"token": t, "pos": event.pos}

        return None

    def _snap_token_to_grid(self, token, grid_size):
        if grid_size <= 0:
            return
        nx = round(token.x / grid_size) * grid_size
        ny = round(token.y / grid_size) * grid_size
        token.x, token.y = nx, ny

    # -----------------------------------------------------------
    # CONTEXT MENU ACTIONS
    # -----------------------------------------------------------

    def perform_menu_action(self, token, action):
        if action == "rotate_cw":
            if not token.locked:
                token.rotation = (token.rotation - 45) % 360
                token.update_transformed_surface()

        elif action == "rotate_ccw":
            if not token.locked:
                token.rotation = (token.rotation + 45) % 360
                token.update_transformed_surface()

        elif action == "scale_up":
            if not token.locked:
                token.scale = round(token.scale * 1.1, 3)
                token.update_transformed_surface()

        elif action == "scale_down":
            if not token.locked:
                token.scale = round(token.scale / 1.1, 3)
                token.update_transformed_surface()

        elif action == "delete":
            if token in self.tokens:
                self.tokens.remove(token)
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
            self._ungroup(token)

        elif action == "z_front":
            self._bring_to_front(token)

        elif action == "z_back":
            self._send_to_back(token)

        elif action == "z_up":
            self._move_up_one(token)

        elif action == "z_down":
            self._move_down_one(token)

        elif action == "export_token":
            self.last_action = {"action": "export_token", "token": token}

    # -----------------------------------------------------------
    # UPDATE & DRAW
    # -----------------------------------------------------------

    def update(self, dt):
        pass

    def draw(
        self,
        screen,
        camera_x,
        camera_y,
        camera_zoom,
        board_rect,
        grid_size,
        show_snap_preview,
    ):
        for t in self._tokens_sorted_by_z():
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

            rect = pygame.Rect(int(sx1), int(sy1), int(sx2 - sx1), int(sy2 - sy1))
            pygame.draw.rect(screen, (255, 255, 0), rect, 1)
            pygame.draw.rect(screen, (255, 255, 0), rect.inflate(-2, -2), 1)

    # -----------------------------------------------------------
    # JSON IO
    # -----------------------------------------------------------

    def to_json(self):
        return [t.to_dict() for t in self.tokens]

    def load_from_json(self, data):
        self.tokens = []
        self.selected_tokens = []
        self.selection_dragging = False
        self.pending_move_events = []

        lookup = {n: m["surface"] for n, m in self.asset_manager.assets.items()}

        for d in data:
            t = Token.from_dict(d, lookup)
            if t:
                self.tokens.append(t)
