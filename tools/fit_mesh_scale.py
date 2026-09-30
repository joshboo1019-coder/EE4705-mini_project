"""
tools/fit_mesh_scale.py — compute the MJCF <mesh scale="sx sy sz"/> value
that makes a downloaded .obj match a target real-world size.

WHY THIS EXISTS: meshes pulled from Objaverse (or anywhere else) come in
whatever units the original modeler used -- meters, centimeters, or
arbitrary "modeling units" with no physical meaning at all. Dropping one
into MuJoCo unscaled is just as likely to spawn a chair the size of a
building, or a stop sign the size of a grain of rice, as it is to be
correct. This reads the mesh's own bounding box with trimesh and prints
the uniform scale factor needed to hit a target height, so you can paste
a real number into custom_scene_meshes.xml instead of guessing and
re-loading the sim over and over.

Like tools/fetch_scene_meshes.py, this has NOT been run against a real
downloaded mesh by whoever wrote it (no internet access from that sandbox
to actually fetch one) -- the bounding-box math itself is standard and
should be reliable, but the trimesh load path can vary in shape depending
on the source file (a lone Trimesh vs. a multi-body Scene), which is
still handled below, just untested end-to-end.

INSTALL: pip install trimesh numpy

RUN:
    python tools/fit_mesh_scale.py assets/scenes/meshes/chair.obj --target-height 0.85
    python tools/fit_mesh_scale.py assets/scenes/meshes/stop_sign.obj --target-height 2.0

Prints something like:
    Mesh bounding box (native units): x=0.62 y=0.58 z=1.94
    Native 'up' axis assumed: Z (largest-looking vertical extent -- verify visually)
    To reach target height 0.85 m: uniform scale = 0.4381
    Paste into custom_scene_meshes.xml:
        <mesh name="chair_mesh" file="chair.obj" scale="0.4381 0.4381 0.4381"/>
"""

import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("obj_path", type=Path, help="path to the .obj file to measure")
    ap.add_argument("--target-height", type=float, required=True,
                     help="desired real-world height in meters (the mesh's "
                          "own vertical/up axis, see the printed assumption "
                          "below -- correct it with --up-axis if wrong)")
    ap.add_argument("--up-axis", choices=["x", "y", "z"], default=None,
                     help="which axis is 'up' in the source mesh, if you "
                          "already know it (glTF/Objaverse convention is "
                          "usually +Y up, but the .obj exporter used here "
                          "may or may not have converted that -- if the "
                          "auto-guess below looks wrong, e.g. picks the "
                          "axis a chair is WIDE along instead of TALL "
                          "along, override it explicitly)")
    args = ap.parse_args()

    if not args.obj_path.is_file():
        raise SystemExit(
            f"{args.obj_path} does not exist -- run "
            f"tools/fetch_scene_meshes.py first, or point this at wherever "
            f"you manually saved a downloaded mesh."
        )

    import trimesh

    loaded = trimesh.load(args.obj_path, force="mesh")
    bounds = loaded.bounds  # shape (2, 3): [min_xyz, max_xyz]
    extents = bounds[1] - bounds[0]
    axis_names = ["x", "y", "z"]

    print(f"Mesh bounding box (native units): "
          f"x={extents[0]:.3f} y={extents[1]:.3f} z={extents[2]:.3f}")

    if args.up_axis:
        up_idx = axis_names.index(args.up_axis)
        print(f"Using --up-axis={args.up_axis} as specified.")
    else:
        # Heuristic only: assume the LARGEST extent is the "up"/height
        # axis. True for most upright single objects (a chair is usually
        # taller than it is wide/deep, a sign-on-a-pole likewise), but
        # NOT reliable for something wider than it is tall -- always
        # sanity-check the printed axis assumption against what you know
        # the object should look like before trusting the scale number.
        up_idx = int(extents.argmax())
        print(f"Native 'up' axis assumed: {axis_names[up_idx].upper()} "
              f"(largest extent -- verify this is actually vertical for "
              f"this particular mesh; override with --up-axis if not)")

    native_height = extents[up_idx]
    if native_height <= 0:
        raise SystemExit("Degenerate mesh: zero extent along the assumed "
                          "up axis. Check the file loaded correctly.")

    scale = args.target_height / native_height
    print(f"To reach target height {args.target_height:.3f} m: "
          f"uniform scale = {scale:.4f}")

    mesh_name = args.obj_path.stem + "_mesh"
    print("\nPaste into custom_scene_meshes.xml's <asset> block:")
    print(f'    <mesh name="{mesh_name}" file="{args.obj_path.name}" '
          f'scale="{scale:.4f} {scale:.4f} {scale:.4f}"/>')
    print(
        "\nAfter pasting, still test-load the scene and LOOK at it -- this "
        "only fixes overall height, not orientation. If the mesh loads "
        "sideways or upside down, that's a separate rotation fix (a "
        "<geom ... euler=\"...\"/> on the body, or re-exporting with a "
        "different up-axis convention), not something this script solves."
    )


if __name__ == "__main__":
    main()
