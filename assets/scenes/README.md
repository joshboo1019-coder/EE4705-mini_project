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

| Object | Position (x, y) |
| --- | --- |
| `green_chair` | (-2.0, 2.0) |
| `red_chair` | (-2.0, -2.0) | 
| 'Blue_chair'| (3.45, 2.0) | 
| `orange_sports_ball` | (-3.5, 0.0) |
| `red_stop_sign` | (-1.3, 0.0) |
| `yellow_stop_sign` | (-4.5, 2.0) | 
| `green_stop_sign` | (-4.5, -2.0) |

Every pair of objects is also ≥2.1 m apart from each other. These numbers
match `core.config.OBJECT_POSITIONS` exactly — if you move an object in
one, update the other. The scene file's own header comment has the full
methodology writeup, in case the terrain or objects are adjusted again
later and this needs re-verifying.

