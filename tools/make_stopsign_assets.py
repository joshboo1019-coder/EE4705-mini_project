"""
tools/make_stopsign_assets.py -- octagonal STOP-sign plate for the scene.
Written by Student B (assist), pending review by Student A (scene) and
Student C (Task 4).

Generates
  * assets/scenes/textures/stopsign_<colour>.png -- one 512x512 texture per
    sign colour: a white-bordered octagon in the sign colour with white
    "STOP" letters (the octagon touches all four image edges);
  * the inline MuJoCo <mesh> attributes (vertex / face / texcoord) of a
    regular octagonal plate, 0.30 m flat-to-flat and 0.02 m thick, whose two
    faces both map the texture so "STOP" reads correctly from either side.

The mesh lives in assets/scenes/custom_scene.xml's <asset> block
(name "stopsign_octagon"); perception/scenarios.py reuses it, because
build_scene_xml() keeps the base scene's assets.

    python tools/make_stopsign_assets.py            # (re)write the PNGs
    python tools/make_stopsign_assets.py --mesh     # also print the <mesh> element

The PNGs are committed, so nothing here runs at simulation time.
"""

import argparse
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEX_DIR = ROOT / "assets" / "scenes" / "textures"

WIDTH_M = 0.30        # flat-to-flat, same as the old 0.30 m square plates
THICK_M = 0.02        # plate thickness
TEX_PX = 512
BORDER = 0.045        # white border, fraction of the flat-to-flat width
TEXT_W, TEXT_H = 0.76, 0.32   # "STOP" box, fraction of the width (real sign: ~1/3 tall)

# Background colours. red/yellow/green are custom_scene.xml's sign_*_mat rgba
# (the colours the signs had before); the rest are perception/scenarios.py's
# COLOR_RGBA so a generated scenario can ask for any of its colours.
COLOURS = {
    "red": (0.80, 0.05, 0.05),
    "yellow": (0.95, 0.80, 0.05),
    "green": (0.10, 0.60, 0.20),
    "blue": (0.05, 0.15, 0.90),
    "orange": (0.95, 0.55, 0.10),
    "purple": (0.55, 0.10, 0.75),
    "pink": (0.95, 0.20, 0.55),
}
FONTS = ("/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf")


def octagon_xy(apothem: float, cx: float = 0.0, cy: float = 0.0):
    """Regular octagon with flat top/bottom/left/right edges, counter-clockwise."""
    r = apothem / math.cos(math.pi / 8)
    return [(cx + r * math.cos(math.pi / 8 + k * math.pi / 4),
             cy + r * math.sin(math.pi / 8 + k * math.pi / 4)) for k in range(8)]


def make_texture(rgb, path: Path, size: int = TEX_PX, ss: int = 4):
    from PIL import Image, ImageDraw, ImageFont

    big = size * ss
    col = tuple(int(round(255 * c)) for c in rgb)
    img = Image.new("RGB", (big, big), col)
    d = ImageDraw.Draw(img)
    c = big / 2
    d.polygon(octagon_xy(big / 2, c, c), fill=(255, 255, 255))
    d.polygon(octagon_xy(big / 2 * (1 - 2 * BORDER), c, c), fill=col)
    font = next(ImageFont.truetype(f, 400) for f in FONTS if Path(f).exists())
    tmp = Image.new("L", (2400, 800), 0)
    ImageDraw.Draw(tmp).text((50, 50), "STOP", font=font, fill=255)
    tmp = tmp.crop(tmp.getbbox())
    tw, th = int(TEXT_W * big), int(TEXT_H * big)
    tmp = tmp.resize((tw, th), Image.LANCZOS)
    img.paste((255, 255, 255), (int(c - tw / 2), int(c - th / 2)), tmp)
    img = img.resize((size, size), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)


def mesh_attrs(width: float = WIDTH_M, thick: float = THICK_M):
    """Octagonal prism in the local x-z plane (faces normal to +-y). Vertices
    are duplicated per face so each face keeps its own texcoords and flat
    normals. Front face (-y) maps u = 0.5 + x/w, back face (+y) mirrors u, so
    the text is not mirrored from either side; v = 0.5 - z/w (image rows run
    top to bottom). The 8 edge faces sample the white border."""
    a = width / 2
    rim = octagon_xy(a)
    verts, uvs, faces = [], [], []

    def add(p, uv):
        verts.append(p)
        uvs.append(uv)
        return len(verts) - 1

    for side, y in (("front", -thick / 2), ("back", thick / 2)):
        sgn = 1 if side == "front" else -1
        ctr = add((0.0, y, 0.0), (0.5, 0.5))
        ids = [add((x, y, z), (0.5 + sgn * x / width, 0.5 - z / width)) for x, z in rim]
        for k in range(8):
            i, j = ids[k], ids[(k + 1) % 8]
            faces.append((ctr, i, j) if side == "front" else (ctr, j, i))
    edge_uv = (0.5, 0.5 * BORDER)   # inside the white border, top edge
    for k in range(8):
        (x0, z0), (x1, z1) = rim[k], rim[(k + 1) % 8]
        f0 = add((x0, -thick / 2, z0), edge_uv)
        f1 = add((x1, -thick / 2, z1), edge_uv)
        b0 = add((x0, thick / 2, z0), edge_uv)
        b1 = add((x1, thick / 2, z1), edge_uv)
        faces += [(f0, b0, b1), (f0, b1, f1)]      # outward normal

    def fmt(rows):
        return "  ".join(" ".join(f"{round(v, 6) + 0.0:.5g}" for v in r) for r in rows)

    return dict(vertex=fmt(verts), face=fmt(faces), texcoord=fmt(uvs))


def mesh_element(name: str = "stopsign_octagon") -> str:
    a = mesh_attrs()
    return (f'<mesh name="{name}"\n      vertex="{a["vertex"]}"\n'
            f'      face="{a["face"]}"\n      texcoord="{a["texcoord"]}" />')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", action="store_true", help="print the <mesh> element")
    a = ap.parse_args()
    for name, rgb in COLOURS.items():
        p = TEX_DIR / f"stopsign_{name}.png"
        make_texture(rgb, p)
        print(f"wrote {p.relative_to(ROOT)} ({p.stat().st_size} B)")
    if a.mesh:
        print(mesh_element())


if __name__ == "__main__":
    main()
