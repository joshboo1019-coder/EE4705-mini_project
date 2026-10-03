"""
eval/e2e/trace.py — Student B. Ground-truth trace for the e2e harness ONLY.

`start_trace(skills, path)` starts a daemon thread that samples the real sim
at ~10 Hz and appends JSON lines to `path`:

    {"t": wall_time, "x", "y", "yaw", "z", "roll", "pitch",
     "contacts": ["<robot geom>|<other geom>", ...]}   # only when non-empty

A contact is any robot geom touching any geom that is not the floor plane
(terrain, stairs, rubble, objects). Nothing is printed to the terminal, and
nothing here feeds back into control: this is logging for evaluation (fall /
contact checks, true distance at the stop), which is the only allowed use of
ground truth. It reads RealSkills' private _model/_data read-only from
another thread; a torn read only affects one sample of the log.
"""

import json
import math
import threading
import time


def _robot_bodies(model, root_name: str = "trunk"):
    import mujoco
    root = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, root_name)
    if root < 0:
        return set()
    bodies = {root}
    changed = True
    while changed:
        changed = False
        for b in range(model.nbody):
            if b not in bodies and int(model.body_parentid[b]) in bodies:
                bodies.add(b)
                changed = True
    return bodies


def _geom_name(model, g: int) -> str:
    import mujoco
    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, g)
    if name:
        return name
    body = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[g]))
    return f"{body or 'body'}#{g}"


def start_trace(skills, path: str, hz: float = 10.0) -> threading.Thread:
    model = getattr(skills, "_model", None)
    data = getattr(skills, "_data", None)
    if model is None or data is None:
        return None
    robot = _robot_bodies(model)
    robot_geom = [int(model.geom_bodyid[g]) in robot for g in range(model.ngeom)]
    plane = [int(model.geom_type[g]) == 0 for g in range(model.ngeom)]   # mjGEOM_PLANE

    def loop():
        period = 1.0 / hz
        with open(path, "a") as f:
            while True:
                try:
                    q = [float(v) for v in data.qpos[0:7]]
                    w, x, y, z = q[3:7]
                    roll = math.degrees(math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
                    pitch = math.degrees(math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x)))))
                    yaw = math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))
                    contacts = set()
                    for i in range(int(data.ncon)):
                        c = data.contact[i]
                        g1, g2 = int(c.geom1), int(c.geom2)
                        if robot_geom[g1] == robot_geom[g2]:
                            continue
                        rg, og = (g1, g2) if robot_geom[g1] else (g2, g1)
                        if plane[og]:
                            continue
                        contacts.add(f"{_geom_name(model, rg)}|{_geom_name(model, og)}")
                    rec = {"t": round(time.time(), 3), "x": round(q[0], 4), "y": round(q[1], 4),
                           "yaw": round(yaw, 2), "z": round(q[2], 4),
                           "roll": round(roll, 2), "pitch": round(pitch, 2)}
                    if contacts:
                        rec["contacts"] = sorted(contacts)
                    f.write(json.dumps(rec) + "\n")
                    f.flush()
                except Exception as e:  # never take the sim down
                    f.write(json.dumps({"t": time.time(), "error": repr(e)}) + "\n")
                time.sleep(period)

    t = threading.Thread(target=loop, daemon=True, name="e2e-trace")
    t.start()
    return t
