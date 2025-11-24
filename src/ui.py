import pygame

class Button:
    def __init__(self, text, x, y, w, h):
        self.text = text
        self.rect = pygame.Rect(x,y,w,h)
        self.font = pygame.font.SysFont(None, 22)

    def draw(self, screen):
        pygame.draw.rect(screen, (70,70,75), self.rect, border_radius=6)
        pygame.draw.rect(screen, (100,100,105), self.rect, 2, border_radius=6)
        txt = self.font.render(self.text, True, (220,220,220))
        tx = self.rect.x + 8
        ty = self.rect.y + (self.rect.h - txt.get_height())//2
        screen.blit(txt, (tx, ty))

class ContextMenu:
    PADDING = 6
    ITEM_HEIGHT = 28
    BG = (28,28,32)
    BORDER = (90,90,95)
    TEXT = (230,230,230)

    def __init__(self, items, pos, token, token_manager, on_properties_request=None):
        """
        items: list of tuples (label, action_key)
        pos: (x,y) for menu top-left
        token: token instance the menu will operate on
        token_manager: TokenManager instance for performing actions
        on_properties_request: optional callback when 'Properties' chosen
        """
        self.items = items
        self.pos = pos
        self.token = token
        self.token_manager = token_manager
        self.on_properties_request = on_properties_request
        self.font = pygame.font.SysFont(None, 20)
        width = max(self.font.size(label)[0] for label, _ in items) + self.PADDING*2 + 24
        height = len(items) * self.ITEM_HEIGHT + self.PADDING
        x,y = pos
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
            screen.blit(txt, (ox + 6, oy + i*self.ITEM_HEIGHT + (self.ITEM_HEIGHT - txt.get_height())//2))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx,my = event.pos
            if not self.rect.collidepoint(mx,my):
                return
            rel_y = my - (self.rect.y + self.PADDING)
            idx = int(rel_y // self.ITEM_HEIGHT)
            if 0 <= idx < len(self.items):
                action = self.items[idx][1]
                if action == "properties":
                    # signal token manager to open properties by setting last_action
                    self.token_manager.perform_menu_action(self.token, "properties")
                else:
                    self.token_manager.perform_menu_action(self.token, action)

class TextInput:
    def __init__(self, rect, text="", placeholder=""):
        self.rect = pygame.Rect(rect)
        self.text = str(text)
        self.placeholder = placeholder
        self.font = pygame.font.SysFont(None, 18)
        self.active = False
        self.cursor = 0
        self.cursor_timer = 0.0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        if not self.active:
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self.cursor > 0:
                    self.text = self.text[:self.cursor-1] + self.text[self.cursor:]
                    self.cursor -= 1
            elif event.key == pygame.K_DELETE:
                self.text = self.text[:self.cursor] + self.text[self.cursor+1:]
            elif event.key == pygame.K_RETURN:
                self.active = False
            elif event.key == pygame.K_LEFT:
                self.cursor = max(0, self.cursor-1)
            elif event.key == pygame.K_RIGHT:
                self.cursor = min(len(self.text), self.cursor+1)
            else:
                if event.unicode:
                    self.text = self.text[:self.cursor] + event.unicode + self.text[self.cursor:]
                    self.cursor += 1

    def draw(self, screen):
        pygame.draw.rect(screen, (40,40,45), self.rect, border_radius=4)
        pygame.draw.rect(screen, (90,90,95), self.rect, 1, border_radius=4)
        if self.text:
            txt = self.font.render(self.text, True, (230,230,230))
        else:
            txt = self.font.render(self.placeholder, True, (120,120,120))
        screen.blit(txt, (self.rect.x + 6, self.rect.y + 6))
        # cursor
        if self.active:
            self.cursor_timer += 1/60.0
            if int(self.cursor_timer*2) % 2 == 0:
                pre = self.font.render(self.text[:self.cursor], True, (230,230,230))
                cx = self.rect.x + 6 + pre.get_width()
                cy1 = self.rect.y + 6
                cy2 = self.rect.y + self.rect.h - 6
                pygame.draw.line(screen, (230,230,230), (cx, cy1), (cx, cy2), 1)

class TextArea:
    def __init__(self, rect, text=""):
        self.rect = pygame.Rect(rect)
        self.text = str(text)
        self.font = pygame.font.SysFont(None, 16)
        self.active = False
        self.scroll = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
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
        pygame.draw.rect(screen, (30,30,34), self.rect, border_radius=4)
        pygame.draw.rect(screen, (80,80,86), self.rect, 1, border_radius=4)
        # draw text with wrapping simple
        lines = self.text.split("\n")
        oy = self.rect.y + 6
        for line in lines[-10:]:
            txt = self.font.render(line, True, (220,220,220))
            screen.blit(txt, (self.rect.x + 6, oy))
            oy += self.font.get_height() + 2

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
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self._set_by_pos(event.pos[0])

    def _set_by_pos(self, x):
        rel = (x - self.rect.x) / max(1, self.rect.w)
        rel = max(0.0, min(1.0, rel))
        self.value = self.min + rel * (self.max - self.min)

    def draw(self, screen):
        pygame.draw.rect(screen, (50,50,56), self.rect, border_radius=4)
        fill_w = int((self.value - self.min) / (self.max - self.min) * self.rect.w)
        pygame.draw.rect(screen, (180,180,180), (self.rect.x, self.rect.y, fill_w, self.rect.h), border_radius=4)
        pygame.draw.rect(screen, (100,100,106), self.rect, 1, border_radius=4)

class Checkbox:
    def __init__(self, rect, checked=False):
        self.rect = pygame.Rect(rect)
        self.checked = checked

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.checked = not self.checked

    def draw(self, screen):
        pygame.draw.rect(screen, (30,30,34), self.rect)
        pygame.draw.rect(screen, (120,120,120), self.rect, 1)
        if self.checked:
            cx = self.rect.x + 4
            cy = self.rect.y + 4
            pygame.draw.rect(screen, (200,200,200), (cx, cy, self.rect.w-8, self.rect.h-8))

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
                # check options area
                ox, oy = self.rect.x, self.rect.y + self.rect.h
                for i, opt in enumerate(self.options):
                    r = pygame.Rect(ox, oy + i * self.rect.h, self.rect.w, self.rect.h)
                    if r.collidepoint(event.pos):
                        self.selected = i
                        self.open = False
                        break
                else:
                    self.open = False

    def draw(self, screen):
        pygame.draw.rect(screen, (40,40,46), self.rect, border_radius=4)
        pygame.draw.rect(screen, (100,100,106), self.rect, 1, border_radius=4)
        txt = self.font.render(self.options[self.selected], True, (230,230,230))
        screen.blit(txt, (self.rect.x + 6, self.rect.y + (self.rect.h - txt.get_height())//2))
        if self.open:
            ox, oy = self.rect.x, self.rect.y + self.rect.h
            for i, opt in enumerate(self.options):
                r = pygame.Rect(ox, oy + i * self.rect.h, self.rect.w, self.rect.h)
                pygame.draw.rect(screen, (36,36,40), r)
                pygame.draw.rect(screen, (80,80,86), r, 1)
                t = self.font.render(opt, True, (220,220,220))
                screen.blit(t, (r.x + 6, r.y + (r.h - t.get_height())//2))

class PropertiesWindow:
    """Advanced token properties window (rect is x,y,w,h)."""
    BG = (22,22,26)
    BORDER = (100,100,105)
    TITLE_COLOR = (230,230,230)

    def __init__(self, rect, token, on_apply=None):
        self.rect = pygame.Rect(rect)
        self.token = token
        self.on_apply = on_apply
        self.font = pygame.font.SysFont(None, 20)
        self.closed = False

        # fields
        x,y,w,h = self.rect
        pad = 12
        col_x = x + pad
        input_w = w - pad*2
        # name
        self.name_input = TextInput((col_x, y+30, input_w, 28), text=self.token.name)
        # HP / Max HP
        self.hp_input = TextInput((col_x, y+70, 80, 28), text=str(self.token.hp))
        self.maxhp_input = TextInput((col_x+90, y+70, 80, 28), text=str(self.token.max_hp))
        # notes
        self.notes_area = TextArea((col_x, y+110, input_w, 120), text=self.token.notes)
        # GM-only checkbox
        self.gm_checkbox = Checkbox((col_x, y+240, 18, 18), checked=self.token.gm_only_notes)
        # tint sliders
        self.sld_r = Slider((col_x, y+270, input_w, 18), 0.0, 1.0, self.token.tint[0])
        self.sld_g = Slider((col_x, y+300, input_w, 18), 0.0, 1.0, self.token.tint[1])
        self.sld_b = Slider((col_x, y+330, input_w, 18), 0.0, 1.0, self.token.tint[2])
        # border dropdown
        self.border_dd = Dropdown((col_x, y+360, 140, 28), ["none", "solid", "dotted"], selected_index=["none","solid","dotted"].index(self.token.border_style) if self.token.border_style in ["none","solid","dotted"] else 0)
        # buttons
        self.apply_btn = Button("Apply", x + w - 180, y + h - 44, 80, 32)
        self.cancel_btn = Button("Cancel", x + w - 90, y + h - 44, 80, 32)

    def handle_event(self, event):
        # route events to fields
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
            mx,my = event.pos
            if self.apply_btn.rect.collidepoint(mx,my):
                # gather data and call on_apply
                try:
                    hp = int(self.hp_input.text) if self.hp_input.text else 0
                except Exception:
                    hp = self.token.hp
                try:
                    maxhp = int(self.maxhp_input.text) if self.maxhp_input.text else max(1, self.token.max_hp)
                except Exception:
                    maxhp = self.token.max_hp
                data = {
                    "name": self.name_input.text,
                    "hp": hp,
                    "max_hp": maxhp,
                    "notes": self.notes_area.text,
                    "gm_only_notes": self.gm_checkbox.checked,
                    "tint": (self.sld_r.value, self.sld_g.value, self.sld_b.value),
                    "border_style": self.border_dd.options[self.border_dd.selected]
                }
                if self.on_apply:
                    self.on_apply(self.token, data)
                self.closed = True
            elif self.cancel_btn.rect.collidepoint(mx,my):
                self.closed = True

    def draw(self, screen):
        # window bg
        pygame.draw.rect(screen, self.BG, self.rect, border_radius=8)
        pygame.draw.rect(screen, self.BORDER, self.rect, 2, border_radius=8)
        # title
        title = self.font.render("Token Properties", True, self.TITLE_COLOR)
        screen.blit(title, (self.rect.x + 12, self.rect.y + 8))
        # labels and fields
        x,y,w,h = self.rect
        pad = 12
        screen.blit(self.font.render("Name:", True, (200,200,200)), (x + pad, y + 30 - 18))
        self.name_input.draw(screen)
        screen.blit(self.font.render("HP:", True, (200,200,200)), (x + pad, y + 70 - 18))
        self.hp_input.draw(screen)
        screen.blit(self.font.render("Max HP:", True, (200,200,200)), (x + pad + 90, y + 70 - 18))
        self.maxhp_input.draw(screen)
        screen.blit(self.font.render("Notes:", True, (200,200,200)), (x + pad, y + 110 - 18))
        self.notes_area.draw(screen)
        screen.blit(self.font.render("GM-only notes:", True, (200,200,200)), (x + pad + 24, y + 240 - 2))
        self.gm_checkbox.draw(screen)
        screen.blit(self.font.render("Tint R:", True, (200,200,200)), (x + pad, y + 270 - 18))
        self.sld_r.draw(screen)
        screen.blit(self.font.render("Tint G:", True, (200,200,200)), (x + pad, y + 300 - 18))
        self.sld_g.draw(screen)
        screen.blit(self.font.render("Tint B:", True, (200,200,200)), (x + pad, y + 330 - 18))
        self.sld_b.draw(screen)
        screen.blit(self.font.render("Border:", True, (200,200,200)), (x + pad, y + 360 - 18))
        self.border_dd.draw(screen)

        # live preview box
        preview_box = pygame.Rect(self.rect.x + self.rect.w - 150, self.rect.y + 40, 120, 120)
        pygame.draw.rect(screen, (18,18,20), preview_box)
        pygame.draw.rect(screen, (80,80,86), preview_box, 1)
        # create a temporary preview token surface by copying token, applying current settings
        tmp_surf = self.token.original_surface.copy()
        # apply scale & rotation preview (use token current scale/rotation)
        try:
            # tint
            r = int(self.sld_r.value * 255)
            g = int(self.sld_g.value * 255)
            b = int(self.sld_b.value * 255)
            tint_surf = pygame.Surface(tmp_surf.get_size(), flags=pygame.SRCALPHA)
            tint_surf.fill((r,g,b,255))
            tmp_surf.blit(tint_surf, (0,0), special_flags=pygame.BLEND_MULT)
        except Exception:
            pass
        # draw into preview box centered
        pw, ph = tmp_surf.get_size()
        scale = min(1.0, (preview_box.w-8)/pw, (preview_box.h-8)/ph)
        new_w = max(1, int(pw * scale))
        new_h = max(1, int(ph * scale))
        try:
            p = pygame.transform.smoothscale(tmp_surf, (new_w, new_h))
        except Exception:
            p = pygame.transform.scale(tmp_surf, (new_w, new_h))
        px = preview_box.x + (preview_box.w - new_w)//2
        py = preview_box.y + (preview_box.h - new_h)//2
        screen.blit(p, (px, py))
        # draw apply/cancel
        self.apply_btn.draw(screen)
        self.cancel_btn.draw(screen)
