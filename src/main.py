import pygame
import sys
from assets import AssetManager
from token import TokenManager
from ui import Button, ContextMenu, PropertiesWindow, AssetBrowserPanel
from utils import roll_dice, save_campaign, load_campaign
import os
import tkinter as tk
from tkinter import filedialog

WIDTH, HEIGHT = 1280, 720
FPS = 60

GRID_SIZE = 64
SHOW_GRID_DEFAULT = True
SNAP_DEFAULT = True

CAMERA_ZOOM_MIN = 0.2
CAMERA_ZOOM_MAX = 4.0


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
        filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.bmp")]
    )
    root.destroy()
    if not fp:
        return None
    return fp


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
    pygame.display.set_caption("UMI.DA Tabletop - Background + Camera + Assets")
    clock = pygame.time.Clock()

    base_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(base_dir, "..", "assets")
    data_dir = os.path.join(base_dir, "..", "data")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    asset_mgr = AssetManager(assets_dir)
    token_mgr = TokenManager(asset_mgr)

    camera_x = 0.0
    camera_y = 0.0
    camera_zoom = 1.0

    background_surface = None
    background_path = None

    btn_import = Button("Import Asset", 10, 10, 140, 32)
    btn_spawn = Button("Spawn Token", 160, 10, 140, 32)
    btn_roll = Button("Roll d20", 310, 10, 100, 32)
    btn_save = Button("Save", 420, 10, 80, 32)
    btn_load = Button("Load", 510, 10, 80, 32)
    btn_toggle_grid = Button("Grid: ON" if SHOW_GRID_DEFAULT else "Grid: OFF", 600, 10, 100, 32)
    btn_toggle_snap = Button("Snap: ON" if SNAP_DEFAULT else "Snap: OFF", 710, 10, 100, 32)
    btn_assets_panel = Button("Assets <<", 820, 10, 110, 32)
    btn_load_bg = Button("Load Background", 940, 10, 160, 32)

    show_grid = SHOW_GRID_DEFAULT
    snap_enabled = SNAP_DEFAULT
    asset_panel_open = True

    asset_panel_rect = pygame.Rect(0, 58, 280, HEIGHT - 58)
    asset_panel = AssetBrowserPanel(asset_panel_rect, asset_mgr)

    dice_result = None
    font = pygame.font.SysFont(None, 24)

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

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    camera_x = 0.0
                    camera_y = 0.0
                    camera_zoom = 1.0
                if event.key == pygame.K_SPACE:
                    space_held = True
            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE:
                    space_held = False
                    panning_space = False

            event_consumed_by_panel = False

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
                            wx, wy = screen_to_world(cx, cy, camera_x, camera_y, camera_zoom, board_rect)
                            t = token_mgr.spawn_token(asset_name, wx, wy)
                            if t:
                                t.x = wx - t.w / 2.0
                                t.y = wy - t.h / 2.0

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

            if context_menu and not event_consumed_by_panel:
                context_menu.handle_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not context_menu.rect.collidepoint(event.pos):
                        context_menu = None

            if properties_window and not event_consumed_by_panel:
                properties_window.handle_event(event)
                if properties_window.closed:
                    properties_window = None

            if not event_consumed_by_panel and not properties_window and not panning_space and not panning_mmb:
                cm_action = token_mgr.handle_event(
                    event,
                    grid_size=GRID_SIZE,
                    snap_enabled=snap_enabled,
                    camera_x=camera_x,
                    camera_y=camera_y,
                    camera_zoom=camera_zoom,
                    board_rect=board_rect,
                )
                if cm_action:
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
                        ("Delete", "delete"),
                    ]
                    context_menu = ContextMenu(
                        menu_items,
                        cm_action["pos"],
                        cm_action["token"],
                        token_mgr,
                    )

            if not event_consumed_by_panel and token_mgr.last_action:
                action_payload = token_mgr.last_action
                token_mgr.last_action = None
                if action_payload.get("action") == "properties":
                    t = action_payload.get("token")
                    properties_window = PropertiesWindow(
                        (200, 80, 560, 460),
                        t,
                        on_apply=lambda tok, newdata: token_mgr.apply_token_properties(
                            tok, newdata
                        ),
                    )
                    context_menu = None

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
                        wx, wy = screen_to_world(cx, cy, camera_x, camera_y, camera_zoom, board_rect)
                        first = list(asset_mgr.assets.keys())[0]
                        token_mgr.spawn_token(first, wx, wy)
                elif btn_roll.rect.collidepoint(mx, my):
                    dice_result = roll_dice(20)
                elif btn_save.rect.collidepoint(mx, my):
                    path = os.path.join(data_dir, "campaign.json")
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
                    save_campaign(path, asset_mgr, token_mgr, bg_state)
                    print("Saved to", path)
                elif btn_load.rect.collidepoint(mx, my):
                    path = os.path.join(data_dir, "campaign.json")
                    if os.path.exists(path):
                        bg_state = load_campaign(path, asset_mgr, token_mgr)
                        print("Loaded from", path)
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
                    btn_assets_panel.text = "Assets <<" if asset_panel_open else "Assets >>"
                elif btn_load_bg.rect.collidepoint(mx, my):
                    fp = load_background_dialog()
                    if fp:
                        surf = asset_mgr._load_surface(fp)
                        if surf:
                            background_surface = surf
                            background_path = fp
                            camera_x, camera_y, camera_zoom = fit_camera_to_background(
                                background_surface, (camera_x, camera_y, camera_zoom)
                            )

        token_mgr.update(dt)

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

        board_rect = pygame.Rect(0, 58, WIDTH, HEIGHT - 58)
        board_surface = screen.subsurface(board_rect)

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

        if show_grid:
            draw_grid(board_surface, GRID_SIZE, camera_x, camera_y, camera_zoom, color=(55, 55, 60))

        token_mgr.draw(
            screen,
            camera_x=camera_x,
            camera_y=camera_y,
            camera_zoom=camera_zoom,
            board_rect=board_rect,
            grid_size=GRID_SIZE,
            show_snap_preview=snap_enabled and show_grid,
        )

        if asset_panel_open:
            asset_panel.draw(screen)
            asset_panel.draw_overlays(screen)

        if context_menu:
            context_menu.draw(screen)

        if properties_window:
            properties_window.draw(screen)

        if dice_result is not None:
            txt = font.render(f"Rol: {dice_result}", True, (255, 255, 255))
            screen.blit(txt, (960, 16))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
