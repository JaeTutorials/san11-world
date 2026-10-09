"""Render world_types.npy (terrain type per hex, China included) as a PNG, north up.

Usage: python preview_world.py [world_dir] [--out file.png] [--scale 1] [--crop LO0 LO1 HI0 HI1]
       [--cities] [--china-frame]
Image x = lo (east), y = hi (south); odd rows are drawn half a hex lower when scale >= 2.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

PALETTE = {
    0: (126, 190, 80),    # 草地
    1: (196, 172, 112),   # 土
    2: (232, 214, 152),   # 沙地
    3: (104, 150, 118),   # 湿地
    4: (160, 60, 160),    # 毒泉
    5: (36, 104, 40),     # 森
    6: (74, 136, 224),    # 川
    7: (48, 98, 206),     # 河
    8: (28, 48, 150),     # 海
    9: (150, 122, 82),    # 荒地
    10: (226, 202, 64),   # 大道
    11: (186, 124, 60),   # 栈道
    12: (236, 236, 236),  # 桥
    13: (110, 200, 220),  # 浅滩
    14: (172, 172, 166),  # 岸
    15: (96, 78, 64),     # 崖/山
    16: (228, 40, 40),    # 都市
    17: (228, 40, 40),    # 关
    18: (228, 40, 40),    # 港
    19: (204, 170, 64),   # 小径
}


def render(t, scale):
    lut = np.zeros((256, 3), np.uint8)
    for k, c in PALETTE.items():
        lut[k] = c
    img = lut[t.T]                                     # (hi, lo, 3): x = lo, y = hi
    if scale == 1:
        return img
    img = np.repeat(np.repeat(img, scale, 0), scale, 1)
    half = scale // 2
    out = img.copy()
    for lo in range(1, t.shape[0], 2):                 # odd rows half a hex towards +hi
        xs = slice(lo * scale, (lo + 1) * scale)
        out[half:, xs] = img[:-half, xs]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world", nargs="?", default=str(DATA / "world"))
    ap.add_argument("--out")
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--crop", type=int, nargs=4, metavar=("LO0", "LO1", "HI0", "HI1"))
    ap.add_argument("--cities", action="store_true")
    ap.add_argument("--china-frame", action="store_true")
    a = ap.parse_args()
    w = Path(a.world)
    t = np.load(w / "world_types.npy")
    info = json.loads((w / "world_info.json").read_text())
    lo0, lo1, hi0, hi1 = a.crop if a.crop else (0, t.shape[0], 0, t.shape[1])
    s = a.scale
    img = Image.fromarray(render(t[lo0:lo1, hi0:hi1], s))
    d = ImageDraw.Draw(img)
    if a.china_frame:
        cl, ch = info["china_lo"] - lo0, info["china_hi"] - hi0
        d.rectangle([cl * s, ch * s, (cl + 200) * s - 1, (ch + 200) * s - 1], outline=(255, 255, 255))
    if a.cities:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msjh.ttc", max(11, 4 * s + 6))
        except OSError:
            font = ImageFont.load_default()
        pts = [(c["name"], c["lo"], c["hi"]) for c in json.loads((w / "cities_world.json").read_text(encoding="utf-8"))]
        pts += [(c["name"], c["lo"] + info["china_lo"], c["hi"] + info["china_hi"])
                for c in json.loads((DATA / "cities_georef.json").read_text(encoding="utf-8"))]
        for name, lo, hi in pts:
            x, y = (lo - lo0) * s, (hi - hi0) * s
            if 0 <= x < img.width and 0 <= y < img.height:
                r = max(2, s)
                d.rectangle([x - r, y - r, x + r, y + r], fill=(230, 30, 30), outline=(0, 0, 0))
                d.text((x + r + 2, y - r - 2), name, fill=(255, 255, 255), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    out = a.out or str(w / "preview.png")
    img.save(out)
    print(out, img.size)


if __name__ == "__main__":
    main()
