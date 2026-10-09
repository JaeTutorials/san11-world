"""Pick the new cities' sites at Koei's China city density.

Candidates: data/new_cities.json (east, {name, full, region, lat, lon}), data/cities_west.json
(west, [name, full, region, lat, lon, rank]) and data/cities_more.json (same format: northern and eastern
Europe, the steppe, India, Korea, Japan, South-East Asia; added for the 500-city stage). Rank 1 = provincial capital, 2 = major city, 3 = minor
city or tribal centre. Candidates are placed in rank order; a site is skipped when it lies closer than
--spacing hexes (Koei's China: nearest-neighbour median 21, minimum 12.8) to a city already placed,
including Koei's 42. Each site is snapped to nearby passable land whose 7-hex footprint is free.

Usage: python select_cities.py [world_dir] [--spacing 14] [--max N]   (--max: at most N new cities)
Writes <world_dir>/cities_world.json: [{id, name, full, region, lo, hi, rank}], ids from 42.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from make_world import COVER, ROAD, SHORE, hex_ring, lonlat_to_hex
from worldgeo import WorldGeo, WorldSpec

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world", nargs="?", default=str(DATA / "world"))
    ap.add_argument("--spacing", type=float, default=14.0)
    ap.add_argument("--max", type=int, default=0, help="at most this many new cities (0 = all that fit)")
    a = ap.parse_args()
    w = Path(a.world)
    info = json.loads((w / "world_info.json").read_text())
    spec = WorldSpec(rows=info["rows"], cols=info["cols"], lon0=info["lon0"], lat0=info["lat0"],
                     china_lo=info["china_lo"], china_hi=info["china_hi"])
    geo = WorldGeo(spec, DATA / "cities_georef.json")
    t = np.load(w / "world_types.npy")
    R, C = t.shape
    koei = json.loads((DATA / "cities_georef.json").read_text(encoding="utf-8"))
    koei_names = {c["name"] for c in koei}

    cand = {}
    for c in json.loads((DATA / "cities_west.json").read_text(encoding="utf-8")):
        name, full, region, lat, lon, rank = c
        cand[name] = {"name": name, "full": full, "region": region, "lat": lat, "lon": lon, "rank": rank}
    more = DATA / "cities_more.json"
    for c in (json.loads(more.read_text(encoding="utf-8")) if more.exists() else []):
        name, full, region, lat, lon, rank = c
        assert name not in cand, name
        cand[name] = {"name": name, "full": full, "region": region, "lat": lat, "lon": lon, "rank": rank}
    for c in json.loads((DATA / "new_cities.json").read_text(encoding="utf-8")):
        if c["name"] not in cand:
            cand[c["name"]] = {**c, "rank": 1}
    cands = [c for c in cand.values() if c["name"] not in koei_names]
    for c in cands:
        assert len(c["name"].encode("big5")) <= 4, c["name"]
    cands.sort(key=lambda c: c["rank"])          # stable: list order within a rank

    lo, x = lonlat_to_hex(geo, np.array([c["lon"] for c in cands]), np.array([c["lat"] for c in cands]))
    placed = [(k["lo"] + spec.china_lo, k["hi"] + spec.china_hi + 0.5 * ((k["lo"] + spec.china_lo) & 1)) for k in koei]
    passable = np.isin(t, COVER + (SHORE, ROAD))
    land = ~np.isin(t, (6, 7, 8))                 # the city footprint is stamped over mountains too
    taken = np.zeros_like(passable)
    taken[spec.china_lo - 4:spec.china_lo + 204, spec.china_hi - 4:spec.china_hi + 204] = True
    out, skipped = [], []
    for c, l, h in zip(cands, lo, x):
        if a.max and len(out) >= a.max:
            skipped.append((c["name"], "over --max")); continue
        y0 = int(round(l)); x0 = int(round(h - 0.5 * (y0 & 1)))
        if not (6 <= y0 < R - 6 and 6 <= x0 < C - 6):
            skipped.append((c["name"], "outside world")); continue
        best = None
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                y, xx = y0 + dy, x0 + dx
                cells = [(y, xx)] + hex_ring(y, xx)
                if any(not (0 <= p < R and 0 <= q < C) or taken[p, q] for p, q in cells):
                    continue
                nland = sum(land[p, q] for p, q in cells)
                if nland < 5:
                    continue
                score = nland * 10 + sum(passable[p, q] for p, q in cells) * 4 - (dy * dy + dx * dx) ** 0.5 + (20 if passable[y, xx] else 0)
                if best is None or score > best[0]:
                    best = (score, y, xx)
        if best is None:                              # no land nearby
            skipped.append((c["name"], "no land")); continue
        _, y, xx = best
        gx = xx + 0.5 * (y & 1)
        d = min(np.hypot(y - p, gx - q) for p, q in placed) if placed else 99
        if d < a.spacing:
            skipped.append((c["name"], f"{d:.0f} hexes from a city")); continue
        placed.append((y, gx))
        for p, q in [(y, xx)] + hex_ring(y, xx):
            taken[p, q] = True
        out.append({"name": c["name"], "full": c["full"], "region": c["region"], "lo": int(y), "hi": int(xx), "rank": c["rank"]})
    for i, c in enumerate(out):
        c["id"] = 42 + i
    (w / "cities_world.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} cities placed (+42 Koei = {len(out) + 42}), {len(skipped)} skipped")
    by = {}
    for n, why in skipped:
        by.setdefault(why.split(' ')[-1] if 'from' in why else why, []).append(n)
    for k, v in by.items():
        print(f"  skipped ({k}): {' '.join(v)}")


if __name__ == "__main__":
    main()
