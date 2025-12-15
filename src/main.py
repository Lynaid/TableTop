import pygame
import sys
from assets import AssetManager
from token import TokenManager
from ui import Button, ContextMenu, PropertiesWindow, AssetBrowserPanel, TextInput
from utils import (
    roll_dice,
    save_campaign,
    load_campaign,
    export_token,
    import_token,
)
from tilemap import TileMap
from rules import RulesEngine
import os
import tkinter as tk
from tkinter import filedialog, simpledialog
import socket
import threading
import json
import queue
import uuid

WIDTH, HEIGHT = 1280, 720
FPS = 60

GRID_SIZE = 64
SHOW_GRID_DEFAULT = True
SNAP_DEFAULT = True

CAMERA_ZOOM_MIN = 0.2
CAMERA_ZOOM_MAX = 4.0


class NetworkClient:
    """
    Simple TCP JSON-line client.

    - connect(host, port, name)
    - send(msg_dict)
    - poll() -> list of received messages
    """

    def __init__(self):
        self.sock = None
        self.recv_thread = None
        self.msg_queue = queue.Queue()
        self.connected = False
        self.client_id = str(uuid.uuid4())[:8]
        self.name = "Player"
        self.lock = threading.Lock()

    def connect(self, host: str, port: int, name: str = None):
        if self.connected:
            return
        self.name = name or self.name
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((host, port))
        s.settimeout(None)
        self.sock = s
        self.connected = True
        self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.recv_thread.start()
        join_msg = {
            "type": "join",
            "client_id": self.client_id,
            "name": self.name,
            "protocol_version": 1,
        }
        self.send(join_msg)

    def _recv_loop(self):
        buffer = b""
        while self.connected and self.sock:
            try:
                data = self.sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            buffer += data
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                self.msg_queue.put(msg)
        self.connected = False
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    def send(self, msg: dict):
        if not self.connected or not self.sock:
            return
        try:
            data = (json.dumps(msg) + "\n").encode("utf-8")
            with self.lock:
                self.sock.sendall(data)
        except OSError:
            self.connected = False
            try:
                if self.sock:
                    self.sock.close()
            except OSError:
                pass
            self.sock = None

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.msg_queue.get_nowait())
            except queue.Empty:
                break
        return out


def draw_grid(surface, grid_size, camera_x, camera_y, camera_zoom, color=(70, 70, 75)):
    w, h = surface.get_size()
    if camera_zoom <= 0:
        return

    left_world = camera_x
    right_world = camera_x + w / camera_zoom
    top_world = camera_y
    bottom_world = camera_y + h / camera_zoom

    start_x = int(left_world // grid_size) * grid_size
    end_x = int(right_world // grid_size + 1) * grid_size
    start_y = int(top_world // grid_size) * grid_size
    end_y = int(bottom_world // grid_size + 1) * grid_size

    for x in range(start_x, end_x, grid_size):
        sx = int((x - camera_x) * camera_zoom)
        pygame.draw.line(surface, color, (sx, 0), (sx, h))

    for y in range(start_y, end_y, grid_size):
        sy = int((y - camera_y) * camera_zoom)
        pygame.draw.line(surface, color, (0, sy), (w, sy))


def screen_to_world(sx, sy, camera_x, camera_y, camera_zoom, board_rect):
    local_x = sx - board_rect.x
    local_y = sy - board_rect.y
    wx = local_x / camera_zoom + camera_x
    wy = local_y / camera_zoom + camera_y
    return wx, wy


def world_to_screen(wx, wy, camera_x, camera_y, camera_zoom, board_rect):
    sx = (wx - camera_x) * camera_zoom + board_rect.x
    sy = (wy - camera_y) * camera_zoom + board_rect.y
    return int(sx), int(sy)


def load_background_dialog():
    root = tk.Tk()
    root.withdraw()
    fp = filedialog.askopenfilename(
        title="Select background image",
        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp")],
    )
    root.destroy()
    if not fp:
        return None
    return fp


def choose_campaign_save_path(data_dir):
    campaigns_dir = os.path.join(data_dir, "campaigns")
    os.makedirs(campaigns_dir, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    path = filedialog.asksaveasfilename(
        title="Save Campaign",
        initialdir=campaigns_dir,
        defaultextension=".json",
        filetypes=[("Campaign JSON", "*.json")],
        initialfile="campaign.json",
    )
    root.destroy()
    return path or None


def choose_campaign_load_path(data_dir):
    campaigns_dir = os.path.join(data_dir, "campaigns")
    os.makedirs(campaigns_dir, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Load Campaign",
        initialdir=campaigns_dir,
        filetypes=[("Campaign JSON", "*.json")],
    )
    root.destroy()
    return path or None


def choose_token_export_path(data_dir, token_id):
    tokens_dir = os.path.join(data_dir, "tokens")
    os.makedirs(tokens_dir, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    default_name = f"token_{token_id}.json"
    path = filedialog.asksaveasfilename(
        title="Export Token",
        initialdir=tokens_dir,
        defaultextension=".json",
        filetypes=[("Token JSON", "*.json")],
        initialfile=default_name,
    )
    root.destroy()
    return path or None


def choose_token_import_path(data_dir):
    tokens_dir = os.path.join(data_dir, "tokens")
    os.makedirs(tokens_dir, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Import Token",
        initialdir=tokens_dir,
        filetypes=[("Token JSON", "*.json")],
    )
    root.destroy()
    return path or None


def fit_camera_to_background(bg_surf, camera):
    camera_x, camera_y, camera_zoom = camera
    bw, bh = bg_surf.get_size()
    if bw <= 0 or bh <= 0:
        return camera_x, camera_y, camera_zoom

    board_w = WIDTH
    board_h = HEIGHT - 58

    zoom_fit = min(board_w / float(bw), board_h / float(bh))
    zoom_fit = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, zoom_fit))

    cx_world = bw / 2.0
    cy_world = bh / 2.0

    camera_zoom = zoom_fit
    camera_x = cx_world - (board_w / (2.0 * camera_zoom))
    camera_y = cy_world - (board_h / (2.0 * camera_zoom))

    return camera_x, camera_y, camera_zoom


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("UMI.DA Tabletop - Dungeon Builder + Rules + LAN")
    clock = pygame.time.Clock()
    fullscreen = False

    base_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(base_dir, "..", "assets")
    data_dir = os.path.join(base_dir, "..", "data")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    asset_mgr = AssetManager(assets_dir)
    token_mgr = TokenManager(asset_mgr)

    # camera
    camera_x = 0.0
    camera_y = 0.0
    camera_zoom = 1.0

    # background
    background_surface = None
    background_path = None

    # dungeon / tilemap
    tilemap = TileMap(width=100, height=100, tile_size=GRID_SIZE)
    dungeon_edit_mode = False
    tile_tool = "pencil"
    tile_type = "floor"
    tile_room_drag = False
    tile_room_start = (0, 0)
    tile_line_drag = False
    tile_line_start = (0, 0)

    # Rules engine
    say_messages = []

    def ui_say(msg):
        say_messages.append((pygame.time.get_ticks(), str(msg)))

    rules_engine = RulesEngine(say_callback=ui_say)

    # Network client
    net_client = NetworkClient()

    # chat
    chat_messages = []
    chat_input = TextInput(
        (10, HEIGHT - 28, 400, 22),
        text="",
        placeholder="Chat (Enter to send)",
    )

    # top bar UI
    btn_import = Button("Import Asset", 10, 10, 140, 32)
    btn_spawn = Button("Spawn Token", 160, 10, 140, 32)
    btn_roll = Button("Roll d20", 310, 10, 100, 32)
    btn_save = Button("Save", 420, 10, 80, 32)
    btn_load = Button("Load", 510, 10, 80, 32)
    btn_toggle_grid = Button(
        "Grid: ON" if SHOW_GRID_DEFAULT else "Grid: OFF", 600, 10, 100, 32
    )
    btn_toggle_snap = Button(
        "Snap: ON" if SNAP_DEFAULT else "Snap: OFF", 710, 10, 100, 32
    )
    btn_assets_panel = Button("Assets <<", 820, 10, 110, 32)
    btn_load_bg = Button("Load Background", 940, 10, 140, 32)
    btn_import_token = Button("Import Token", 1090, 10, 110, 32)
    btn_connect = Button("Connect", 1210, 10, 60, 32)

    show_grid = SHOW_GRID_DEFAULT
    snap_enabled = SNAP_DEFAULT
    asset_panel_open = True

    asset_panel_rect = pygame.Rect(0, 58, 280, HEIGHT - 58)
    asset_panel = AssetBrowserPanel(asset_panel_rect, asset_mgr)

    dice_result = None
    font = pygame.font.SysFont(None, 24)
    say_font = pygame.font.SysFont(None, 20)
    chat_font = pygame.font.SysFont(None, 18)

    context_menu = None
    properties_window = None

    panning_mmb = False
    panning_space = False
    pan_last_pos = (0, 0)
    space_held = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        board_rect = pygame.Rect(0, 58, WIDTH, HEIGHT - 58)
        if asset_panel_open:
            asset_drop_rect = pygame.Rect(280, 58, WIDTH - 280, HEIGHT - 58)
        else:
            asset_drop_rect = pygame.Rect(0, 58, WIDTH, HEIGHT - 58)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # chat send on Enter
            if (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_RETURN
                and chat_input.active
            ):
                text = chat_input.text.strip()
                if text:
                    sender = net_client.name if net_client.connected else "Local"
                    chat_messages.append((sender, text))
                    if net_client.connected:
                        net_client.send(
                            {"type": "chat", "from": sender, "message": text}
                        )
                chat_input.text = ""

            # keyboard controls
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    if dungeon_edit_mode:
                        tile_tool = "room"
                    else:
                        camera_x = 0.0
                        camera_y = 0.0
                        camera_zoom = 1.0
                elif event.key == pygame.K_SPACE:
                    space_held = True
                elif event.key == pygame.K_b:
                    dungeon_edit_mode = not dungeon_edit_mode
                elif event.key == pygame.K_p:
                    tile_tool = "pencil"
                    tile_type = "floor"
                elif event.key == pygame.K_e:
                    tile_tool = "erase"
                    tile_type = "empty"
                elif event.key == pygame.K_f:
                    tile_tool = "fill"
                elif event.key == pygame.K_l:
                    tile_tool = "line"
                elif event.key == pygame.K_d:
                    tile_tool = "door"
                    tile_type = "door"
                elif event.key == pygame.K_w:
                    tile_tool = "pencil"
                    tile_type = "wall"
                elif event.key == pygame.K_g:
                    tile_tool = "pencil"
                    tile_type = "floor"
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    flags = pygame.FULLSCREEN if fullscreen else 0
                    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    space_held = False
                    panning_space = False

            # chat input events
            chat_input.handle_event(event)

            event_consumed_by_panel = False

            # asset panel
            if asset_panel_open and not properties_window:
                panel_result = asset_panel.handle_event(event, asset_drop_rect)
                if panel_result:
                    event_consumed_by_panel = panel_result.get("consumed", False)
                    spawn_req = panel_result.get("spawn")
                    if spawn_req:
                        asset_name = spawn_req.get("asset")
                        pos = spawn_req.get("pos")
                        if asset_name and asset_name in asset_mgr.assets:
                            if pos is None:
                                cx = asset_drop_rect.x + asset_drop_rect.w // 2
                                cy = asset_drop_rect.y + asset_drop_rect.h // 2
                            else:
                                cx, cy = pos
                            wx, wy = screen_to_world(
                                cx, cy, camera_x, camera_y, camera_zoom, board_rect
                            )
                            t = token_mgr.spawn_token(asset_name, wx, wy)
                            if t:
                                t.x = wx - t.w / 2.0
                                t.y = wy - t.h / 2.0
                                rules_engine.run_event(
                                    "onSpawn", t, None, {"pos": (t.x, t.y)}
                                )
                                if net_client.connected:
                                    net_client.send(
                                        {
                                            "type": "token_update",
                                            "token": t.to_dict(),
                                        }
                                    )

            # camera zoom
            if (
                not event_consumed_by_panel
                and event.type == pygame.MOUSEBUTTONDOWN
                and event.button in (4, 5)
            ):
                mx, my = event.pos
                if board_rect.collidepoint(mx, my):
                    if event.button == 4:
                        zoom_factor = 1.1
                    else:
                        zoom_factor = 1.0 / 1.1

                    new_zoom = camera_zoom * zoom_factor
                    new_zoom = max(CAMERA_ZOOM_MIN, min(CAMERA_ZOOM_MAX, new_zoom))

                    if new_zoom != camera_zoom:
                        local_x = mx - board_rect.x
                        local_y = my - board_rect.y
                        world_x = local_x / camera_zoom + camera_x
                        world_y = local_y / camera_zoom + camera_y

                        camera_zoom = new_zoom
                        camera_x = world_x - local_x / camera_zoom
                        camera_y = world_y - local_y / camera_zoom

                    event_consumed_by_panel = True

            # camera panning (MMB or Space+LMB)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                mx, my = event.pos
                if board_rect.collidepoint(mx, my):
                    panning_mmb = True
                    pan_last_pos = (mx, my)
                    event_consumed_by_panel = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                panning_mmb = False

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and space_held:
                mx, my = event.pos
                if board_rect.collidepoint(mx, my):
                    panning_space = True
                    pan_last_pos = (mx, my)
                    event_consumed_by_panel = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and panning_space:
                panning_space = False

            if event.type == pygame.MOUSEMOTION and (panning_mmb or panning_space):
                mx, my = event.pos
                dx = mx - pan_last_pos[0]
                dy = my - pan_last_pos[1]
                pan_last_pos = (mx, my)
                camera_x += dx / camera_zoom
                camera_y += dy / camera_zoom
                event_consumed_by_panel = True

            # Dungeon Builder tile editing
            tile_event_consumed = False
            if (
                dungeon_edit_mode
                and not properties_window
                and not event_consumed_by_panel
            ):
                if event.type in (
                    pygame.MOUSEBUTTONDOWN,
                    pygame.MOUSEBUTTONUP,
                    pygame.MOUSEMOTION,
                ):
                    mx, my = getattr(event, "pos", (0, 0))
                    if board_rect.collidepoint(mx, my):
                        wx, wy = screen_to_world(
                            mx, my, camera_x, camera_y, camera_zoom, board_rect
                        )
                        tx = int(wx // tilemap.tile_size)
                        ty = int(wy // tilemap.tile_size)

                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            if tile_tool == "pencil":
                                tilemap.set_tile(tx, ty, tile_type)
                                tilemap.update_wall_autotiles_region(tx, ty, tx, ty)
                            elif tile_tool == "erase":
                                tilemap.erase_tile(tx, ty)
                                tilemap.update_wall_autotiles_region(tx, ty, tx, ty)
                            elif tile_tool == "fill":
                                tilemap.flood_fill(tx, ty, tile_type)
                            elif tile_tool == "room":
                                tile_room_drag = True
                                tile_room_start = (tx, ty)
                            elif tile_tool == "line":
                                tile_line_drag = True
                                tile_line_start = (tx, ty)
                            elif tile_tool == "door":
                                t = tilemap.get_tile(tx, ty)
                                if t and t.type == "wall":
                                    meta = dict(t.meta) if t.meta else {}
                                    trigger = dict(t.trigger) if t.trigger else None
                                    self_trigger = trigger or {}
                                    self_trigger.setdefault("type", "onInteract")
                                    self_trigger.setdefault("script", "")
                                    self_trigger.setdefault("once", False)
                                    self_trigger.setdefault("fired", False)
                                    tilemap.set_tile(
                                        tx,
                                        ty,
                                        "door",
                                        t.sprite,
                                        meta,
                                        self_trigger,
                                    )
                            tile_event_consumed = True

                        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                            tilemap.erase_tile(tx, ty)
                            tilemap.update_wall_autotiles_region(tx, ty, tx, ty)
                            tile_event_consumed = True

                        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
                            if tile_tool == "pencil":
                                tilemap.set_tile(tx, ty, tile_type)
                                tilemap.update_wall_autotiles_region(tx, ty, tx, ty)
                                tile_event_consumed = True
                            elif tile_tool == "erase":
                                tilemap.erase_tile(tx, ty)
                                tilemap.update_wall_autotiles_region(tx, ty, tx, ty)
                                tile_event_consumed = True

                        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                            if tile_tool == "room" and tile_room_drag:
                                sx, sy = tile_room_start
                                tilemap.draw_rect_room(
                                    sx, sy, tx, ty, floor_sprite="", wall_sprite=""
                                )
                                tilemap.update_wall_autotiles_region(sx, sy, tx, ty)
                                tile_room_drag = False
                                tile_event_consumed = True
                            elif tile_tool == "line" and tile_line_drag:
                                sx, sy = tile_line_start
                                tilemap.draw_line(sx, sy, tx, ty, tile_type, "")
                                tilemap.update_wall_autotiles_region(sx, sy, tx, ty)
                                tile_line_drag = False
                                tile_event_consumed = True

            # context menu (tokens)
            if (
                context_menu
                and not event_consumed_by_panel
                and not tile_event_consumed
            ):
                context_menu.handle_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not context_menu.rect.collidepoint(event.pos):
                        context_menu = None

            # properties window
            if properties_window and not event_consumed_by_panel:
                properties_window.handle_event(event)
                if properties_window.closed:
                    properties_window = None

            # token events
            if (
                not dungeon_edit_mode
                and not event_consumed_by_panel
                and not properties_window
                and not panning_space
                and not panning_mmb
            ):
                cm_action = token_mgr.handle_event(
                    event,
                    grid_size=GRID_SIZE,
                    snap_enabled=snap_enabled,
                    camera_x=camera_x,
                    camera_y=camera_y,
                    camera_zoom=camera_zoom,
                    board_rect=board_rect,
                )

                # process onMove events for rules + network + tile triggers
                if token_mgr.pending_move_events:
                    for mevt in token_mgr.pending_move_events:
                        t = mevt["token"]
                        from_x, from_y = mevt["from"]
                        to_x, to_y = mevt["to"]

                        rules_engine.run_event(
                            "onMove",
                            t,
                            None,
                            {"from": (from_x, from_y), "to": (to_x, to_y)},
                        )

                        if net_client.connected:
                            net_client.send(
                                {
                                    "type": "token_update",
                                    "token": t.to_dict(),
                                }
                            )

                        if tilemap is not None and tilemap.tile_size > 0:
                            ts = tilemap.tile_size
                            from_tx = int(from_x // ts)
                            from_ty = int(from_y // ts)
                            to_tx = int(to_x // ts)
                            to_ty = int(to_y // ts)

                            if from_tx != to_tx or from_ty != to_ty:
                                from_tile = tilemap.get_tile(from_tx, from_ty)
                                to_tile = tilemap.get_tile(to_tx, to_ty)

                                if from_tile is not None:
                                    rules_engine.run_event(
                                        "onLeaveTile",
                                        t,
                                        from_tile,
                                        {
                                            "from": (from_tx, from_ty),
                                            "to": (to_tx, to_ty),
                                        },
                                    )
                                if to_tile is not None:
                                    rules_engine.run_event(
                                        "onEnterTile",
                                        t,
                                        to_tile,
                                        {
                                            "from": (from_tx, from_ty),
                                            "to": (to_tx, to_ty),
                                        },
                                    )

                    token_mgr.pending_move_events.clear()

                if cm_action:
                    token = cm_action["token"]
                    menu_items = [
                        ("Properties", "properties"),
                        ("Rotate CW 45°", "rotate_cw"),
                        ("Rotate CCW 45°", "rotate_ccw"),
                        ("Scale +10%", "scale_up"),
                        ("Scale -10%", "scale_down"),
                        ("Bring to Front", "z_front"),
                        ("Send to Back", "z_back"),
                        ("Layer Up", "z_up"),
                        ("Layer Down", "z_down"),
                        ("Group Selected", "group_selected"),
                        ("Ungroup", "ungroup"),
                        ("Lock", "lock"),
                        ("Unlock", "unlock"),
                        ("Export Token...", "export_token"),
                        ("Delete", "delete"),
                    ]
                    context_menu = ContextMenu(
                        menu_items,
                        cm_action["pos"],
                        token,
                        token_mgr,
                    )
                    rules_engine.run_event(
                        "onRightClick", token, None, {"pos": cm_action["pos"]}
                    )

            # handle TokenManager actions (properties / export)
            if not event_consumed_by_panel and token_mgr.last_action:
                action_payload = token_mgr.last_action
                token_mgr.last_action = None
                act = action_payload.get("action")
                if act == "properties":
                    t = action_payload.get("token")
                    properties_window = PropertiesWindow(
                        (200, 80, 560, 460),
                        t,
                        on_apply=lambda tok, newdata: (
                            token_mgr.apply_token_properties(tok, newdata),
                            net_client.connected
                            and net_client.send(
                                {
                                    "type": "token_update",
                                    "token": tok.to_dict(),
                                }
                            ),
                        ),
                    )
                    context_menu = None
                elif act == "export_token":
                    t = action_payload.get("token")
                    if t is not None:
                        path = choose_token_export_path(data_dir, t.id)
                        if path:
                            export_token(path, t)

            # top bar buttons
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and not properties_window
                and not event_consumed_by_panel
            ):
                mx, my = event.pos
                if btn_import.rect.collidepoint(mx, my):
                    asset_mgr.import_asset_dialog()
                    asset_mgr.refresh_assets()
                    if asset_panel_open:
                        asset_panel._build_categories()
                        asset_panel._rebuild_filtered_list()
                elif btn_spawn.rect.collidepoint(mx, my):
                    if asset_mgr.assets:
                        cx = asset_drop_rect.x + asset_drop_rect.w // 2
                        cy = asset_drop_rect.y + asset_drop_rect.h // 2
                        wx, wy = screen_to_world(
                            cx, cy, camera_x, camera_y, camera_zoom, board_rect
                        )
                        first = list(asset_mgr.assets.keys())[0]
                        t = token_mgr.spawn_token(first, wx, wy)
                        if t:
                            rules_engine.run_event(
                                "onSpawn", t, None, {"pos": (t.x, t.y)}
                            )
                            if net_client.connected:
                                net_client.send(
                                    {
                                        "type": "token_update",
                                        "token": t.to_dict(),
                                    }
                                )
                elif btn_roll.rect.collidepoint(mx, my):
                    dice_result = roll_dice(20)
                elif btn_save.rect.collidepoint(mx, my):
                    path = choose_campaign_save_path(data_dir)
                    if path:
                        bg_state = None
                        if background_surface and background_path:
                            bg_state = {
                                "path": background_path,
                                "camera": {
                                    "x": camera_x,
                                    "y": camera_y,
                                    "zoom": camera_zoom,
                                },
                            }
                        save_campaign(
                            path,
                            asset_mgr,
                            token_mgr,
                            bg_state,
                            tilemap,
                            rules_engine=rules_engine,
                        )
                elif btn_load.rect.collidepoint(mx, my):
                    path = choose_campaign_load_path(data_dir)
                    if path:
                        bg_state = load_campaign(
                            path,
                            asset_mgr,
                            token_mgr,
                            tilemap,
                            rules_engine,
                        )
                        asset_mgr.refresh_assets()
                        if asset_panel_open:
                            asset_panel._build_categories()
                            asset_panel._rebuild_filtered_list()
                        background_surface = None
                        background_path = None
                        if bg_state:
                            p = bg_state.get("path")
                            cam = bg_state.get("camera", {})
                            if p and os.path.exists(p):
                                surf = asset_mgr._load_surface(p)
                                if surf:
                                    background_surface = surf
                                    background_path = p
                            camera_x = float(cam.get("x", 0.0))
                            camera_y = float(cam.get("y", 0.0))
                            camera_zoom = float(cam.get("zoom", 1.0))
                elif btn_toggle_grid.rect.collidepoint(mx, my):
                    show_grid = not show_grid
                    btn_toggle_grid.text = "Grid: ON" if show_grid else "Grid: OFF"
                elif btn_toggle_snap.rect.collidepoint(mx, my):
                    snap_enabled = not snap_enabled
                    btn_toggle_snap.text = "Snap: ON" if snap_enabled else "Snap: OFF"
                elif btn_assets_panel.rect.collidepoint(mx, my):
                    asset_panel_open = not asset_panel_open
                    btn_assets_panel.text = (
                        "Assets <<" if asset_panel_open else "Assets >>"
                    )
                elif btn_load_bg.rect.collidepoint(mx, my):
                    fp = load_background_dialog()
                    if fp:
                        surf = asset_mgr._load_surface(fp)
                        if surf:
                            background_surface = surf
                            background_path = fp
                            camera_x, camera_y, camera_zoom = fit_camera_to_background(
                                background_surface,
                                (camera_x, camera_y, camera_zoom),
                            )
                elif btn_import_token.rect.collidepoint(mx, my):
                    tp = choose_token_import_path(data_dir)
                    if tp:
                        t = import_token(tp, asset_mgr, token_mgr)
                        if t and net_client.connected:
                            net_client.send(
                                {
                                    "type": "token_update",
                                    "token": t.to_dict(),
                                }
                            )
                elif btn_connect.rect.collidepoint(mx, my):
                    root = tk.Tk()
                    root.withdraw()
                    ip = simpledialog.askstring(
                        "Connect", "Server IP:", initialvalue="127.0.0.1"
                    )
                    port_str = simpledialog.askstring(
                        "Connect", "Port:", initialvalue="8765"
                    )
                    name = simpledialog.askstring(
                        "Connect", "Name:", initialvalue=net_client.name
                    )
                    root.destroy()
                    if ip and port_str:
                        try:
                            port = int(port_str)
                            net_client.connect(ip, port, name or net_client.name)
                        except Exception as e:
                            print(f"[ERROR] Connect failed: {e}")

        # network: handle incoming messages
        if net_client.connected:
            for msg in net_client.poll():
                mtype = msg.get("type")
                if mtype == "state":
                    tokens_data = msg.get("tokens", [])
                    tilemap_data = msg.get("tilemap")
                    bg_data = msg.get("background")
                    token_mgr.load_from_json(tokens_data)
                    if tilemap_data is not None:
                        tilemap.load_from_json(tilemap_data)
                    if bg_data:
                        p = bg_data.get("path")
                        cam = bg_data.get("camera", {}) or {}
                        if p and os.path.exists(p):
                            surf = asset_mgr._load_surface(p)
                            if surf:
                                background_surface = surf
                                background_path = p
                        camera_x = float(cam.get("x", camera_x))
                        camera_y = float(cam.get("y", camera_y))
                        camera_zoom = float(cam.get("zoom", camera_zoom))
                elif mtype == "token_update":
                    td = msg.get("token")
                    if isinstance(td, dict):
                        tid = td.get("id")
                        if tid:
                            existing = None
                            for t in token_mgr.tokens:
                                if t.id == tid:
                                    existing = t
                                    break
                            if existing is None:
                                token_mgr.create_token_from_dict(td)
                            else:
                                existing.x = td.get("x", existing.x)
                                existing.y = td.get("y", existing.y)
                                existing.rotation = td.get("rotation", existing.rotation)
                                existing.scale = td.get("scale", existing.scale)
                                existing.visible = td.get("visible", existing.visible)
                                existing.name = td.get("name", existing.name)
                                existing.hp = td.get("hp", existing.hp)
                                existing.max_hp = td.get("max_hp", existing.max_hp)
                                existing.notes = td.get("notes", existing.notes)
                                existing.gm_only_notes = td.get(
                                    "gm_only_notes", existing.gm_only_notes
                                )
                                tint = td.get("tint", list(existing.tint))
                                if isinstance(tint, (list, tuple)) and len(tint) == 3:
                                    existing.tint = tuple(
                                        max(0.0, min(1.0, float(v))) for v in tint
                                    )
                                existing.border_style = td.get(
                                    "border_style", existing.border_style
                                )
                                existing.locked = td.get("locked", existing.locked)
                                existing.group_id = td.get(
                                    "group_id", existing.group_id
                                )
                                existing.z_index = td.get("z_index", existing.z_index)
                                existing.scripts = dict(
                                    td.get("scripts", existing.scripts)
                                )
                                existing.update_transformed_surface()
                elif mtype == "chat":
                    sender = msg.get("from", "??")
                    text = msg.get("message", "")
                    if isinstance(text, str):
                        chat_messages.append((str(sender), text))

        token_mgr.update(dt)

        # ------------------------------------------------------------------
        # RENDERING
        # ------------------------------------------------------------------
        screen.fill((40, 40, 45))
        pygame.draw.rect(screen, (30, 30, 35), pygame.Rect(0, 0, WIDTH, 58))

        btn_import.draw(screen)
        btn_spawn.draw(screen)
        btn_roll.draw(screen)
        btn_save.draw(screen)
        btn_load.draw(screen)
        btn_toggle_grid.draw(screen)
        btn_toggle_snap.draw(screen)
        btn_assets_panel.draw(screen)
        btn_load_bg.draw(screen)
        btn_import_token.draw(screen)
        btn_connect.draw(screen)

        board_rect = pygame.Rect(0, 58, WIDTH, HEIGHT - 58)
        board_surface = screen.subsurface(board_rect)

        # background
        if background_surface:
            bw, bh = background_surface.get_size()
            if bw > 0 and bh > 0:
                scaled_w = int(bw * camera_zoom)
                scaled_h = int(bh * camera_zoom)
                if scaled_w > 0 and scaled_h > 0:
                    try:
                        bg_scaled = pygame.transform.smoothscale(
                            background_surface, (scaled_w, scaled_h)
                        )
                    except Exception:
                        bg_scaled = pygame.transform.scale(
                            background_surface, (scaled_w, scaled_h)
                        )
                    sx, sy = -int(camera_x * camera_zoom), -int(camera_y * camera_zoom)
                    board_surface.blit(bg_scaled, (sx, sy))

        # tilemap
        tilemap.render(screen, asset_mgr, camera_x, camera_y, camera_zoom, board_rect)

        # grid
        if show_grid:
            draw_grid(
                board_surface,
                GRID_SIZE,
                camera_x,
                camera_y,
                camera_zoom,
                color=(55, 55, 60),
            )

        # tokens
        token_mgr.draw(
            screen,
            camera_x=camera_x,
            camera_y=camera_y,
            camera_zoom=camera_zoom,
            board_rect=board_rect,
            grid_size=GRID_SIZE,
            show_snap_preview=snap_enabled and show_grid,
        )

        # asset panel
        if asset_panel_open:
            asset_panel.draw(screen)
            asset_panel.draw_overlays(screen)

        # context menu
        if context_menu:
            context_menu.draw(screen)

        # properties window
        if properties_window:
            properties_window.draw(screen)

        # dice result
        if dice_result is not None:
            txt = font.render(f"Rol: {dice_result}", True, (255, 255, 255))
            screen.blit(txt, (960, 16))

        # SAY messages (rules)
        now = pygame.time.get_ticks()
        say_messages = [(t, m) for (t, m) in say_messages if now - t < 4000]
        y_msg = HEIGHT - 180
        for t0, msg in reversed(say_messages):
            txt = say_font.render(msg, True, (255, 255, 0))
            screen.blit(txt, (10, y_msg))
            y_msg -= 20

        # chat panel
        chat_panel_rect = pygame.Rect(10, HEIGHT - 150, 420, 110)
        pygame.draw.rect(screen, (20, 20, 24), chat_panel_rect, border_radius=4)
        pygame.draw.rect(screen, (70, 70, 80), chat_panel_rect, 1, border_radius=4)

        max_lines = 6
        visible_msgs = chat_messages[-max_lines:]
        cy = chat_panel_rect.y + 6
        for sender, text in visible_msgs:
            line = f"{sender}: {text}"
            txt = chat_font.render(line, True, (230, 230, 230))
            screen.blit(txt, (chat_panel_rect.x + 6, cy))
            cy += chat_font.get_height() + 2

        chat_input.rect.y = HEIGHT - 30
        chat_input.draw(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
