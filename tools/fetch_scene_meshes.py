# Owner: Student A (Task 2)
"""
tools/fetch_scene_meshes.py — download real chair + stop-sign meshes for
Task 2.iii, replacing the flat-color primitive geoms currently in
assets/scenes/custom_scene.xml.

WHY THIS SCRIPT EXISTS / WHAT IT DOES NOT DO
----------------------------------------------------------------------------
This was written from a sandboxed cloud environment with NO general
internet access -- only pip/npm package registries and `git clone` over
github.com are reachable; Objaverse's own CDN, Sketchfab, and even plain
file downloads from raw.githubusercontent.com are all blocked there. That
means THIS SCRIPT HAS NEVER ACTUALLY BEEN RUN and no mesh file has been
downloaded or inspected by whoever wrote it -- it is a best-effort,
carefully-commented starting point for YOU to run on your own machine
(which has normal internet access), not a finished, verified pipeline.
Read it before running it, and expect to iterate.

WHAT IT DOES (once run somewhere with real internet access):
  1. Uses the `objaverse` package's Objaverse-LVIS annotations -- a subset
     of Objaverse where every model is manually tagged with a category
     name matching the LVIS/COCO-style vocabulary (this is exactly what
     you want: reliably a "chair", not something merely tagged "chair" by
     an uploader). "chair" is a standard LVIS category. A literal
     "stop_sign" LVIS category may or may not exist (LVIS has ~1200
     categories but sign taxonomy is inconsistent across releases) --
     the script tries a short list of plausible category names and tells
     you which one actually matched, so you're not guessing blind.
  2. Downloads ONE model per matched category (the first result -- not
     curated for quality, just for existing) as a .glb.
  3. Converts .glb -> .obj with trimesh, since the rest of this project's
     scene file uses plain Wavefront .obj meshes, not glTF.
  4. Saves into assets/scenes/meshes/, alongside a small JSON manifest
     recording which Objaverse UID / license each file came from -- you
     need this for the report's citation and to confirm the license
     permits your use (Objaverse aggregates many licenses, predominantly
     CC-BY variants; a UID is enough to look the specific one up at
     https://objaverse.allenai.org).

INSTALL (on your own machine, not in this sandbox):
    pip install objaverse trimesh

RUN (from the project root):
    python tools/fetch_scene_meshes.py

AFTER RUNNING, before touching custom_scene.xml:
    python tools/fit_mesh_scale.py assets/scenes/meshes/chair.obj --target-height 0.85
    python tools/fit_mesh_scale.py assets/scenes/meshes/stop_sign.obj --target-height 2.0

That prints the MJCF <mesh scale="..."/> value to paste into
assets/scenes/custom_scene_meshes.xml (see that file's own header comment
for the rest of the swap-over process). Do NOT skip the scale-fitting
step -- meshes from different sources come in wildly different native
units (meters, centimeters, or arbitrary modeling units), and an
unscaled mesh is just as likely to be 100x too large or too small as it
is to be right.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MESH_DIR = PROJECT_ROOT / "assets" / "scenes" / "meshes"

# LVIS category name -> output filename (without extension). Each is
# tried in order; the first one that returns at least one UID wins.
# "chair" is a confirmed-real LVIS category name. The stop-sign
# candidates are guesses at plausible LVIS vocabulary -- if all three
# fail, search https://objaverse.allenai.org yourself for "stop sign" /
# "street sign" / "traffic sign" and hardcode a UID directly (see the
# fallback function below).
TARGETS = {
    "chair": ["chair"],
    "stop_sign": ["stop_sign", "street_sign", "traffic_sign"],
}


def fetch_by_category(category_candidates: list) -> tuple:
    """Returns (matched_category, uid, local_glb_path) for the first
    category name that has at least one annotated UID, or raises."""
    import objaverse

    lvis = objaverse.load_lvis_annotations()
    for cat in category_candidates:
        uids = lvis.get(cat)
        if uids:
            uid = uids[0]
            print(f"  matched LVIS category {cat!r} -> uid {uid} "
                  f"({len(uids)} candidates total, took the first)")
            downloaded = objaverse.load_objects(uids=[uid])
            glb_path = Path(downloaded[uid])
            return cat, uid, glb_path
    raise RuntimeError(
        f"None of {category_candidates} matched an LVIS category with "
        f"any annotated models. Available categories: "
        f"objaverse.load_lvis_annotations().keys() -- inspect that list "
        f"and either add the right name to TARGETS above, or download a "
        f"specific UID manually from https://objaverse.allenai.org and "
        f"place the resulting .obj directly into assets/scenes/meshes/."
    )


def convert_glb_to_obj(glb_path: Path, obj_path: Path) -> None:
    import trimesh

    scene_or_mesh = trimesh.load(glb_path, force="mesh")
    # force="mesh" collapses a multi-node glTF scene into one mesh, which
    # is what a single MJCF <geom type="mesh"> needs. If the source model
    # is genuinely multi-part (e.g. separate seat/legs/back nodes) this
    # merges them into one watertight-ish mesh -- fine for MuJoCo visual
    # + collision geometry, just don't expect per-part materials to
    # survive; the MJCF <geom material=...> override below replaces
    # whatever texture came with the model anyway (see custom_scene_meshes
    # .xml's own comment on why: real geometry for YOLO, flat known color
    # for Task 4's HSV color grounding).
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    scene_or_mesh.export(obj_path)
    print(f"  wrote {obj_path} ({obj_path.stat().st_size} bytes)")


def main():
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}

    for out_name, candidates in TARGETS.items():
        print(f"\n=== {out_name} ===")
        try:
            category, uid, glb_path = fetch_by_category(candidates)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            continue

        obj_path = MESH_DIR / f"{out_name}.obj"
        convert_glb_to_obj(glb_path, obj_path)
        manifest[out_name] = {
            "lvis_category": category,
            "objaverse_uid": uid,
            "source": f"https://objaverse.allenai.org/explore/{uid}",
            "obj_file": str(obj_path.relative_to(PROJECT_ROOT)),
            "note": "License varies per-model on Objaverse -- check the "
                    "source URL above and record the specific license in "
                    "the report before submitting.",
        }

    manifest_path = MESH_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {manifest_path}")
    print(
        "\nNext step: run tools/fit_mesh_scale.py on each .obj to get the "
        "right MJCF <mesh scale=.../> values -- see this script's own "
        "docstring."
    )


if __name__ == "__main__":
    main()
