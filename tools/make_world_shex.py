"""Generate world_shex.bin: the base hex terrain of the whole world for worldmod.

File layout: b"WSHX", u32 W, u32 H, then W*H SHEX0008 records (11 bytes each, row-major y*W+x).
worldmod overlays the original 200x200 China block at (china_x, china_y) at load time, so the
China area of this file is ignored.

Modes
  margins  hexes that fall on the stock 1025x1025 terrain outside China (the 28-hex border)
           get terrain derived from the K3ST stage data; everything else is impassable mountain.
           This is a test world for validating the enlarged logic grid.

Usage: python make_world_shex.py <out.bin> W H china_x china_y [--mode margins] [--res san11pkres.bin]
"""
import argparse
import struct
from pathlib import Path

import numpy as np

REC = 11
CHINA = 200
TERRAIN_ORIGIN = 28                 # China hex (0,0) sits on terrain cell 28 (vertex 112)
GRASS, SEA, MOUNTAIN = 0, 8, 15
UNOWNED_AREA = 90                   # area ids >= 87 are not bases; 90 is the common mountain area


def read_link(res: Path, index: int) -> bytes:
    with res.open("rb") as f:
        head = f.read(16)
        count = struct.unpack_from("<I", head, 4)[0]
        if head[:4] != b"LINK" or index >= count:
            raise SystemExit("bad resource pack")
        f.seek(16 + 8 * index)
        off, size = struct.unpack("<II", f.read(8))
        f.seek(off)
        return f.read(size)


def record(terrain: int) -> bytes:
    r = bytearray(REC)
    r[0] = terrain
    struct.pack_into("<H", r, 1, UNOWNED_AREA)
    r[4] = 4 if terrain == SEA else 6
    r[9] = 15
    return bytes(r)


def classify_margins(res: Path) -> np.ndarray:
    """Terrain type for each of the 256x256 terrain cells, from vertex material/height."""
    k3st = read_link(res, 0x12B9)
    if k3st[:4] != b"K3ST":
        raise SystemExit("unexpected stage resource")
    v = np.frombuffer(k3st[8:8 + 1025 * 1025 * 8], dtype=np.uint8).reshape(1025, 1025, 8)
    cells = np.full((256, 256), MOUNTAIN, dtype=np.uint8)
    for cy in range(256):
        for cx in range(256):
            block = v[cy * 4:cy * 4 + 5, cx * 4:cx * 4 + 5]
            water = (block[:, :, 7] == 0).mean()
            h = block[:, :, 0].astype(int)
            if water > 0.5:
                cells[cy, cx] = SEA
            elif h.max() - h.min() < 24 and h.mean() < 140:
                cells[cy, cx] = GRASS
    return cells


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("W", type=int)
    ap.add_argument("H", type=int)
    ap.add_argument("china_x", type=int)
    ap.add_argument("china_y", type=int)
    ap.add_argument("--mode", default="margins", choices=["margins"])
    ap.add_argument("--res", type=Path, default=Path("Media/san11pkres.bin"))
    a = ap.parse_args()
    if a.W % 200 or a.H % 200 or a.china_y % 2:
        raise SystemExit("W and H must be multiples of 200 and china_y must be even")

    types = np.full((a.H, a.W), MOUNTAIN, dtype=np.uint8)
    cells = classify_margins(a.res)
    for cy in range(256):
        for cx in range(256):
            # odd hex rows are shifted half a hex east on the terrain; ignore that sub-cell offset here
            hy = cy - TERRAIN_ORIGIN + a.china_y
            hx = cx - TERRAIN_ORIGIN + a.china_x
            if 0 <= hy < a.H and 0 <= hx < a.W:
                types[hy, hx] = cells[cy, cx]

    lut = {t: record(t) for t in np.unique(types)}
    with a.out.open("wb") as f:
        f.write(b"WSHX" + struct.pack("<II", a.W, a.H))
        for row in types:
            f.write(b"".join(lut[t] for t in row))
    land = (types == GRASS).sum()
    sea = (types == SEA).sum()
    print(f"wrote {a.out}: {a.W}x{a.H}, China at ({a.china_x},{a.china_y}), "
          f"{land} grass / {sea} sea hexes outside the mountain fill")


if __name__ == "__main__":
    main()
