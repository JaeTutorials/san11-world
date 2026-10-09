"""World hex grid <-> geography for the San11PK world map.

Hex coordinates follow the game: a position is (lo, hi) where `lo` is the array row (low 16 bits,
grows EAST) and `hi` is the column (high 16 bits, grows SOUTH). Odd rows are shifted half a hex
towards +hi. The world has ROWS x COLS hexes; the stock 200x200 China map is embedded at
(CHINA_LO, CHINA_HI). worldmod.ini: height=ROWS, width=COLS, china_y=CHINA_LO, china_x=CHINA_HI.

Outside China the grid is a plain equirectangular projection at the game's own scale
(about 9 km per hex). Koei's China is close to linear but sheared and locally distorted, so a
smooth displacement field, fitted to the 42 city seats and faded out away from China, bends real
geography so that it meets Koei's coastlines and rivers at the edge of the China block.
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import RBFInterpolator

DLON = 0.0969          # degrees of longitude per row (fitted from the 42 cities)
DLAT = 0.0825          # degrees of latitude per column


@dataclass(frozen=True)
class WorldSpec:
    # Default world: Eurasia + North Africa (15W .. 159E, 77N .. 5.5S)
    rows: int = 1800       # east-west, multiple of 200
    cols: int = 1000       # north-south, multiple of 200
    lon0: float = -15.07   # longitude of row 0
    lat0: float = 77.0     # latitude of column 0
    china_lo: int = 1234   # even, keeps the odd-row hex parity of the China block
    china_hi: int = 436

    def linear_to_lonlat(self, lo, hi):
        lo = np.asarray(lo, dtype=np.float64)
        hi = np.asarray(hi, dtype=np.float64) + 0.5 * (np.asarray(lo, dtype=np.int64) & 1)
        return self.lon0 + DLON * lo, self.lat0 - DLAT * hi

    def lonlat_to_linear(self, lon, lat):
        return (np.asarray(lon) - self.lon0) / DLON, (self.lat0 - np.asarray(lat)) / DLAT


class WorldGeo:
    """Maps world hexes to (lon, lat), bending geography around Koei's China."""

    def __init__(self, spec: WorldSpec, georef: Path, fade_inner=20.0, fade_outer=320.0):
        self.spec = spec
        cities = json.loads(Path(georef).read_text(encoding="utf-8"))
        koei = np.array([[c["lo"] + spec.china_lo, c["hi"] + spec.china_hi] for c in cities], dtype=float)
        lin = np.stack(spec.lonlat_to_linear([c["lon"] for c in cities], [c["lat"] for c in cities]), axis=1)
        # displacement (in hexes) that carries a linear position onto Koei's position
        self.rbf = RBFInterpolator(koei, koei - lin, kernel="thin_plate_spline", degree=1, smoothing=2.0)
        self.residual_rms = float(np.sqrt(((self.rbf(koei) - (koei - lin)) ** 2).sum(1).mean()))
        self.fade_inner, self.fade_outer = fade_inner, fade_outer

    def _fade(self, lo, hi):
        s = self.spec
        dlo = np.maximum(0, np.maximum(s.china_lo - lo, lo - (s.china_lo + 199)))
        dhi = np.maximum(0, np.maximum(s.china_hi - hi, hi - (s.china_hi + 199)))
        d = np.hypot(dlo, dhi)
        t = np.clip((d - self.fade_inner) / (self.fade_outer - self.fade_inner), 0, 1)
        return 1 - t * t * (3 - 2 * t)      # smoothstep 1 -> 0

    def hex_to_lonlat(self, lo, hi, step=8):
        """(lon, lat) for arrays of world hex coordinates. The displacement field is evaluated on a
        coarse lattice (every `step` hexes) and interpolated, which is accurate to well under a hex."""
        lo = np.asarray(lo, dtype=np.float64)
        hi = np.asarray(hi, dtype=np.float64)
        glo = np.arange(lo.min() // step * step, lo.max() + 2 * step, step)
        ghi = np.arange(hi.min() // step * step, hi.max() + 2 * step, step)
        GL, GH = np.meshgrid(glo, ghi, indexing="ij")
        pts = np.stack([GL.ravel(), GH.ravel()], 1)
        disp = self.rbf(pts) * self._fade(GL.ravel(), GH.ravel())[:, None]
        disp = disp.reshape(len(glo), len(ghi), 2)
        # bilinear interpolation of the displacement at the requested hexes
        fi = (lo - glo[0]) / step
        fj = (hi - ghi[0]) / step
        i0 = np.clip(fi.astype(int), 0, len(glo) - 2)
        j0 = np.clip(fj.astype(int), 0, len(ghi) - 2)
        a = (fi - i0)[..., None]
        b = (fj - j0)[..., None]
        d = (disp[i0, j0] * (1 - a) * (1 - b) + disp[i0 + 1, j0] * a * (1 - b)
             + disp[i0, j0 + 1] * (1 - a) * b + disp[i0 + 1, j0 + 1] * a * b)
        return self.spec.linear_to_lonlat(lo - d[..., 0], hi - d[..., 1])


if __name__ == "__main__":
    import sys
    g = WorldGeo(WorldSpec(), Path(sys.argv[1] if len(sys.argv) > 1 else "data/cities_georef.json"))
    print(f"control-point fit residual: {g.residual_rms:.2f} hexes")
    cities = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "data/cities_georef.json").read_text(encoding="utf-8"))
    lo = np.array([c["lo"] + g.spec.china_lo for c in cities])
    hi = np.array([c["hi"] + g.spec.china_hi for c in cities])
    lon, lat = g.hex_to_lonlat(lo, hi)
    err = np.hypot((lon - [c["lon"] for c in cities]) * np.cos(np.radians(lat)), lat - [c["lat"] for c in cities]) * 111
    print(f"city placement error: mean {err.mean():.1f} km, max {err.max():.1f} km")
