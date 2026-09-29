"""
JSON Cinematic — saf matematik kamera yolu modülü.

Blender'a bağımlılığı yok; tests/verify.py kapıları doğrudan bu modülü test eder.
Kural: easing yok, keyframe hilesi yok — sabit açısal/líneer hız, gerçek geometri.
"""

import math


def orbit_points(center, radius, height, az0_deg, az1_deg, n):
    """center etrafında sabit açısal hızla dolanan n nokta.

    az=0 -> +Y (kuzey) tarafında; açı arttıkça saat yönünde döner.
    Kapalı tur için az1 = az0 + 360 ver; ilk ve son nokta çakışır (GIF döngüsü).
    """
    if n < 2:
        raise ValueError("orbit en az 2 nokta ister")
    if radius <= 0:
        raise ValueError("radius > 0 olmalı")
    pts = []
    for i in range(n):
        t = i / (n - 1)
        az = math.radians(az0_deg + (az1_deg - az0_deg) * t)
        x = center[0] + radius * math.sin(az)
        y = center[1] - radius * math.cos(az)
        pts.append((x, y, center[2] + height))
    return pts


def dolly_points(start, end, n, bow=0.0):
    """start->end arası n nokta; bow>0 ise görüşe dik yarım-sinüs yayı ekler.

    bow, kamerayı yolun ortasında kenara iter (düz ray hissi vermeden
    parallax üretir). bow işareti hangi tarafa kaçacağını seçer.
    """
    if n < 2:
        raise ValueError("dolly en az 2 nokta ister")
    dx, dy = end[0] - start[0], end[1] - start[1]
    ln = math.hypot(dx, dy)
    if ln == 0:
        raise ValueError("start ve end çakışık")
    px, py = -dy / ln, dx / ln  # sağ dik
    pts = []
    for i in range(n):
        t = i / (n - 1)
        bulge = bow * math.sin(math.pi * t)
        z = start[2] + (end[2] - start[2]) * t
        pts.append((
            start[0] + dx * t + px * bulge,
            start[1] + dy * t + py * bulge,
            z,
        ))
    return pts


def azimuth_steps(points, center):
    """Art arda açı adımları — sabit açısal hız kapısı buradan kontrol edilir."""
    steps = []
    for (x0, y0, _), (x1, y1, _) in zip(points, points[1:]):
        a0 = math.atan2(x0 - center[0], -(y0 - center[1]))
        a1 = math.atan2(x1 - center[0], -(y1 - center[1]))
        d = a1 - a0
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        steps.append(d)
    return steps


def radii(points, center):
    return [math.hypot(x - center[0], y - center[1]) for x, y, _ in points]


class TerrainMap:
    """Evaluated mesh tepe noktalarından kaba yükseklik haritası.

    grid hücre başına max z tutar; sorgu 3x3 komşuluğa bakar (kamera
    çevresindeki en yüksek arazi parmaklarını kaçırmamak için).
    """

    def __init__(self, verts_xyz, cell=2.0, pad=6.0):
        self.cell = cell
        xs = [v[0] for v in verts_xyz]
        ys = [v[1] for v in verts_xyz]
        self.x0, self.y0 = min(xs) - pad, min(ys) - pad
        self.ncx = int((max(xs) + pad - self.x0) / cell) + 1
        self.ncy = int((max(ys) + pad - self.y0) / cell) + 1
        self.buckets = {}
        for x, y, z in verts_xyz:
            ix = int((x - self.x0) / cell)
            iy = int((y - self.y0) / cell)
            b = self.buckets.get((ix, iy))
            if b is None or z > b:
                self.buckets[(ix, iy)] = z

    def max_near(self, x, y, reach_cells=1):
        ix = int((x - self.x0) / self.cell)
        iy = int((y - self.y0) / self.cell)
        best = None
        for dx in range(-reach_cells, reach_cells + 1):
            for dy in range(-reach_cells, reach_cells + 1):
                b = self.buckets.get((ix + dx, iy + dy))
                if b is not None and (best is None or b > best):
                    best = b
        return best

    def clearance_fix(self, points, margin):
        """Kamerayı arazi + margin üstüne sabitler.

        Dönüş: (düzeltilmiş noktalar, rapor). Rapor: kaç nokta yükseltildi,
        en kritik noktada arazi ve kamera z'si.
        """
        fixed, report = [], {"raised": 0, "worst": None}
        worst_gap = None
        for (x, y, z) in points:
            tmax = self.max_near(x, y)
            if tmax is None:
                fixed.append((x, y, z))
                continue
            floor = tmax + margin
            if z < floor:
                fixed.append((x, y, floor))
                report["raised"] += 1
                gap = floor - z
                if worst_gap is None or gap > worst_gap:
                    worst_gap = gap
                    report["worst"] = {
                        "xy": [round(x, 2), round(y, 2)],
                        "asked_z": round(z, 3),
                        "terrain_max": round(tmax, 3),
                        "final_z": round(floor, 3),
                    }
            else:
                fixed.append((x, y, z))
        return fixed, report
