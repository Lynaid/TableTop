import pygame


class Tile:
    """
    Single tile in the dungeon tilemap.

    Fields:
        x, y      : integer tile coordinates
        type      : "empty" | "floor" | "wall" | "door" | custom
        sprite    : asset name (key in AssetManager.assets) or ""
        meta      : dict for wall masks / notes / misc
        trigger   : dict for tile trigger:
                    {
                      "type": "onEnter" | "onLeave" | "onInteract",
                      "script": "damage(2)",
                      "once": bool,
                      "fired": bool
                    }
    """

    __slots__ = ("x", "y", "type", "sprite", "meta", "trigger")

    def __init__(self, x, y, tile_type="empty", sprite="", meta=None, trigger=None):
        self.x = int(x)
        self.y = int(y)
        self.type = tile_type
        self.sprite = sprite or ""
        self.meta = dict(meta) if meta else {}
        self.trigger = dict(trigger) if trigger else None

    def to_dict(self):
        d = {
            "x": self.x,
            "y": self.y,
            "type": self.type,
            "sprite": self.sprite,
            "meta": self.meta,
        }
        if self.trigger:
            d["trigger"] = self.trigger
        return d

    @staticmethod
    def from_dict(d):
        return Tile(
            d.get("x", 0),
            d.get("y", 0),
            d.get("type", "empty"),
            d.get("sprite", ""),
            d.get("meta", {}),
            d.get("trigger", None),
        )


class TileMap:
    """
    Dungeon tilemap in world space.

    World coordinates:
        world_x = tile_x * tile_size
        world_y = tile_y * tile_size

    Storage:
        self.tiles is a dict keyed by (x, y) -> Tile (sparse)
    """

    def __init__(self, width=100, height=100, tile_size=64):
        self.width = int(width)
        self.height = int(height)
        self.tile_size = int(tile_size)
        self.tiles = {}

    # ---------------------------------------------------------
    # Basic tile operations
    # ---------------------------------------------------------

    def set_tile(self, tx, ty, tile_type, sprite="", meta=None, trigger=None):
        if tx < 0 or ty < 0 or tx >= self.width or ty >= self.height:
            return
        key = (int(tx), int(ty))
        if tile_type == "empty":
            if key in self.tiles:
                del self.tiles[key]
            return
        self.tiles[key] = Tile(tx, ty, tile_type, sprite, meta, trigger)

    def erase_tile(self, tx, ty):
        key = (int(tx), int(ty))
        if key in self.tiles:
            del self.tiles[key]

    def get_tile(self, tx, ty):
        return self.tiles.get((int(tx), int(ty)))

    # ---------------------------------------------------------
    # Tools
    # ---------------------------------------------------------

    def flood_fill(self, start_x, start_y, new_type, new_sprite=""):
        """Simple flood fill in tile coordinates, by matching original type."""
        sx, sy = int(start_x), int(start_y)
        if sx < 0 or sy < 0 or sx >= self.width or sy >= self.height:
            return

        start_tile = self.get_tile(sx, sy)
        orig_type = start_tile.type if start_tile else "empty"
        if orig_type == new_type:
            return

        stack = [(sx, sy)]
        visited = set()

        while stack:
            x, y = stack.pop()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            if x < 0 or y < 0 or x >= self.width or y >= self.height:
                continue

            t = self.get_tile(x, y)
            t_type = t.type if t else "empty"
            if t_type != orig_type:
                continue

            self.set_tile(x, y, new_type, new_sprite)

            stack.append((x + 1, y))
            stack.append((x - 1, y))
            stack.append((x, y + 1))
            stack.append((x, y - 1))

    def draw_rect_room(self, x1, y1, x2, y2, floor_sprite="", wall_sprite=""):
        """
        Draws a rectangular room:
            interior   -> type "floor"
            perimeter  -> type "wall"
        """
        tx1 = min(int(x1), int(x2))
        tx2 = max(int(x1), int(x2))
        ty1 = min(int(y1), int(y2))
        ty2 = max(int(y1), int(y2))

        for ty in range(ty1, ty2 + 1):
            for tx in range(tx1, tx2 + 1):
                if tx < 0 or ty < 0 or tx >= self.width or ty >= self.height:
                    continue
                if tx == tx1 or tx == tx2 or ty == ty1 or ty == ty2:
                    self.set_tile(tx, ty, "wall", wall_sprite)
                else:
                    self.set_tile(tx, ty, "floor", floor_sprite)

    def draw_line(self, x1, y1, x2, y2, tile_type="wall", sprite=""):
        """Bresenham line to draw simple walls."""
        x1 = int(x1)
        y1 = int(y1)
        x2 = int(x2)
        y2 = int(y2)

        dx = abs(x2 - x1)
        dy = -abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx + dy

        x, y = x1, y1
        while True:
            self.set_tile(x, y, tile_type, sprite)
            if x == x2 and y == y2:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    # ---------------------------------------------------------
    # Auto-wall (simplified neighbour-based)
    # ---------------------------------------------------------

    def _neighbors_mask_4(self, tx, ty):
        """
        Simple 4-direction bitmask:
            1 = north
            2 = east
            4 = south
            8 = west
        """
        mask = 0
        if self._is_wall(tx, ty - 1):
            mask |= 1
        if self._is_wall(tx + 1, ty):
            mask |= 2
        if self._is_wall(tx, ty + 1):
            mask |= 4
        if self._is_wall(tx - 1, ty):
            mask |= 8
        return mask

    def _is_wall(self, tx, ty):
        t = self.get_tile(tx, ty)
        return t is not None and t.type == "wall"

    def update_wall_autotiles_region(self, x1, y1, x2, y2):
        """
        Update meta["wall_mask"] for walls in a region (for later sprite selection).
        This does not change sprites; it just stores bitmask data in tile.meta.
        """
        tx1 = min(int(x1), int(x2)) - 1
        tx2 = max(int(x1), int(x2)) + 1
        ty1 = min(int(y1), int(y2)) - 1
        ty2 = max(int(y1), int(y2)) + 1

        for ty in range(ty1, ty2 + 1):
            for tx in range(tx1, tx2 + 1):
                t = self.get_tile(tx, ty)
                if not t or t.type != "wall":
                    continue
                mask = self._neighbors_mask_4(tx, ty)
                if t.meta is None:
                    t.meta = {}
                t.meta["wall_mask"] = mask

    # ---------------------------------------------------------
    # Save / Load
    # ---------------------------------------------------------

    def to_json(self):
        return {
            "width": self.width,
            "height": self.height,
            "tile_size": self.tile_size,
            "tiles": [t.to_dict() for t in self.tiles.values()],
        }

    def load_from_json(self, data):
        """
        Load tilemap from dict or None.
        If data is None or invalid, the map is cleared but width/height/tile_size stay.
        """
        if not isinstance(data, dict):
            self.tiles = {}
            return

        self.width = int(data.get("width", self.width))
        self.height = int(data.get("height", self.height))
        self.tile_size = int(data.get("tile_size", self.tile_size))

        self.tiles = {}
        tiles_list = data.get("tiles", [])
        if not isinstance(tiles_list, list):
            return

        for td in tiles_list:
            if not isinstance(td, dict):
                continue
            t = Tile.from_dict(td)
            key = (t.x, t.y)
            self.tiles[key] = t

    # ---------------------------------------------------------
    # Rendering
    # ---------------------------------------------------------

    def render(self, screen, asset_manager, camera_x, camera_y, camera_zoom, board_rect):
        """
        Draws tiles:
            - Above background
            - Below grid and tokens
        Only tiles inside the current camera view are drawn.
        """
        if self.tile_size <= 0 or camera_zoom <= 0:
            return

        view_world_left = camera_x
        view_world_top = camera_y
        view_world_right = camera_x + board_rect.w / camera_zoom
        view_world_bottom = camera_y + board_rect.h / camera_zoom

        for (tx, ty), tile in self.tiles.items():
            wx = tx * self.tile_size
            wy = ty * self.tile_size

            if wx + self.tile_size < view_world_left:
                continue
            if wx > view_world_right:
                continue
            if wy + self.tile_size < view_world_top:
                continue
            if wy > view_world_bottom:
                continue

            sx = (wx - camera_x) * camera_zoom + board_rect.x
            sy = (wy - camera_y) * camera_zoom + board_rect.y
            size_screen = int(self.tile_size * camera_zoom)

            sprite_surf = None
            if tile.sprite:
                meta = asset_manager.assets.get(tile.sprite)
                if meta:
                    sprite_surf = meta.get("surface")

            if sprite_surf is not None:
                try:
                    img = pygame.transform.smoothscale(
                        sprite_surf,
                        (size_screen, size_screen),
                    )
                except Exception:
                    img = pygame.transform.scale(
                        sprite_surf,
                        (max(1, size_screen), max(1, size_screen)),
                    )
                screen.blit(img, (int(sx), int(sy)))
            else:
                # Fallback colored tiles by type
                if tile.type == "floor":
                    col = (80, 80, 80)
                elif tile.type == "wall":
                    col = (100, 60, 60)
                elif tile.type == "door":
                    col = (120, 90, 40)
                else:
                    col = (50, 50, 50)

                pygame.draw.rect(
                    screen,
                    col,
                    pygame.Rect(int(sx), int(sy), size_screen, size_screen),
                )
