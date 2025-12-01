import pygame
import os

class Button:
    def __init__(self, text, x, y, w, h):
        self.text = text
        self.rect = pygame.Rect(x, y, w, h)
        self.font = pygame.font.SysFont(None, 22)

    def draw(self, screen):
        pygame.draw.rect(screen, (70, 70, 75), self.rect, border_radius=6)
        pygame.draw.rect(screen, (100, 100, 105), self.rect, 2, border_radius=6)
        txt = self.font.render(self.text, True, (220, 220, 220))
        tx = self.rect.x + 8
        ty = self.rect.y + (self.rect.h - txt.get_height()) // 2
        screen.blit(txt, (tx, ty))


class ContextMenu:
    PADDING = 6
    ITEM_HEIGHT = 28
    BG = (28, 28, 32)
    BORDER = (90, 90, 95)
    TEXT = (230, 230, 230)

    def __init__(self, items, pos, token, token_manager, on_properties_request=None):
        self.items = items
        self.pos = pos
        self.token = token
        self.token_manager = token_manager
        self.on_properties_request = on_properties_request
        self.font = pygame.font.SysFont(None, 20)
        width = max(self.font.size(label)[0] for label, _ in items) + self.PADDING * 2 + 24
        height = len(items) * self.ITEM_HEIGHT + self.PADDING
        x, y = pos
        screen_w, screen_h = pygame.display.get_surface().get_size()
        if x + width > screen_w:
            x = max(0, screen_w - width - 4)
        if y + height > screen_h:
            y = max(0, screen_h - height - 4)
        self.rect = pygame.Rect(x, y, width, height)

    def draw(self, screen):
        pygame.draw.rect(screen, self.BG, self.rect, border_radius=6)
        pygame.draw.rect(screen, self.BORDER, self.rect, 2, border_radius=6)
        ox = self.rect.x + self.PADDING
        oy = self.rect.y + self.PADDING
        for i, (label, key) in enumerate(self.items):
            txt = self.font.render(label, True, self.TEXT)
            screen.blit(
                txt,
                (ox + 6, oy + i * self.ITEM_HEIGHT + (self.ITEM_HEIGHT - txt.get_height()) // 2),
            )

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if not self.rect.collidepoint(mx, my):
                return
            rel_y = my - (self.rect.y + self.PADDING)
            idx = int(rel_y // self.ITEM_HEIGHT)
            if 0 <= idx < len(self.items):
                action = self.items[idx][1]
                self.token_manager.perform_menu_action(self.token, action)


class TextInput:
    def __init__(self, rect, text="", placeholder="", numeric_only=False):
        self.rect = pygame.Rect(rect)
        self.text = str(text)
        self.placeholder = placeholder
        self.font = pygame.font.SysFont(None, 18)
        self.active = False
        self.cursor = len(self.text)
        self.cursor_timer = 0.0
        self.numeric_only = numeric_only

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
            return

        if not self.active:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.cursor > 0:
                    self.text = self.text[: self.cursor - 1] + self.text[self.cursor :]
                    self.cursor -= 1
            elif event.key == pygame.K_DELETE:
                if self.cursor < len(self.text):
                    self.text = self.text[: self.cursor] + self.text[self.cursor + 1 :]
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif event.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor - 1)
            elif event.key == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor + 1)
            else:
                if event.unicode:
                    ch = event.unicode
                    if self.numeric_only and not ch.isdigit():
                        return
                    self.text = self.text[: self.cursor] + ch + self.text[self.cursor :]
                    self.cursor += 1

    def draw(self, screen):
        bg_color = (50, 50, 56) if self.active else (40, 40, 45)
        border_color = (140, 140, 145) if self.active else (90, 90, 95)
        pygame.draw.rect(screen, bg_color, self.rect, border_radius=4)
        pygame.draw.rect(screen, border_color, self.rect, 1, border_radius=4)

        if self.text:
            txt_surface = self.font.render(self.text, True, (230, 230, 230))
        else:
            txt_surface = self.font.render(self.placeholder, True, (120, 120, 120))

        clip_old = screen.get_clip()
        inner_rect = self.rect.inflate(-4, -4)
        screen.set_clip(inner_rect)
        screen.blit(txt_surface, (self.rect.x + 6, self.rect.y + 6))
        screen.set_clip(clip_old)

        if self.active:
            self.cursor_timer += 1 / 60.0
            if int(self.cursor_timer * 2) % 2 == 0:
                pre_text = self.text[: self.cursor]
                pre = self.font.render(pre_text, True, (230, 230, 230))
                cx = self.rect.x + 6 + pre.get_width()
                cy1 = self.rect.y + 4
                cy2 = self.rect.y + self.rect.h - 4
                pygame.draw.line(screen, (230, 230, 230), (cx, cy1), (cx, cy2), 1)


class TextArea:
    def __init__(self, rect, text=""):
        self.rect = pygame.Rect(rect)
        self.text = str(text)
        self.font = pygame.font.SysFont(None, 16)
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
            return
        if not self.active:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                self.text += "\n"
            else:
                if event.unicode:
                    self.text += event.unicode

    def draw(self, screen):
        bg_color = (30, 30, 34)
        border_color = (140, 140, 145) if self.active else (80, 80, 86)
        pygame.draw.rect(screen, bg_color, self.rect, border_radius=4)
        pygame.draw.rect(screen, border_color, self.rect, 1, border_radius=4)

        lines = self.text.split("\n")
        clip_old = screen.get_clip()
        inner_rect = self.rect.inflate(-4, -4)
        screen.set_clip(inner_rect)

        oy = self.rect.y + 6
        for line in lines[-10:]:
            txt = self.font.render(line, True, (220, 220, 220))
            screen.blit(txt, (self.rect.x + 6, oy))
            oy += self.font.get_height() + 2

        screen.set_clip(clip_old)


class Slider:
    def __init__(self, rect, minv=0.0, maxv=1.0, value=1.0):
        self.rect = pygame.Rect(rect)
        self.min = minv
        self.max = maxv
        self.value = float(value)
        self.dragging = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self._set_by_pos(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._set_by_pos(event.pos[0])

    def _set_by_pos(self, x):
        rel = (x - self.rect.x) / max(1, self.rect.w)
        rel = max(0.0, min(1.0, rel))
        self.value = self.min + rel * (self.max - self.min)

    def draw(self, screen):
        pygame.draw.rect(screen, (50, 50, 56), self.rect, border_radius=4)
        if self.max > self.min:
            fill_w = int((self.value - self.min) / (self.max - self.min) * self.rect.w)
        else:
            fill_w = 0
        pygame.draw.rect(screen, (180, 180, 180),
                         (self.rect.x, self.rect.y, fill_w, self.rect.h), border_radius=4)
        pygame.draw.rect(screen, (100, 100, 106), self.rect, 1, border_radius=4)


class Checkbox:
    def __init__(self, rect, checked=False):
        self.rect = pygame.Rect(rect)
        self.checked = checked

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.checked = not self.checked

    def draw(self, screen):
        pygame.draw.rect(screen, (30, 30, 34), self.rect)
        pygame.draw.rect(screen, (120, 120, 120), self.rect, 1)
        if self.checked:
            cx = self.rect.x + 4
            cy = self.rect.y + 4
            pygame.draw.rect(screen, (200, 200, 200),
                             (cx, cy, self.rect.w - 8, self.rect.h - 8))


class Dropdown:
    def __init__(self, rect, options, selected_index=0):
        self.rect = pygame.Rect(rect)
        self.options = options
        self.selected = selected_index
        self.open = False
        self.font = pygame.font.SysFont(None, 18)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
            elif self.open:
                ox, oy = self.rect.x, self.rect.y + self.rect.h
                for i, opt in enumerate(self.options):
                    r = pygame.Rect(ox, oy + i * self.rect.h,
                                     self.rect.w, self.rect.h)
                    if r.collidepoint(event.pos):
                        self.selected = i
                        self.open = False
                        break
                else:
                    self.open = False

    def draw(self, screen):
        pygame.draw.rect(screen, (40, 40, 46), self.rect, border_radius=4)
        pygame.draw.rect(screen, (100, 100, 106), self.rect, 1, border_radius=4)

        txt = self.font.render(self.options[self.selected], True, (230, 230, 230))
        screen.blit(txt,
                    (self.rect.x + 6,
                     self.rect.y + (self.rect.h - txt.get_height()) // 2))

    def draw_dropdown(self, screen):
        if not self.open:
            return

        ox, oy = self.rect.x, self.rect.y + self.rect.h
        for i, opt in enumerate(self.options):
            r = pygame.Rect(ox, oy + i * self.rect.h, self.rect.w, self.rect.h)
            pygame.draw.rect(screen, (36, 36, 40), r)
            pygame.draw.rect(screen, (80, 80, 86), r, 1)
            t = self.font.render(opt, True, (220, 220, 220))
            screen.blit(t,
                        (r.x + 6, r.y + (r.h - t.get_height()) // 2))


###########################################
# ASSET BROWSER PANEL
###########################################

class AssetBrowserPanel:
    """Asset browser sidebar with separate overlay rendering."""

    def __init__(self, rect, asset_manager):
        self.rect = pygame.Rect(rect)
        self.asset_manager = asset_manager
        self.font = pygame.font.SysFont(None, 18)
        self.title_font = pygame.font.SysFont(None, 20)

        x, y, w, h = self.rect
        pad = 8

        self.search_input = TextInput(
            (x + pad, y + pad + 20, w - pad * 2, 24),
            text="",
            placeholder="Search name or extension",
        )

        self.refresh_btn = Button("Refresh",
                                  x + pad,
                                  self.search_input.rect.bottom + 6,
                                  90, 24)

        sort_options = ["A–Z", "Z–A", "File size", "Date added"]
        self.sort_dd = Dropdown(
            (self.refresh_btn.rect.right + 8,
             self.refresh_btn.rect.y,
             w - pad * 3 - 90,
             24),
            sort_options,
            selected_index=0,
        )
        self.sort_mode = "az"
        self._last_sort_index = self.sort_dd.selected

        self.categories = []
        self.category_buttons = []
        self.active_category = None
        self._build_categories()

        list_top = max(
            b.rect.bottom
            for b in ([self.refresh_btn, self.sort_dd] + self.category_buttons)
        ) + 8 if self.category_buttons else self.sort_dd.rect.bottom + 8

        self.list_area = pygame.Rect(
            x + pad,
            list_top,
            w - pad * 2,
            y + h - list_top - pad,
        )

        self.item_height = 96
        self.scroll = 0
        self.max_scroll = 0
        self.scroll_dragging = False
        self.scroll_drag_offset = 0

        self.filtered_names = []
        self._last_search_text = ""
        self._rebuild_filtered_list()

        self.dragging = False
        self.drag_asset = None
        self.drag_pos = (0, 0)
        self.last_click_name = None
        self.last_click_time = 0
        self.double_click_ms = 300

    def _build_categories(self):
        self.categories = ["All"] + self.asset_manager.get_categories()
        self.category_buttons = []
        if len(self.categories) <= 1:
            return

        x, _, w, _ = self.rect
        pad = 8
        y_buttons = self.sort_dd.rect.bottom + 6
        bx = x + pad
        by = y_buttons

        for cat in self.categories:
            btn = Button(cat, bx, by, 80, 22)
            self.category_buttons.append(btn)
            bx += 84
            if bx + 80 > x + w - pad:
                bx = x + pad
                by += 26

        self.active_category = None

    def _collect_asset_names(self):
        return list(self.asset_manager.assets.keys())

    def _apply_sort_mode(self, names):
        def meta(name):
            return self.asset_manager.assets.get(name, {})

        if self.sort_mode == "az":
            names.sort(key=lambda n: n.lower())
        elif self.sort_mode == "za":
            names.sort(key=lambda n: n.lower(), reverse=True)
        elif self.sort_mode == "size":
            names.sort(key=lambda n: meta(n).get("size", 0), reverse=True)
        elif self.sort_mode == "date":
            names.sort(key=lambda n: meta(n).get("date_added", 0.0), reverse=True)

        return names

    def _rebuild_filtered_list(self):
        names = self._collect_asset_names()
        search = self.search_input.text.strip().lower()

        filtered = []
        for name in names:
            meta = self.asset_manager.assets.get(name)
            if not meta:
                continue

            if self.active_category:
                base_dir = self.asset_manager.assets_dir
                cat_path = self.active_category
                full_prefix = os.path.join(base_dir, cat_path) + os.sep
                if not meta["path"].startswith(full_prefix):
                    continue

            if search:
                base = name.lower()
                ext = name.split(".")[-1].lower() if "." in name else ""
                if search not in base and search not in ext:
                    continue

            filtered.append(name)

        filtered = self._apply_sort_mode(filtered)

        self.filtered_names = filtered
        content_h = len(self.filtered_names) * self.item_height

        self.max_scroll = max(0, content_h - self.list_area.h)
        self.scroll = max(0, min(self.scroll, self.max_scroll))

        self._last_search_text = self.search_input.text

    def _update_sort_mode_from_dropdown(self):
        idx = self.sort_dd.selected
        if idx == self._last_sort_index:
            return
        self._last_sort_index = idx

        if idx == 0:
            self.sort_mode = "az"
        elif idx == 1:
            self.sort_mode = "za"
        elif idx == 2:
            self.sort_mode = "size"
        elif idx == 3:
            self.sort_mode = "date"

        self._rebuild_filtered_list()

    def _get_scrollbar_rect(self):
        if self.max_scroll <= 0:
            return None

        view_h = self.list_area.h
        content_h = view_h + self.max_scroll
        bar_h = max(20, int(view_h * view_h / float(content_h)))

        track_y = self.list_area.y
        track_h = view_h
        ratio = self.scroll / float(max(1, self.max_scroll))
        bar_y = track_y + int((track_h - bar_h) * ratio)

        return pygame.Rect(self.list_area.right - 10, bar_y, 8, bar_h)

    def _iter_item_rows(self):
        y0 = self.list_area.y - self.scroll
        for idx, name in enumerate(self.filtered_names):
            meta = self.asset_manager.assets.get(name)
            if not meta:
                continue

            row_y = y0 + idx * self.item_height

            row_rect = pygame.Rect(
                self.list_area.x, row_y,
                self.list_area.w, self.item_height - 4
            )

            if row_rect.bottom < self.list_area.y or row_rect.y > self.list_area.bottom:
                continue

            thumb = meta.get("thumb")
            if thumb:
                tw, th = thumb.get_size()
            else:
                tw, th = 64, 64

            thumb_x = row_rect.x + 6
            thumb_y = row_rect.y + (row_rect.h - th) // 2
            thumb_rect = pygame.Rect(thumb_x, thumb_y, tw, th)

            yield name, meta, row_rect, thumb_rect

    def handle_event(self, event, board_rect):
        consumed = False
        spawn_request = None

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION):
            if self.dragging:
                consumed = True
            elif hasattr(event, "pos") and self.rect.collidepoint(event.pos):
                consumed = True

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self.search_input.handle_event(event)
            if self.search_input.text != self._last_search_text:
                self._rebuild_filtered_list()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self.refresh_btn.rect.collidepoint(mx, my):
                self.asset_manager.refresh_assets()
                self._build_categories()
                self._rebuild_filtered_list()
                return {"consumed": True, "spawn": None}

            for idx, btn in enumerate(self.category_buttons):
                if btn.rect.collidepoint(mx, my):
                    cat = self.categories[idx]
                    self.active_category = None if cat == "All" else cat
                    self._rebuild_filtered_list()
                    return {"consumed": True, "spawn": None}

        self.sort_dd.handle_event(event)
        self._update_sort_mode_from_dropdown()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
            if self.list_area.collidepoint(event.pos):
                if event.button == 4:
                    self.scroll = max(0, self.scroll - 32)
                else:
                    self.scroll = min(self.max_scroll, self.scroll + 32)
                return {"consumed": True, "spawn": None}

        bar = self._get_scrollbar_rect()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and bar:
            if bar.collidepoint(event.pos):
                self.scroll_dragging = True
                self.scroll_drag_offset = event.pos[1] - bar.y
                return {"consumed": True, "spawn": None}
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.scroll_dragging = False
        elif event.type == pygame.MOUSEMOTION and self.scroll_dragging and bar:
            _, my = event.pos
            track_y = self.list_area.y
            view_h = self.list_area.h
            content_h = view_h + self.max_scroll
            bar_h = max(20, int(view_h * view_h / float(content_h)))

            new_y = my - self.scroll_drag_offset
            new_y = max(track_y, min(track_y + view_h - bar_h, new_y))

            rel = (new_y - track_y) / float(max(1, view_h - bar_h))
            self.scroll = int(rel * self.max_scroll)

            return {"consumed": True, "spawn": None}

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            if self.list_area.collidepoint(mx, my):
                clicked_name = None

                for name, meta, row_rect, thumb_rect in self._iter_item_rows():
                    if row_rect.collidepoint(mx, my):
                        clicked_name = name
                        break

                if clicked_name:
                    now = pygame.time.get_ticks()

                    if self.last_click_name == clicked_name and \
                       (now - self.last_click_time <= self.double_click_ms):
                        spawn_request = {"asset": clicked_name, "pos": None}
                        self.last_click_name = None
                        self.last_click_time = 0
                    else:
                        self.last_click_name = clicked_name
                        self.last_click_time = now
                        self.dragging = True
                        self.drag_asset = clicked_name
                        self.drag_pos = (mx, my)

                    return {"consumed": True, "spawn": spawn_request}

        if event.type == pygame.MOUSEMOTION and self.dragging:
            self.drag_pos = event.pos
            return {"consumed": True, "spawn": None}

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            pos = event.pos
            if board_rect.collidepoint(pos):
                spawn_request = {"asset": self.drag_asset, "pos": pos}

            self.dragging = False
            self.drag_asset = None
            return {"consumed": True, "spawn": spawn_request}

        return {"consumed": consumed, "spawn": spawn_request}

    def draw(self, screen):
        pygame.draw.rect(screen, (26, 26, 30), self.rect)
        pygame.draw.rect(screen, (80, 80, 90), self.rect, 1)

        title = self.title_font.render("Assets", True, (230, 230, 230))
        screen.blit(title, (self.rect.x + 8, self.rect.y + 2))

        self.search_input.draw(screen)

        self.refresh_btn.draw(screen)
        self.sort_dd.draw(screen)

        for btn in self.category_buttons:
            btn.draw(screen)

        clip_old = screen.get_clip()
        screen.set_clip(self.list_area)

        pygame.draw.rect(screen, (20, 20, 24), self.list_area)

        for name, meta, row_rect, thumb_rect in self._iter_item_rows():
            pygame.draw.rect(screen, (36, 36, 42), row_rect, border_radius=4)
            pygame.draw.rect(screen, (60, 60, 68), row_rect, 1, border_radius=4)

            thumb = meta.get("thumb")
            if thumb:
                screen.blit(thumb, thumb_rect.topleft)

            text_x = thumb_rect.right + 8
            text_y = row_rect.y + 6

            name_txt = self.font.render(name, True, (230, 230, 230))
            screen.blit(name_txt, (text_x, text_y))

            size_kb = meta.get("size", 0) // 1024
            size_txt = self.font.render(f"{size_kb} KB", True, (180, 180, 180))
            screen.blit(size_txt, (text_x, text_y + 18))

            surf = meta.get("surface")
            if surf:
                w, h = surf.get_size()
                dim_txt = self.font.render(f"{w}x{h}px", True, (160, 160, 160))
                screen.blit(dim_txt, (text_x, text_y + 36))

        screen.set_clip(clip_old)

        bar = self._get_scrollbar_rect()
        if bar:
            track_rect = pygame.Rect(
                self.list_area.right - 10,
                self.list_area.y,
                8, self.list_area.h
            )
            pygame.draw.rect(screen, (30, 30, 36), track_rect)
            pygame.draw.rect(screen, (70, 70, 76), bar, border_radius=4)

        if self.dragging and self.drag_asset:
            meta = self.asset_manager.assets.get(self.drag_asset)
            if meta:
                thumb = meta.get("thumb")
                if thumb:
                    ghost = thumb.copy()
                    ghost.fill((255, 255, 255, 160), special_flags=pygame.BLEND_RGBA_MULT)
                    gx = self.drag_pos[0] - ghost.get_width() // 2
                    gy = self.drag_pos[1] - ghost.get_height() // 2
                    screen.blit(ghost, (gx, gy))

    def draw_overlays(self, screen):
        self.sort_dd.draw_dropdown(screen)


###########################################
# PROPERTIES WINDOW (560x460 layout)
###########################################

class PropertiesWindow:
    BG = (22, 22, 26)
    BORDER = (100, 100, 105)
    TITLE_COLOR = (230, 230, 230)
    LABEL_COLOR = (200, 200, 200)

    def __init__(self, rect, token, on_apply=None):
        self.rect = pygame.Rect(rect)
        self.token = token
        self.on_apply = on_apply
        self.font = pygame.font.SysFont(None, 20)
        self.small_font = pygame.font.SysFont(None, 18)
        self.closed = False

        x, y, w, h = self.rect
        pad = 16
        preview_w = 160
        left_w = w - pad * 3 - preview_w

        self.name_input = TextInput(
            (x + pad, y + 40, left_w, 28),
            text=self.token.name,
            placeholder="Token name",
        )

        hp_y = self.name_input.rect.bottom + 16
        self.hp_input = TextInput(
            (x + pad, hp_y, 80, 28),
            text=str(self.token.hp),
            numeric_only=True,
        )
        self.maxhp_input = TextInput(
            (x + pad + 120, hp_y, 80, 28),
            text=str(self.token.max_hp),
            numeric_only=True,
        )

        notes_y = self.hp_input.rect.bottom + 16
        self.notes_area = TextArea(
            (x + pad, notes_y, left_w, 120),
            text=self.token.notes,
        )

        gm_y = self.notes_area.rect.bottom + 10
        self.gm_checkbox = Checkbox(
            (x + pad, gm_y, 18, 18),
            checked=self.token.gm_only_notes,
        )

        tint_r_y = gm_y + 32
        self.sld_r = Slider(
            (x + pad, tint_r_y, left_w, 18),
            0.0, 1.0, self.token.tint[0],
        )
        tint_g_y = tint_r_y + 30
        self.sld_g = Slider(
            (x + pad, tint_g_y, left_w, 18),
            0.0, 1.0, self.token.tint[1],
        )
        tint_b_y = tint_g_y + 30
        self.sld_b = Slider(
            (x + pad, tint_b_y, left_w, 18),
            0.0, 1.0, self.token.tint[2],
        )

        border_y = tint_b_y + 32
        styles = ["none", "solid", "dotted"]
        try:
            idx = styles.index(self.token.border_style)
        except ValueError:
            idx = 0
        self.border_dd = Dropdown(
            (x + pad, border_y, 140, 28),
            styles,
            selected_index=idx,
        )

        btn_y = y + h - pad - 34
        self.apply_btn = Button("Apply", x + w - pad - 180, btn_y, 80, 30)
        self.cancel_btn = Button("Cancel", x + w - pad - 90, btn_y, 80, 30)

        self.preview_rect = pygame.Rect(
            x + w - pad - preview_w,
            y + 40,
            preview_w,
            preview_w,
        )

    def handle_event(self, event):
        self.name_input.handle_event(event)
        self.hp_input.handle_event(event)
        self.maxhp_input.handle_event(event)
        self.notes_area.handle_event(event)
        self.gm_checkbox.handle_event(event)
        self.sld_r.handle_event(event)
        self.sld_g.handle_event(event)
        self.sld_b.handle_event(event)
        self.border_dd.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos

            if self.apply_btn.rect.collidepoint(mx, my):
                try:
                    hp = int(self.hp_input.text) if self.hp_input.text else self.token.hp
                except ValueError:
                    hp = self.token.hp
                try:
                    maxhp = int(self.maxhp_input.text) if self.maxhp_input.text else self.token.max_hp
                except ValueError:
                    maxhp = self.token.max_hp

                maxhp = max(1, maxhp)
                hp = max(0, min(maxhp, hp))

                data = {
                    "name": self.name_input.text,
                    "hp": hp,
                    "max_hp": maxhp,
                    "notes": self.notes_area.text,
                    "gm_only_notes": self.gm_checkbox.checked,
                    "tint": (self.sld_r.value, self.sld_g.value, self.sld_b.value),
                    "border_style": self.border_dd.options[self.border_dd.selected],
                }
                if self.on_apply:
                    self.on_apply(self.token, data)
                self.closed = True

            elif self.cancel_btn.rect.collidepoint(mx, my):
                self.closed = True

    def _draw_labels(self, screen):
        x, y, w, h = self.rect
        pad = 16

        title = self.font.render("Token Properties", True, self.TITLE_COLOR)
        screen.blit(title, (x + pad, y + 8))

        screen.blit(self.small_font.render("Name:", True, self.LABEL_COLOR),
                    (self.name_input.rect.x, self.name_input.rect.y - 18))

        screen.blit(self.small_font.render("HP:", True, self.LABEL_COLOR),
                    (self.hp_input.rect.x, self.hp_input.rect.y - 18))
        screen.blit(self.small_font.render("Max HP:", True, self.LABEL_COLOR),
                    (self.maxhp_input.rect.x, self.maxhp_input.rect.y - 18))

        screen.blit(self.small_font.render("Notes:", True, self.LABEL_COLOR),
                    (self.notes_area.rect.x, self.notes_area.rect.y - 18))

        screen.blit(self.small_font.render("GM-only notes:", True, self.LABEL_COLOR),
                    (self.gm_checkbox.rect.x + 26, self.gm_checkbox.rect.y))

        screen.blit(self.small_font.render("Tint R:", True, self.LABEL_COLOR),
                    (self.sld_r.rect.x, self.sld_r.rect.y - 18))
        screen.blit(self.small_font.render("Tint G:", True, self.LABEL_COLOR),
                    (self.sld_g.rect.x, self.sld_g.rect.y - 18))
        screen.blit(self.small_font.render("Tint B:", True, self.LABEL_COLOR),
                    (self.sld_b.rect.x, self.sld_b.rect.y - 18))

        screen.blit(self.small_font.render("Border:", True, self.LABEL_COLOR),
                    (self.border_dd.rect.x, self.border_dd.rect.y - 18))

        screen.blit(self.small_font.render("Preview:", True, self.LABEL_COLOR),
                    (self.preview_rect.x, self.preview_rect.y - 18))

    def _draw_preview(self, screen):
        pygame.draw.rect(screen, (18, 18, 20), self.preview_rect)
        pygame.draw.rect(screen, (80, 80, 86), self.preview_rect, 1)

        if not hasattr(self.token, "original_surface") or self.token.original_surface is None:
            return

        tmp_surf = self.token.original_surface.copy()
        try:
            r = int(self.sld_r.value * 255)
            g = int(self.sld_g.value * 255)
            b = int(self.sld_b.value * 255)
            tint_surf = pygame.Surface(tmp_surf.get_size(), flags=pygame.SRCALPHA)
            tint_surf.fill((r, g, b, 255))
            tmp_surf.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_MULT)
        except Exception:
            pass

        pw, ph = tmp_surf.get_size()
        if pw <= 0 or ph <= 0:
            return

        scale = min(
            (self.preview_rect.w - 8) / float(pw),
            (self.preview_rect.h - 8) / float(ph),
        )
        scale = max(0.1, min(4.0, scale))

        new_w = max(1, int(pw * scale))
        new_h = max(1, int(ph * scale))

        try:
            p = pygame.transform.smoothscale(tmp_surf, (new_w, new_h))
        except Exception:
            p = pygame.transform.scale(tmp_surf, (new_w, new_h))

        px = self.preview_rect.x + (self.preview_rect.w - new_w) // 2
        py = self.preview_rect.y + (self.preview_rect.h - new_h) // 2
        screen.blit(p, (px, py))

    def draw(self, screen):
        pygame.draw.rect(screen, self.BG, self.rect, border_radius=8)
        pygame.draw.rect(screen, self.BORDER, self.rect, 2, border_radius=8)

        self._draw_labels(screen)

        self.name_input.draw(screen)
        self.hp_input.draw(screen)
        self.maxhp_input.draw(screen)
        self.notes_area.draw(screen)
        self.gm_checkbox.draw(screen)
        self.sld_r.draw(screen)
        self.sld_g.draw(screen)
        self.sld_b.draw(screen)
        self.border_dd.draw(screen)

        self._draw_preview(screen)

        self.apply_btn.draw(screen)
        self.cancel_btn.draw(screen)
