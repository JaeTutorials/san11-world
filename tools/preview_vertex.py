"""Hill-shaded render of the global vertex grid (world_height.npy + world_mat.npy), north up.

Usage: python preview_vertex.py [world_dir] --hex LO0 LO1 HI0 HI1 [--step 2] [--out file.png]
Colours come from world_palette.bin (RGB per material, as used by worldmod's terrain fill).
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world", nargs="?", default=str(DATA / "world"))
    ap.add_argument("--hex", type=int, nargs=4, required=True, metavar=("LO0", "LO1", "HI0", "HI1"))
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--out")
    a = ap.parse_args()
    w = Path(a.world)
    h = np.load(w / "world_height.npy", mmap_mode="r")
    m = np.load(w / "world_mat.npy", mmap_mode="r")
    pal_path = w / "world_palette.bin"
    if not pal_path.exists():
        pal_path = DATA / "world" / "world_palette.bin"
    pal = np.frombuffer(pal_path.read_bytes(), np.uint8)
    pal = pal[: len(pal) // 3 * 3].reshape(-1, 3).astype(np.float32)
    lo0, lo1, hi0, hi1 = a.hex
    z = slice(lo0 * 4 + 112, lo1 * 4 + 112, a.step)
    x = slice(hi0 * 4 + 112, hi1 * 4 + 112, a.step)
    hh = h[z, x].astype(np.float32) * 0.5          # world y = height * 0.5, vertex spacing 5
    mm = np.minimum(m[z, x], len(pal) - 1)
    gz, gx = np.gradient(hh, 5.0 * a.step)
    n = np.stack([-gz, np.ones_like(hh), -gx], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    light = np.array([-0.5, 0.75, -0.45])
    light /= np.linalg.norm(light)
    shade = np.clip(n @ light, 0, 1) * 0.75 + 0.35
    col = pal[mm] * 1.6
    col[(mm == 0) & (hh <= 2.0)] = (70, 110, 180)          # material 0 at water level: water
    rgb = col * shade[..., None]
    img = np.clip(rgb, 0, 255).astype(np.uint8).transpose(1, 0, 2)   # x = lo (east), y = hi (south)
    out = a.out or str(w / "vertex_preview.png")
    Image.fromarray(img).save(out)
    print(out, img.shape[1], "x", img.shape[0])


if __name__ == "__main__":
    main()
