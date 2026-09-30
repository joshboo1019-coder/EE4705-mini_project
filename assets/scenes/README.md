# assets/scenes/

Student A: put `custom_scene.xml` (or your platform's equivalent scene
file) here, registered as a MapSpec per the example repo's convention.
Needs >=3 objects from >=2 COCO classes, including two objects of the same
class in different colors (e.g. `green_chair`, `red_chair`).

Record each object's world (x, y) position in `core.config.OBJECT_POSITIONS`
using the `"<color>_<class>"` key convention already used there — Task 4's
distance logging depends on those keys matching what Student C reads.

## Current scene: `custom_scene.xml`

Built on top of the example platform's own bundled `rc26_track` obstacle
course rather than an empty scene, since an earlier from-scratch empty
custom scene had a locomotion bug (the robot couldn't stand/walk on it)
that was never root-caused — building on the platform's own
known-working terrain sidesteps that entirely. The terrain's 152 `<geom>`
elements were imported programmatically (not hand-copied) from:

- Repo: https://github.com/aoqianz/quadruped_mujoco
- File: `src/runtime_control/maps/26rc_track.xml`
- Registered as `"rc26_track"` in `src/runtime_control/resources.py`'s
  `_BUNDLED_MAPS` dict, imported the same way the platform's own
  `MapSpec` machinery would (`exclude_bodies=("trunk",)`, dropping that
  file's own embedded demo-robot body).

Six graded object bodies sit on top of that terrain: `green_chair`,
`red_chair` (the same-class/different-color pair), `orange_sports_ball`,
and `red_stop_sign` / `yellow_stop_sign` / `green_stop_sign`. Each stop
sign is a pole plus **two** perpendicular flat plates forming a "+"
cross (not one flat plate) — a single plate is edge-on and effectively
invisible from most approach angles.

**Object placement was computed, not eyeballed.** An earlier version
placed all six objects by eye against the track's `<statistic>` tag and
ended up overlapping several of them with the track's own terrain geoms
(one stop sign was ~1 m *inside* a track geom). The current positions
were instead found by scanning a grid of candidate `(x, y)` points,
computing each one's actual clearance to the nearest track geom (center
distance minus that geom's half-extent), and picking a cluster with good
clearance west of the robot's spawn:

| Object | Position (x, y) | Clearance to nearest track geom |
| --- | --- | --- |
| `green_chair` | (-2.0, 2.0) | 2.00 m |
| `red_chair` | (-2.0, -2.0) | 2.46 m |
| `orange_sports_ball` | (-3.5, 0.0) | 3.50 m |
| `red_stop_sign` | (-1.3, 0.0) | 1.30 m |
| `yellow_stop_sign` | (-4.5, 2.0) | 3.59 m |
| `green_stop_sign` | (-4.5, -2.0) | 4.77 m |

Every pair of objects is also ≥2.1 m apart from each other. These numbers
match `core.config.OBJECT_POSITIONS` exactly — if you move an object in
one, update the other. The scene file's own header comment has the full
methodology writeup, in case the terrain or objects are adjusted again
later and this needs re-verifying.

## ⚠️ Known risk: chairs/signs are primitive geoms, not real meshes

The handout is explicit: *"A plain colored box will not be detected as a
'chair'; free meshes can be found on Objaverse or Sketchfab."*
`custom_scene.xml`'s chairs (4 leg boxes + seat + backrest) and stop
signs (pole + two perpendicular plates) are exactly that — flat-color
primitive `<geom>`s, not real meshes. They're geometrically
chair-/sign-shaped and human-scale, but not photorealistic, so YOLO
detection confidence on them is a real, acknowledged risk, not
hypothetical.

**`custom_scene_meshes.xml`** is a prepared (but not yet active) mesh
variant — same terrain, same object positions/colors, but the 6 object
bodies use `<geom type="mesh">` referencing `meshes/chair.obj` and
`meshes/stop_sign.obj` instead of primitives. Those two `.obj` files
**do not exist in this repo yet** — they need to be downloaded on a
machine with real internet access (this project was largely built from
a sandbox that could not reach Objaverse/Sketchfab/even plain GitHub
file downloads). `custom_scene_meshes.xml`'s own header comment has the
full step-by-step: run `tools/fetch_scene_meshes.py` to download +
convert the meshes, `tools/fit_mesh_scale.py` to compute the right MJCF
`<mesh scale="..."/>`, then test-load and visually fix orientation
(`euler="0 0 0"` placeholders on each mesh geom are almost certainly
wrong for whatever orientation the downloaded mesh comes in) before
switching `core.config.SCENE_PATH` over to it.

Until that's done, `core.config.SCENE_PATH` still points at the
original `custom_scene.xml` — nothing is broken by
`custom_scene_meshes.xml` existing, it's just inert until you finish
setting it up.
