"""Validate scene inputs before Blender resets the scene or builds geometry."""
import argparse
import json
import math
from pathlib import Path

REQUIRED = {
    "render": ("resolution", "samples", "output"),
    "world": ("sun_elevation_deg", "sun_rotation_deg"),
    "terrain": ("size", "subdivisions", "base_height", "detail_height"),
    "water": ("level", "size"),
    "monoliths": ("count", "min_height", "max_height", "spread", "seed"),
    "fog": ("cube_size", "density"),
    "dust": ("count", "area", "particle_size"),
    "camera": ("location", "target", "lens_mm", "fstop"),
}


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="scene.json", help="scene JSON (relative to the working directory)")
    parser.add_argument("--check", action="store_true", help="validate only; Blender is not required")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true", help="render one 320×180 preview")
    mode.add_argument("--anim", action="store_true", help="render the configured camera animation")
    mode.add_argument("--anim-preview", action="store_true", help="render up to 12 animation preview frames")
    opts = vars(parser.parse_args(argv))
    opts["anim"] = opts["anim"] or opts["anim_preview"]
    return opts


def validate_scene(cfg, require_animation=False):
    def fail(field, reason):
        raise ValueError(f"{field}: {reason}")

    def finite_tree(value, field="scene"):
        if isinstance(value, float) and not math.isfinite(value):
            fail(field, "must be finite")
        if isinstance(value, dict):
            for key, item in value.items():
                finite_tree(item, f"{field}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                finite_tree(item, f"{field}[{index}]")

    def section(name, keys):
        if not isinstance(cfg.get(name), dict):
            fail(name, "must be an object")
        for key in keys:
            if key not in cfg[name]:
                fail(f"{name}.{key}", "required")

    def number(field, minimum=None, integer=False):
        name, key = field.split(".")
        value = cfg[name][key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail(field, "must be a number")
        if integer and not isinstance(value, int):
            fail(field, "must be an integer")
        if minimum is not None and value < minimum:
            fail(field, f"must be >= {minimum}")

    def vector(field, size, positive_integers=False):
        name, key = field.split(".")
        value = cfg[name][key]
        if not isinstance(value, list) or len(value) != size:
            fail(field, f"must contain {size} numbers")
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                fail(field, "must contain numbers")
            if positive_integers and (not isinstance(item, int) or item < 1):
                fail(field, "must contain positive integers")

    def path(field):
        name, key = field.split(".")
        value = cfg[name][key]
        if not isinstance(value, str) or not value.strip() or "\0" in value:
            fail(field, "must be a nonempty path")

    if not isinstance(cfg, dict):
        fail("scene", "must be an object")
    finite_tree(cfg)
    for name, keys in REQUIRED.items():
        section(name, keys)
    vector("render.resolution", 2, positive_integers=True)
    number("render.samples", 1, integer=True)
    path("render.output")
    for field in ("world.sun_elevation_deg", "world.sun_rotation_deg", "terrain.base_height", "terrain.detail_height", "water.level"):
        number(field)
    for field in ("terrain.size", "water.size", "monoliths.min_height", "monoliths.max_height", "fog.cube_size", "dust.area", "dust.particle_size", "camera.lens_mm", "camera.fstop"):
        number(field, 0)
        name, key = field.split(".")
        if cfg[name][key] == 0:
            fail(field, "must be > 0")
    number("terrain.subdivisions", 2, integer=True)
    for field in ("monoliths.count", "dust.count"):
        number(field, 0, integer=True)
    number("monoliths.seed", integer=True)
    for field in ("monoliths.spread", "fog.density"):
        number(field, 0)
    if cfg["monoliths"]["max_height"] < cfg["monoliths"]["min_height"]:
        fail("monoliths.max_height", "must be >= min_height")
    for field in ("camera.location", "camera.target"):
        vector(field, 3)
    if require_animation and "animation" not in cfg:
        fail("animation", "required for --anim / --anim-preview")
    if "animation" in cfg:
        section("animation", ("frames", "fps", "type", "look_at", "output_dir"))
        a = cfg["animation"]
        number("animation.frames", 2, integer=True)
        number("animation.fps", 1, integer=True)
        vector("animation.look_at", 3)
        path("animation.output_dir")
        if a["type"] == "orbit":
            section("animation", ("radius", "height", "azimuth_start_deg", "azimuth_end_deg"))
            number("animation.radius", 0)
            if a["radius"] == 0:
                fail("animation.radius", "must be > 0")
            for key in ("height", "azimuth_start_deg", "azimuth_end_deg"):
                number(f"animation.{key}")
            if "center" in a:
                vector("animation.center", 3)
        elif a["type"] == "dolly":
            section("animation", ("start", "end"))
            vector("animation.start", 3)
            vector("animation.end", 3)
            if a["start"][:2] == a["end"][:2]:
                fail("animation.end", "dolly needs distinct XY endpoints")
            if "bow" in a:
                number("animation.bow")
        else:
            fail("animation.type", "must be orbit or dolly")
        if "terrain_margin" in a:
            number("animation.terrain_margin", 0)
        if "resolution" in a:
            vector("animation.resolution", 2, positive_integers=True)
        if "samples" in a:
            number("animation.samples", 1, integer=True)
    return cfg


def load_scene(path, require_animation=False):
    with Path(path).open(encoding="utf-8") as stream:
        cfg = json.load(stream)
    return validate_scene(cfg, require_animation=require_animation)
