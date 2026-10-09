"""Lay roads along every link between neighbouring cities, so armies can actually march between them.

    python tools/connect_cities.py [world_dir] --links <data_dir>/bases_cities.json

In Koei's map rivers (川 6), cliffs (崖 15) and banks (岸 14) stop land units; armies cross them only on
main roads (主徑 10), plank roads (棧道 11) and ferries (渡所 12). The generated world has Koei's share of
those obstacles, so a city link from gen_bases.py does not mean there is a way to walk. For each link
(new city <-> new city, or new city <-> Koei city through the nearest gateway outside China) this tool
finds the cheapest route over the current terrain, preferring existing roads, and turns it into road:
cliffs become plank roads, streams and rivers ferries, banks and other land main roads. Sea is crossed
by sailing (left as it is) only when no land route exists nearby, and the bank where the route lands is opened. China's block is never changed.
Then it reports which cities are still unreachable on foot and by any route the game's A* accepts.

Writes world_dir/world_types.npy (the previous one is kept once as world_types.before_roads.npy).
Afterwards rebuild: make_world.py --types-from, gen_bases.py, convert_scen.py (or the editor's Build).
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

from make_world import (BRIDGE, CITY, FORD, MOUNTAIN, PATH, PLANK, RIVER, ROAD, SEA, SHORE, STREAM, COVER,
                        china_box, china_gateways, dist_to_china, hex_ring)
from worldgeo import WorldSpec

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

# route cost per hex entered (existing roads cheapest); inf = never
COST = np.full(256, np.inf, np.float32)
for k, c in {0: 1.0, 1: 1.0, 2: 1.4, 3: 2.2, 4: 3.0, 5: 1.6, 9: 1.3, SHORE: 1.2, MOUNTAIN: 7.0, STREAM: 6.0,
             RIVER: 20.0, SEA: 5.0, ROAD: 0.35, PLANK: 0.5, BRIDGE: 0.5, FORD: 1.5, PATH: 1.0, CITY: 1.0,
             17: 1.0, 18: 1.0}.items():
    COST[k] = c
# the game's A* (0x567520) may enter these terrain types (table 0x8a5df8); 7/8 by boat
ASTAR = np.zeros(256, bool); ASTAR[[0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 16, 17, 18]] = True


def graph(cost):
    """hex grid graph (lo = row, odd rows half a hex further along hi); edge weight = cost of the target"""
    R, C = cost.shape
    idx = np.arange(R * C).reshape(R, C)
    a_list, b_list = [], []
    a_list.append(idx[:, :-1].ravel()); b_list.append(idx[:, 1:].ravel())          # same row
    a_list.append(idx[:-1].ravel()); b_list.append(idx[1:].ravel())                 # next row, same hi
    rows = np.arange(R - 1)
    ev, od = rows[rows % 2 == 0], rows[rows % 2 == 1]
    a_list.append(idx[ev, 1:].ravel()); b_list.append(idx[ev + 1, :-1].ravel())     # even row -> next row hi-1
    a_list.append(idx[od, :-1].ravel()); b_list.append(idx[od + 1, 1:].ravel())     # odd row -> next row hi+1
    a = np.concatenate(a_list); b = np.concatenate(b_list)
    w = cost.ravel()
    src = np.concatenate([a, b]); dst = np.concatenate([b, a])
    ok = np.isfinite(w[dst]) & np.isfinite(w[src])
    return csr_matrix((w[dst][ok], (src[ok], dst[ok])), shape=(R * C, R * C))


def components(mask):
    R, C = mask.shape
    g = graph(np.where(mask, 1.0, np.inf).astype(np.float32))
    n, lab = connected_components(g, directed=False)
    lab = lab.reshape(R, C)
    lab[~mask] = -1
    return lab


def route(t, cost_fn, a, b, margins=(60, 160, 400)):
    """cheapest path a -> b (lo, hi) inside a window around both; returns [(lo, hi), ...] or None"""
    R, C = t.shape
    for m in margins:
        y0, y1 = max(0, min(a[0], b[0]) - m), min(R, max(a[0], b[0]) + m + 1)
        x0, x1 = max(0, min(a[1], b[1]) - m), min(C, max(a[1], b[1]) + m + 1)
        y0 -= y0 % 2                                       # keep row parity
        cost = cost_fn(y0, y1, x0, x1)
        w = x1 - x0
        g = graph(cost)
        s = (a[0] - y0) * w + (a[1] - x0); e = (b[0] - y0) * w + (b[1] - x0)
        dist, pred = dijkstra(g, indices=s, return_predecessors=True)
        if np.isfinite(dist[e]):
            path, v = [], e
            while v != s and v >= 0:
                path.append((y0 + v // w, x0 + v % w)); v = pred[v]
            return path[::-1]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("world", nargs="?", default=str(DATA / "world"))
    ap.add_argument("--links", required=True, help="bases_cities.json written by gen_bases.py (city links)")
    a = ap.parse_args()
    w = Path(a.world)
    info = json.loads((w / "world_info.json").read_text())
    spec = WorldSpec(rows=info["rows"], cols=info["cols"], lon0=info["lon0"], lat0=info["lat0"],
                     china_lo=info["china_lo"], china_hi=info["china_hi"])
    t = np.load(w / "world_types.npy").astype(np.uint8)
    R, C = t.shape
    clo, chi = spec.china_lo, spec.china_hi
    links = json.loads(Path(a.links).read_text(encoding="utf-8"))
    ncity = links["C"]
    koei = json.loads((DATA / "cities_georef.json").read_text(encoding="utf-8"))
    pos = {k["id"]: (k["lo"] + clo, k["hi"] + chi) for k in koei}
    name = {k["id"]: k["name"] for k in koei}
    for c in links["new"]:
        pos[c["id"]] = (c["lo"], c["hi"]); name[c["id"]] = c["name"]
    footprint = np.zeros((R, C), bool)
    for cid, (y, x) in pos.items():
        if cid >= 42:
            for p, q in [(y, x)] + hex_ring(y, x):
                footprint[p, q] = True
    in_china = np.zeros((R, C), bool)
    s_lo, s_hi = china_box(spec)
    in_china[s_lo, s_hi] = True
    border = dist_to_china(spec, R, C) <= 3
    gates = china_gateways(t, spec, koei)                  # [(koei name, lo, hi)] just outside the block
    gate_of = {}
    for k in koei:
        ky, kx = pos[k["id"]]
        best = min(gates, key=lambda g: (g[1] - ky) ** 2 + (g[2] - kx) ** 2)
        gate_of[k["id"]] = (best[1], best[2])

    def cost_fn(y0, y1, x0, x1, sea=True):
        tt = t[y0:y1, x0:x1]
        c = COST[tt].copy()
        if not sea:
            c[tt == SEA] = np.inf                          # first try to walk
        c[border[y0:y1, x0:x1]] *= 4
        c[in_china[y0:y1, x0:x1]] = np.inf
        c[footprint[y0:y1, x0:x1]] = 1.0
        return c

    edges = set()
    for c in links["new"]:
        for n in c["neighbours"]:
            if n >= ncity:
                continue                                   # gates and ports
            edges.add((min(c["id"], n), max(c["id"], n)))
    def ends(e):
        i, j = e
        pi = gate_of[i] if i < 42 else pos[i]
        pj = gate_of[j] if j < 42 else pos[j]
        return pi, pj
    order = sorted(edges, key=lambda e: np.hypot(*(np.subtract(*ends(e)))))
    if not (w / "world_types.before_roads.npy").exists():
        shutil.copy2(w / "world_types.npy", w / "world_types.before_roads.npy")
    made = {ROAD: 0, PLANK: 0, BRIDGE: 0}
    failed = []
    for e in order:
        pa, pb = ends(e)
        path = route(t, lambda *r: cost_fn(*r, sea=False), pa, pb, margins=(60, 160))     # a land route if there is one nearby
        if path is None:
            path = route(t, cost_fn, pa, pb)                                               # islands: sail
        if path is None:
            failed.append(e); continue
        for (y, x) in path:
            if footprint[y, x] or in_china[y, x]:
                continue
            k = t[y, x]
            if k == MOUNTAIN:
                t[y, x] = PLANK; made[PLANK] += 1
            elif k in (STREAM, RIVER):
                t[y, x] = BRIDGE; made[BRIDGE] += 1
            elif k in COVER or k in (SHORE, FORD, PATH, 4):
                t[y, x] = ROAD; made[ROAD] += 1
            # SEA: sailed across, left as it is
    # cities on the main landmass that are still cut off on foot (their links all cross water): one more
    # land-only road to the nearest city that is reachable on foot. Islands keep their sea routes.
    def foot_labels():
        tt = t.copy(); tt[footprint] = CITY
        return components(ASTAR[tt] & ~np.isin(tt, (RIVER, SEA)))
    land = components(t != SEA)                                    # landmasses (rivers, cliffs can be bridged)
    main_land = land[pos[1]]
    for _ in range(3):
        lab = foot_labels(); main_c = lab[pos[1]]
        cut = [cid for cid in sorted(pos) if cid < ncity and cid >= 42 and lab[pos[cid]] != main_c and land[pos[cid]] == main_land]
        if not cut:
            break
        reach = [cid for cid in sorted(pos) if cid < ncity and lab[pos[cid]] == main_c]
        for cid in cut:
            a_ = pos[cid]
            near = sorted(reach, key=lambda k: (pos[k][0] - a_[0]) ** 2 + (pos[k][1] - a_[1]) ** 2)[:4]
            for k in near:
                b_ = gate_of[k] if k < 42 else pos[k]
                path = route(t, lambda *r: cost_fn(*r, sea=False), a_, b_, margins=(80, 200, 500))
                if path is None:
                    continue
                for (y, x) in path:
                    if footprint[y, x] or in_china[y, x]:
                        continue
                    kk = t[y, x]
                    if kk == MOUNTAIN: t[y, x] = PLANK; made[PLANK] += 1
                    elif kk in (STREAM, RIVER): t[y, x] = BRIDGE; made[BRIDGE] += 1
                    elif kk in COVER or kk in (SHORE, FORD, PATH, 4): t[y, x] = ROAD; made[ROAD] += 1
                print(f"  land road for {name[cid]} -> {name[k]}")
                break
    np.save(w / "world_types.npy", t)
    print(f"{len(edges)} links routed ({len(failed)} without any route); new road hexes: main road {made[ROAD]}, "
          f"plank road {made[PLANK]}, ferry {made[BRIDGE]}")
    for i, j in failed:
        print(f"  no route: {name[i]} - {name[j]}")
    # reachability as the game sees it (footprints are city terrain in the game)
    tt = t.copy(); tt[footprint] = CITY
    for label, mask in (("on foot", ASTAR[tt] & ~np.isin(tt, (RIVER, SEA))), ("by any route the game's A* accepts", ASTAR[tt])):
        lab = components(mask)
        main_c = lab[pos[1]]
        cut = [name[cid] for cid in sorted(pos) if cid < ncity and lab[pos[cid]] != main_c]
        print(f"cities unreachable from 北平 {label}: {len(cut)}" + (": " + " ".join(cut) if cut else ""))


if __name__ == "__main__":
    main()
