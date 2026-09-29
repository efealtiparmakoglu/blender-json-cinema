"""
JSON Cinematic — doğrulama kapıları.

    python3 tests/verify.py

Blender gerekmez: cam_path saf matematiktir, şema kapıları sadece JSON okur.
Bir kapı kırmızıysa render açılmaz; sayısal teşhis basılır.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cam_path  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GATES = []


def gate(name):
    def deco(fn):
        GATES.append((name, fn))
        return fn
    return deco


REQUIRED = {
    "render": ["resolution", "samples", "output"],
    "world": ["sun_elevation_deg", "sun_rotation_deg"],
    "terrain": ["size", "subdivisions", "base_height", "detail_height"],
    "water": ["level", "size"],
    "monoliths": ["count", "min_height", "max_height", "spread", "seed"],
    "fog": ["cube_size", "density"],
    "dust": ["count", "area", "particle_size"],
    "camera": ["location", "target", "lens_mm", "fstop"],
}

ANIM_REQUIRED = {"frames", "fps", "type", "look_at", "output_dir"}


@gate("G1 şema: tüm sahne JSON'ları zorunlu anahtarları taşıyor")
def g1_schema():
    scenes = [os.path.join(REPO, "scene.json")]
    ex = os.path.join(REPO, "examples")
    scenes += [os.path.join(ex, f) for f in sorted(os.listdir(ex)) if f.endswith(".json")]
    errs = []
    for path in scenes:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        rel = os.path.relpath(path, REPO)
        for sect, keys in REQUIRED.items():
            if sect not in cfg:
                errs.append(f"{rel}: bölüm yok: {sect}")
                continue
            for k in keys:
                if k not in cfg[sect]:
                    errs.append(f"{rel}: {sect}.{k} yok")
        if "animation" in cfg:
            missing = ANIM_REQUIRED - set(cfg["animation"])
            if missing:
                errs.append(f"{rel}: animation eksik: {sorted(missing)}")
    return errs


@gate("G2 orbit: sabit açısal hız + sabit yarıçap")
def g2_orbit():
    pts = cam_path.orbit_points((0, 4, 0), 26.0, 7.0, 0.0, 360.0, 48)
    errs = []
    steps = cam_path.azimuth_steps(pts, (0, 4, 0))
    want = 2 * math.pi / 47
    for i, s in enumerate(steps):
        if abs(s - want) > 1e-9:
            errs.append(f"adım {i}: {s:.9f} != {want:.9f}")
    for i, r in enumerate(cam_path.radii(pts, (0, 4, 0))):
        if abs(r - 26.0) > 1e-9:
            errs.append(f"yarıçap {i}: {r:.9f} != 26")
    # kapalı turda son nokta ilkine dönmeli
    if math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) > 1e-9:
        errs.append("360° turda son nokta ilkine dönmedi")
    return errs


@gate("G3 dolly: yay simetrisi + monoton ilerleme")
def g3_dolly():
    pts = cam_path.dolly_points((-18, -20, 6), (4, 6, 6), 40, bow=3.0)
    errs = []
    # orta nokta yayın tepesinde; kenarlar yaysız
    mid = pts[len(pts) // 2]
    dx, dy = 4 - (-18), 6 - (-20)
    ln = math.hypot(dx, dy)
    px, py = -dy / ln, dx / ln
    t_mid = (len(pts) // 2) / (len(pts) - 1)
    base_x = -18 + dx * t_mid
    base_y = -20 + dy * t_mid
    off = (mid[0] - base_x) * px + (mid[1] - base_y) * py
    want = 3.0 * math.sin(math.pi * t_mid)
    if abs(off - want) > 1e-9:
        errs.append(f"orta yay ofseti {off:.6f} != {want:.6f}")
    first = pts[0]
    off0 = (first[0] - (-18)) * px + (first[1] - (-20)) * py
    if abs(off0) > 1e-9:
        errs.append(f"başlangıçta yay olmamalı: {off0:.6f}")
    # ilerleme monoton (yay bow olsa da hat boyunca geri dönmemeli)
    prev = -1.0
    for p in pts:
        t = ((p[0] - (-18)) * dx + (p[1] - (-20)) * dy) / (ln * ln)
        if t < prev - 1e-9:
            errs.append("yol boyunca geri dönüş var")
            break
        prev = t
    return errs


@gate("G4 clearance: kamera arazi + margin altına inmiyor")
def g4_clearance():
    # sentetik arazi: merkezde 12 m'lik tepe
    def terrain(x, y):
        return 12.0 * math.exp(-(x * x + y * y) / 50.0)

    verts = [(x, y, terrain(x, y))
             for x in [i * 1.0 for i in range(-40, 41)]
             for y in [i * 1.0 for i in range(-40, 41)]]
    tm = cam_path.TerrainMap(verts, cell=2.0)
    pts = cam_path.orbit_points((0, 0, 0), 8.0, 1.0, 0, 360, 48)  # bilerek tepeye çarpar
    fixed, rep = tm.clearance_fix(pts, margin=2.5)
    errs = []
    if rep["raised"] == 0:
        errs.append("tepeye çarpan yol yükseltilmedi — kapı ölü")
    for (x, y, z) in fixed:
        tmax = tm.max_near(x, y)
        if tmax is not None and z < tmax + 2.5 - 1e-6:
            errs.append(f"({x:.1f},{y:.1f}) z={z:.2f} < arazi {tmax:.2f}+2.5")
    if rep["worst"] is None or rep["worst"]["final_z"] < rep["worst"]["terrain_max"] + 2.5:
        errs.append("worst raporu tutarsız")
    return errs


@gate("G5 anim şeması: scene.json animasyon değerleri makul")
def g5_anim_config():
    with open(os.path.join(REPO, "scene.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    if "animation" not in cfg:
        return ["scene.json'da animation yok — hareket fazı bağlı değil"]
    a = cfg["animation"]
    errs = []
    if not (12 <= a["frames"] <= 240):
        errs.append(f"frames={a['frames']} 12-240 dışında")
    if not (8 <= a["fps"] <= 30):
        errs.append(f"fps={a['fps']} 8-30 dışında")
    if a["type"] not in ("orbit", "dolly"):
        errs.append(f"type={a['type']} bilinmiyor")
    if a.get("radius", 1) <= 0:
        errs.append("radius > 0 olmalı")
    if a.get("terrain_margin", 0) < 1.0:
        errs.append("terrain_margin >= 1.0 olmalı")
    if os.path.isabs(a["output_dir"]) or ".." in a["output_dir"].split(os.sep):
        errs.append("output_dir repo içi göreli olmalı")
    return errs


def main():
    failures = 0
    for name, fn in GATES:
        errs = fn()
        if errs:
            failures += 1
            print(f"❌ {name}")
            for e in errs[:10]:
                print(f"   {e}")
        else:
            print(f"✅ {name}")
    print(f"\n{'KAPILAR KIRIK' if failures else 'TÜM KAPILAR YEŞİL'} ({failures} kırık)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
