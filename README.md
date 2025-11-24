# TableTop
UMI.DA Tabletop - Prototype

Install:
    python -m pip install -r requirements.txt

Run:
    python src/main.py

Folders:
- assets/: drop or import your PNG/JPG images here via the Import Asset button.
- data/: saved campaigns (campaign.json) will be written here.

Features:
- Grid + snapping
- Import assets (opens file dialog)
- Spawn tokens, drag & drop
- Right-click context menu (Rotate, Scale, Delete, Properties)
- Advanced Properties window (Name, HP, Max HP, Notes, RGB tint)
- Save/Load campaign (saves token properties & asset paths)

If you encounter issues with pygame on Python 3.13, use Python 3.10-3.12.
