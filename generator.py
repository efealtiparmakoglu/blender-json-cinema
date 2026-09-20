"""
JSON Cinematic — JSON tanımından prosedürel sinematik sahne kuran Blender üreteci.

Kullanım:
    blender --background --python generator.py                      # scene.json kullanır
    blender --background --python generator.py -- --scene other.json --preview

--preview: hızlı doğrulama için 320x180 / 32 sample render alır.
"""

import json
import math
import os
import random
import sys

import bpy

# ---------------------------------------------------------------- yardımcılar

def p(obj, attr, val):
    """API sürümleri arasında değişebilen özellikleri sessizce dene."""
    try:
        setattr(obj, attr, val)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  [atlandı] {attr}: {e}")
        return False


def arg_repo():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {"scene": "scene.json", "preview": False}
    i = 0
    while i < len(args):
        if args[i] == "--scene":
            opts["scene"] = args[i + 1]
            i += 2
        elif args[i] == "--preview":
            opts["preview"] = True
            i += 1
        else:
            i += 1
    return opts


def temiz_sahne():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def doku(name, kind):
    t = bpy.data.textures.new(name, type=kind)
    return t


def mat_kur(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    return m, nt


def dugum(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        p(n, k, v) if not isinstance(v, dict) else None
    return n


# ---------------------------------------------------------------- sahne parçaları

def dunya_kur(cfg):
    """Nishita atmosferik gökyüzü + fiziksel güneş."""
    w = bpy.data.worlds.new("Dunya")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()

    sky = nt.nodes.new("ShaderNodeTexSky")
    # Blender 5.x: SINGLE_SCATTERING (fiziksel), 4.x: NISHITA
    if not p(sky, "sky_type", "SINGLE_SCATTERING"):
        p(sky, "sky_type", "NISHITA")
    p(sky, "sun_elevation", math.radians(cfg["world"]["sun_elevation_deg"]))
    p(sky, "sun_rotation", math.radians(cfg["world"]["sun_rotation_deg"]))
    p(sky, "air_density", cfg["world"].get("air_density", 1.2))
    if not p(sky, "aerosol_density", cfg["world"].get("dust_density", 2.0)):
        p(sky, "dust_density", cfg["world"].get("dust_density", 2.0))
    p(sky, "sun_intensity", cfg["world"].get("sun_intensity", 1.0))
    p(sky, "sun_size", math.radians(cfg["world"].get("sun_size_deg", 0.55)))
    p(sky, "sun_disc", not cfg["world"].get("use_sun_lamp", False))

    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = cfg["world"].get("background_strength", 1.0)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    print("  [ok] Nishita gökyüzü")


def arazi_kur(cfg):
    """İki katmanlı displacement ile prosedürel vadi."""
    c = cfg["terrain"]
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=c["subdivisions"],
        y_subdivisions=c["subdivisions"],
        size=c["size"],
    )
    obj = bpy.context.active_object
    obj.name = "Arazi"

    t1 = doku("AraziBuyuk", "CLOUDS")
    p(t1, "noise_scale", c["size"] / 4.5)
    p(t1, "noise_depth", 4)
    m1 = obj.modifiers.new("Taban", "DISPLACE")
    m1.texture = t1
    m1.strength = c["base_height"]

    t2 = doku("AraziInce", "VORONOI")
    p(t2, "noise_scale", 1.4)
    m2 = obj.modifiers.new("Ince", "DISPLACE")
    m2.texture = t2
    m2.strength = c["detail_height"]

    # kenarları yükselt -> vadi hissi
    solid = obj.modifiers.new("Kabuk", "SOLIDIFY")
    solid.thickness = 1.5

    m, nt = mat_kur("Bazalt")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    p(noise.inputs["Scale"], "default_value", 6.0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.012, 0.012, 0.014, 1)
    ramp.color_ramp.elements[1].color = (0.075, 0.070, 0.065, 1)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    p(bsdf.inputs["Roughness"], "default_value", 0.95)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.append(m)
    print("  [ok] Arazi + bazalt materyal")
    return obj


def su_kur(cfg):
    c = cfg["water"]
    bpy.ops.mesh.primitive_plane_add(size=c["size"], location=(0, 0, c["level"]))
    obj = bpy.context.active_object
    obj.name = "Su"

    m, nt = mat_kur("Su")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    p(noise.inputs["Scale"], "default_value", c["ripple_scale"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    mapping = nt.nodes.new("ShaderNodeMapping")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    p(bsdf.inputs["Base Color"], "default_value", (0.004, 0.010, 0.013, 1))
    p(bsdf.inputs["Roughness"], "default_value", 0.10)
    p(bsdf.inputs["Transmission Weight"], "default_value", 1.0) or \
        p(bsdf.inputs["Transmission"], "default_value", 1.0)
    p(bsdf.inputs["IOR"], "default_value", 1.333)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.append(m)
    print("  [ok] Su")
    return obj


def monolitler_kur(cfg):
    c = cfg["monoliths"]
    rng = random.Random(c["seed"])
    made = []
    for i in range(c["count"]):
        h = rng.uniform(c["min_height"], c["max_height"])
        x = rng.uniform(-c["spread"], c["spread"])
        y = rng.uniform(-6, 14)
        z = h / 2 - 1.5
        bpy.ops.mesh.primitive_cube_add(location=(x, y, z))
        obj = bpy.context.active_object
        obj.name = f"Monolit_{i:02d}"
        obj.scale = (rng.uniform(0.9, 1.8), rng.uniform(0.9, 1.8), h / 2)
        obj.rotation_euler[2] = rng.uniform(0, math.pi)

        t = doku(f"MonoTek_{i}", "CLOUDS")
        p(t, "noise_scale", 0.9)
        p(t, "noise_depth", 6)
        md = obj.modifiers.new("Erozyon", "DISPLACE")
        md.texture = t
        md.strength = 0.5
        ms = obj.modifiers.new("Yuzeysel", "SUBSURF")
        ms.levels = 2
        ms.render_levels = 2
        made.append(obj)

    m, nt = mat_kur("Kaya")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    p(noise.inputs["Scale"], "default_value", 3.0)
    p(noise.inputs["Detail"], "default_value", 8.0)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.020, 0.018, 0.017, 1)
    ramp.color_ramp.elements[1].color = (0.115, 0.105, 0.095, 1)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    p(bsdf.inputs["Roughness"], "default_value", 0.65)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    for obj in made:
        obj.data.materials.append(m)
    print(f"  [ok] {len(made)} monolit")
    return made


def gunes_kur(cfg):
    """Güneş lambası: kameradan bakınca tam karenin içinde, arka ışık."""
    w = cfg["world"]
    if not w.get("use_sun_lamp", False):
        return None
    light = bpy.data.lights.new("Gunes", "SUN")
    light.energy = w.get("sun_lamp_strength", 4.0)
    p(light, "angle", math.radians(w.get("sun_lamp_angle_deg", 2.5)))
    p(light, "color", (1.0, 0.82, 0.62))
    obj = bpy.data.objects.new("Gunes", light)
    bpy.context.scene.collection.objects.link(obj)

    t = cfg["camera"]["target"]
    loc = cfg["camera"]["location"]
    # güneşi hedefin arkasına, kameranın tam karşısına koy -> siluet + huzme
    off = w.get("sun_lateral_offset", 0.0)
    vx, vy = t[0] - loc[0], t[1] - loc[1]
    norm = math.hypot(vx, vy)
    px, py = vy / norm, -vx / norm  # görüş eksenine dik sağ yön
    obj.location = (t[0] + (t[0] - loc[0]) * 1.2 + px * off,
                    t[1] + (t[1] - loc[1]) * 1.2 + py * off,
                    max(t[2] + 8.0, 14.0))
    bpy.ops.object.empty_add(location=t)
    aim = bpy.context.active_object
    aim.name = "GunesHedef"
    tr = obj.constraints.new("TRACK_TO")
    tr.target = aim

    # görünür güneş diski (sisin içinden parlar)
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=w.get("sun_glow_radius", 3.0), location=obj.location)
    disk = bpy.context.active_object
    disk.name = "GunesDiski"
    dm, dnt = mat_kur("GunesMat")
    dnt.nodes.clear()
    dout = dnt.nodes.new("ShaderNodeOutputMaterial")
    dem = dnt.nodes.new("ShaderNodeEmission")
    p(dem.inputs["Color"], "default_value", (1.0, 0.75, 0.45, 1))
    dem.inputs["Strength"].default_value = w.get("sun_glow_strength", 40.0)
    dnt.links.new(dem.outputs["Emission"], dout.inputs["Surface"])
    disk.data.materials.append(dm)

    print("  [ok] Güneş lambası + disk")
    return obj


def sis_kur(cfg):
    """Işık huzmelerini yakalayan hacimsel sis küpü."""
    c = cfg["fog"]
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 12), scale=(c["cube_size"] / 2, c["cube_size"] / 2, 30))
    obj = bpy.context.active_object
    obj.name = "Sis"
    obj.display_type = "WIRE"
    obj.hide_render = False

    m, nt = mat_kur("Sis")
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    p(noise.inputs["Scale"], "default_value", 0.55)
    p(noise.inputs["Detail"], "default_value", c.get("detail", 0.5))
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.75
    mult = nt.nodes.new("ShaderNodeMath")
    mult.operation = "MULTIPLY"
    mult.inputs[1].default_value = c["density"]
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1, 1, 0.25)  # dikeyde düz sis
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], mult.inputs[0])
    nt.links.new(mult.outputs["Value"], vol.inputs["Density"])
    p(vol.inputs["Anisotropy"], "default_value", c.get("anisotropy", 0.3))
    p(vol.inputs["Color"], "default_value", (0.85, 0.80, 0.72, 1))
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    obj.data.materials.append(m)
    print("  [ok] Hacimsel sis")
    return obj


def toz_kur(cfg):
    """Güneşte parlayan yüz binlerce toz zerresi."""
    c = cfg["dust"]
    bpy.ops.mesh.primitive_plane_add(size=c["area"], location=(0, 0, 8))
    emitter = bpy.context.active_object
    emitter.name = "TozYayici"
    emitter.hide_render = True

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=c["particle_size"])
    zerre = bpy.context.active_object
    zerre.name = "TozZerresi"

    m, nt = mat_kur("Toz")
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 3.0
    p(em.inputs["Color"], "default_value", (1.0, 0.85, 0.6, 1))
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.55
    nt.links.new(em.outputs["Emission"], mix.inputs[1])
    nt.links.new(transp.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    zerre.data.materials.append(m)

    ps_mod = emitter.modifiers.new("Toz", "PARTICLE_SYSTEM")
    # Blender 5.x: obj.particle_systems[0].settings — eski: modifier.particle_settings
    ps = getattr(ps_mod, "particle_settings", None) or emitter.particle_systems[0].settings
    ps.count = c["count"]
    ps.frame_start = 0
    ps.frame_end = 0
    ps.distribution = "RAND"
    ps.render_type = "OBJECT"
    ps.instance_object = zerre
    p(ps, "particle_size", 1.0)
    p(ps, "lifetime", 10)
    print(f"  [ok] {c['count']:,} toz zerresi")
    return emitter


def kamera_kur(cfg):
    c = cfg["camera"]
    bpy.ops.object.camera_add(location=c["location"])
    cam = bpy.context.active_object
    bpy.ops.object.empty_add(location=c["target"])
    hedef = bpy.context.active_object
    hedef.name = "Odak"
    tr = cam.constraints.new("TRACK_TO")
    tr.target = hedef
    cam.data.lens = c["lens_mm"]
    p(cam.data.dof, "use_dof", True)
    p(cam.data.dof, "focus_object", hedef)
    p(cam.data.dof, "aperture_fstop", c["fstop"])
    p(cam.data, "shift_y", c.get("shift_y", 0.0))
    bpy.context.scene.camera = cam
    print("  [ok] Kamera")
    return cam


def render_kur(cfg, preview=False):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    r = cfg["render"]

    # Metal GPU (Apple Silicon) — olmazsa CPU
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
        print("  [ok] Cycles GPU (Metal)")
    except Exception as e:  # noqa: BLE001
        sc.cycles.device = "CPU"
        print(f"  [uyarı] GPU yok, CPU: {e}")

    if preview:
        sc.render.resolution_x, sc.render.resolution_y = 320, 180
        sc.cycles.samples = 32
    else:
        sc.render.resolution_x, sc.render.resolution_y = r["resolution"]
        sc.cycles.samples = r["samples"]
    p(sc.cycles, "use_adaptive_sampling", True)
    p(sc.cycles, "adaptive_threshold", 0.005 if preview else r.get("adaptive_threshold", 0.005))
    p(sc.cycles, "use_denoising", r.get("denoise", True))
    p(sc.cycles, "denoiser", "OPENIMAGEDENOISE")
    p(sc.cycles, "max_bounces", 12)
    p(sc.cycles, "diffuse_bounces", 6)
    p(sc.cycles, "glossy_bounces", 8)
    p(sc.cycles, "transmission_bounces", 12)
    p(sc.cycles, "volume_bounces", 2)
    p(sc.cycles, "transparent_max_bounces", 16)
    p(sc.cycles, "sample_clamp_indirect", 10.0)

    sc.render.image_settings.file_format = "PNG"
    p(sc.render.image_settings, "color_depth", "16")
    sc.render.filepath = os.path.abspath(r["output"])

    # sinematik renk
    p(sc.view_settings, "view_transform", "AgX")
    p(sc.view_settings, "look", "AgX - Medium High Contrast")
    p(sc.view_settings, "exposure", -0.8)

    print(f"  [ok] Render {sc.render.resolution_x}x{sc.render.resolution_y}, "
          f"{sc.cycles.samples} sample, hedef: {sc.render.filepath}")


# ---------------------------------------------------------------- ana

def main():
    opts = arg_repo()
    with open(opts["scene"], encoding="utf-8") as f:
        cfg = json.load(f)

    print(f"== JSON Cinematic :: {opts['scene']} ==")
    temiz_sahne()
    dunya_kur(cfg)
    arazi_kur(cfg)
    su_kur(cfg)
    monolitler_kur(cfg)
    gunes_kur(cfg)
    sis_kur(cfg)
    toz_kur(cfg)
    kamera_kur(cfg)
    render_kur(cfg, preview=opts["preview"])

    out = os.path.abspath(cfg["render"]["output"])
    if opts["preview"]:
        bpy.context.scene.render.filepath = out.replace(".png", "_preview.png")
    bpy.ops.render.render(write_still=True)
    print(f"== BİTTİ -> {bpy.context.scene.render.filepath} ==")


main()
