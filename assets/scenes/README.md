# assets/scenes/

Student A: put `custom_scene.xml` (or your platform's equivalent scene
file) here, registered as a MapSpec per the example repo's convention.
Needs >=3 objects from >=2 COCO classes, including two objects of the same
class in different colors (e.g. `green_chair`, `red_chair`).

Record each object's world (x, y) position in `core.config.OBJECT_POSITIONS`
using the `"<color>_<class>"` key convention already used there — Task 4's
distance logging depends on those keys matching what Student C reads.
