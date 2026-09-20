# 🎞️ JSON Cinematic — Blender

**EN:** A JSON-driven procedural cinematic scene generator for Blender. Feed it one JSON file, get a fully ray-traced cinematic render out — terrain, water, monoliths, volumetric god-rays, 160k dust particles, physical atmosphere, all built from parameters.

**TR:** Blender için JSON ile çalışan prosedürel sinematik sahne üreteci. Tek bir JSON dosyası veriyorsun; arazi, su, monolitler, hacimsel ışık huzmeleri, 160 bin toz zerresi ve fiziksel atmosferle birlikte tam yol-izlemeli (path tracing) sinematik render alıyorsun.

![Hero render](renders/hero.png)

## ✨ What's inside / Neler var

| Component | Detail |
|---|---|
| 🏔️ Terrain | 448×448 grid (~200k verts), two-layer procedural displacement |
| 🗿 Monoliths | Seeded random placement, erosion displacement, subsurface |
| 🌊 Water | Transmission BSDF, IOR 1.333, animated-style ripple bump |
| 🌫️ Volumetrics | Noise-modulated Principled Volume → god rays, anisotropic scattering |
| ✨ Dust | 160,000 instanced emissive particles |
| ☀️ Atmosphere | Physical single-scattering sky + configurable sun lamp + visible sun disc |
| 🎥 Camera | Track-to rig, depth of field, 24 mm cinematic lens |
| 🖥️ Render | Cycles GPU (Metal), adaptive sampling, OpenImageDenoise, AgX |

## 🖼️ Gallery / Galeri

**EN:** Every world below is *just a different JSON file* — same generator, zero new code. Swap the seed, the sun, the fog color, and you get a different planet.

**TR:** Aşağıdaki her dünya *sadece farklı bir JSON dosyası* — aynı üreteç, sıfır yeni kod. Seed'i, güneşi, sis rengini değiştir; bambaşka bir gezegen çıkar.

### ❄️ Polar Dawn / Kutup Şafağı — [`examples/polar.json`](examples/polar.json)
![Polar dawn render](examples/polar.png)
Sun at 3.5°, icy blue fog and light. Taller, sharper spires frozen in place. — *Güneş 3.5°'te, buz mavisi sis ve ışık. Sivri, devrilmiş gibi duran kuleler.*

### 🔴 Mars Dust / Mars Tozu — [`examples/mars.json`](examples/mars.json)
![Mars render](examples/mars.png)
High orange sun dissolved into butterscotch haze — the sun is a pale glow through the dust, just like real Mars photos. 230k dust grains, 13 scattered monoliths. — *Turuncu güneş karamel rengi tozda silik bir parıltı; 230 bin toz zerresi, 13 dağınık kule.*

### 🌙 Moonless Night / Ay Isığı Gece — [`examples/night.json`](examples/night.json)
![Night render](examples/night.png)
A cold moon glowing faintly behind the spires of a black desert; only rim light survives. — *Kara çölün sivri kulelerinin ardında soluk bir ay; sadece kenar ışığı hayatta kalıyor.*

### 🔥 Inferno / Cehennem — [`examples/inferno.json`](examples/inferno.json)
![Inferno render](examples/inferno.png)
A blood-red sun bleeding through ember fog; 300k embers drift over a scorched valley. — *Kan kırmızısı güneş kor sisinden kanıyor; yanmış vadide 300 bin kor süzülüyor.*

### 💚 Emerald / Zümrüt Gezegen — [`examples/emerald.json`](examples/emerald.json)
![Emerald render](examples/emerald.png)
Teal sunlight and jade fog — nothing on this planet is from Earth. — *Turkuaz güneş ışığı ve yeşim sis — bu gezegenden hiçbir şey Dünya'dan değil.*

### 🗿 Colossus / Koloslar — [`examples/colossus.json`](examples/colossus.json)
![Colossus render](examples/colossus.png)
Giants against a 20 mm lens from trench level — scale is the story. — *Siper hizasından 20 mm lensle devler — hikâye ölçeğin kendisi.*

### ⚪ Whiteout / Sis Sınırı — [`examples/whiteout.json`](examples/whiteout.json)
![Whiteout render](examples/whiteout.png)
The volumetric dial turned to maximum: the mid-ground dissolves into haze and the sun becomes a pale smear. Heaviest fog this generator can carry. — *Hacimsel sis düğmesi sonuna kadar açıldı: orta plan sise çözülüyor, güneş soluk bir lekeye dönüşüyor.*

Reproduce any of them / Hangisini istersen yeniden üret:

```bash
blender --background --python generator.py -- --scene examples/polar.json
```

## 🚀 Usage / Kullanım


```bash
# default scene
blender --background --python generator.py

# your own scene
blender --background --python generator.py -- --scene my_scene.json

# fast 320p validation pass
blender --background --python generator.py -- --preview
```

Requires **Blender 4.x / 5.x** (tested on 5.2 LTS, Apple Silicon / Metal).
No add-ons, no dependencies — just Python + Blender.

## 🎛️ Tune everything from `scene.json`

```jsonc
{
  "render":  { "samples": 1024, "resolution": [1920, 1080], "adaptive_threshold": 0.005 },
  "world":   { "sun_elevation_deg": 8.0, "sun_lamp_strength": 6.0, "background_strength": 0.25 },
  "terrain": { "subdivisions": 448, "base_height": 7.5, "seed": 7 },
  "monoliths": { "count": 9, "min_height": 9, "max_height": 17, "seed": 21 },
  "fog":     { "density": 0.0035, "anisotropy": 0.45 },
  "dust":    { "count": 160000 },
  "camera":  { "lens_mm": 24, "fstop": 2.0 }
}
```

Every rock, ray and grain of dust is a parameter. Change the seed → whole new world.

## 🧪 Why / Neden

**TR:** "Prompt → render" hattının en sade hâli: **parametreler = prompt, sahne = cevap.** Tüm geometri ve materyaller prosedürel; hiçbir doku dosyası, hiçbir harici varlık yok. Kompozisyon denemeleri için `--preview` ile saniyeler içinde düşük çözünürlükte önizleme alın, memnun kalınca aynı JSON ile tam kalitede render basın.

## 📄 License

MIT
