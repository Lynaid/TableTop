import pygame
import sys
from assets import AssetManager
from token import TokenManager
from ui import Button, ContextMenu, PropertiesWindow
from utils import roll_dice, save_campaign, load_campaign
import os

WIDTH, HEIGHT = 1280, 720
FPS = 60

GRID_SIZE = 64
SHOW_GRID_DEFAULT = True
SNAP_DEFAULT = True

def draw_grid(surface, grid_size, color=(70,70,75)):
    w,h = surface.get_size()
    for x in range(0, w, grid_size):
        pygame.draw.line(surface, color, (x, 58), (x, h))
    for y in range(58, h, grid_size):
        pygame.draw.line(surface, color, (0, y), (w, y))

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("UMI.DA Tabletop - Properties Window (Advanced)")
    clock = pygame.time.Clock()

    base_dir = os.path.dirname(__file__)
    assets_dir = os.path.join(base_dir, "..", "assets")
    data_dir = os.path.join(base_dir, "..", "data")
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    asset_mgr = AssetManager(assets_dir)
    token_mgr = TokenManager(asset_mgr)

    # UI buttons
    btn_import = Button("Import Asset", 10, 10, 140, 32)
    btn_spawn = Button("Spawn Token", 160, 10, 140, 32)
    btn_roll = Button("Roll d20", 310, 10, 100, 32)
    btn_save = Button("Save", 420, 10, 80, 32)
    btn_load = Button("Load", 510, 10, 80, 32)
    btn_toggle_grid = Button("Grid: ON" if SHOW_GRID_DEFAULT else "Grid: OFF", 600, 10, 100, 32)
    btn_toggle_snap = Button("Snap: ON" if SNAP_DEFAULT else "Snap: OFF", 710, 10, 100, 32)

    show_grid = SHOW_GRID_DEFAULT
    snap_enabled = SNAP_DEFAULT

    dice_result = None
    font = pygame.font.SysFont(None, 24)

    context_menu = None
    properties_window = None

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Context menu input has priority when open
            if context_menu:
                context_menu.handle_event(event)
                # clicking outside closes it; left click outside handled in context_menu
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not context_menu.rect.collidepoint(event.pos):
                        context_menu = None

            # Properties window handles its own events when open
            if properties_window:
                properties_window.handle_event(event)
                # check if window asked to apply/cancel
                if properties_window.closed:
                    # if applied, the window already updated the token via callback
                    properties_window = None

            # pass events to token manager so tokens can handle dragging and right-clicks
            cm_action = token_mgr.handle_event(event, grid_size=GRID_SIZE, snap_enabled=snap_enabled)
            if cm_action:
                # cm_action is dict like {"token": token, "pos": (x,y)}
                menu_items = [
                    ("Properties", "properties"),
                    ("Rotate CW 45°", "rotate_cw"),
                    ("Rotate CCW 45°", "rotate_ccw"),
                    ("Scale +10%", "scale_up"),
                    ("Scale -10%", "scale_down"),
                    ("Delete", "delete")
                ]
                context_menu = ContextMenu(menu_items, cm_action["pos"], cm_action["token"], token_mgr,
                                           on_properties_request=lambda tok, pos: (
                                               # create properties window
                                               tok, pos
                                           ))

            # If context menu exists and user clicked an item, ContextMenu will call token_mgr.perform_menu_action
            # We intercept 'properties' action here by checking last selection stored in token_mgr (token_mgr.last_action)
            if token_mgr.last_action:
                action_payload = token_mgr.last_action
                token_mgr.last_action = None
                if action_payload.get("action") == "properties":
                    # open properties window
                    t = action_payload.get("token")
                    # create a properties window; callback will be bound to apply changes
                    properties_window = PropertiesWindow( (200,80,400,380), t, on_apply=lambda tok, newdata: token_mgr.apply_token_properties(tok, newdata) )
                    context_menu = None  # close menu

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not properties_window:
                mx, my = event.pos
                if btn_import.rect.collidepoint(mx,my):
                    asset_mgr.import_asset_dialog()
                elif btn_spawn.rect.collidepoint(mx,my):
                    if asset_mgr.assets:
                        first = list(asset_mgr.assets.keys())[0]
                        token_mgr.spawn_token(first, 400, 200)
                elif btn_roll.rect.collidepoint(mx,my):
                    dice_result = roll_dice(20)
                elif btn_save.rect.collidepoint(mx,my):
                    path = os.path.join(data_dir, "campaign.json")
                    save_campaign(path, asset_mgr, token_mgr)
                    print("Saved to", path)
                elif btn_load.rect.collidepoint(mx,my):
                    path = os.path.join(data_dir, "campaign.json")
                    if os.path.exists(path):
                        load_campaign(path, asset_mgr, token_mgr)
                        print("Loaded from", path)
                elif btn_toggle_grid.rect.collidepoint(mx,my):
                    show_grid = not show_grid
                    btn_toggle_grid.text = "Grid: ON" if show_grid else "Grid: OFF"
                elif btn_toggle_snap.rect.collidepoint(mx,my):
                    snap_enabled = not snap_enabled
                    btn_toggle_snap.text = "Snap: ON" if snap_enabled else "Snap: OFF"

        token_mgr.update(dt)

        # render
        screen.fill((40, 40, 45))
        pygame.draw.rect(screen, (30,30,35), pygame.Rect(0,0,WIDTH,58))
        btn_import.draw(screen)
        btn_spawn.draw(screen)
        btn_roll.draw(screen)
        btn_save.draw(screen)
        btn_load.draw(screen)
        btn_toggle_grid.draw(screen)
        btn_toggle_snap.draw(screen)

        # board and grid
        board_rect = pygame.Rect(0, 58, WIDTH, HEIGHT-58)
        board_surface = screen.subsurface(board_rect)
        if show_grid:
            draw_grid(board_surface, GRID_SIZE, color=(55,55,60))

        token_mgr.draw(screen, grid_size=GRID_SIZE, show_snap_preview=snap_enabled and show_grid)

        # draw context menu and properties window on top if present
        if context_menu:
            context_menu.draw(screen)
        if properties_window:
            properties_window.draw(screen)

        # dice result
        if dice_result is not None:
            txt = font.render(f"Rol: {dice_result}", True, (255,255,255))
            screen.blit(txt, (830, 16))

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
