"""San11 world map / city editor: a local web page plus this small server.

    python tools/editor/server.py [--world data/world] [--game C:/San11PK] [--out world_custom] [--port 8611]

Opens http://127.0.0.1:8611/ in the browser. The page edits the world directory written by
tools/make_world.py (world_types.npy = hex terrain, cities_world.json = the new cities, ids 42..);
the first save keeps the previous files as *.orig. "Build" runs the same tools as the manual workflow:

  1. make_world.py --types-from   (only when the terrain changed and "rebuild 3D" is ticked)
     otherwise the hex records in world_shex.bin are patched from the edited terrain in place
  2. gen_bases.py --cities C      territories, adjacency, the per-base tables, city models
  3. convert_scen.py              scenarios in the C-city format
  4. copy the 3D terrain files, and point worldmod.ini [san11pk_world] at the new data directory

Only standard Python plus numpy/scipy/pyshp (the same as the other tools) is needed.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
PROJ = TOOLS.parent
DATA = PROJ / "data"

TERRAIN = [  # id, name, colour (the same palette as preview_world.py)
    (0, "草地", (126, 190, 80)), (1, "土", (196, 172, 112)), (2, "沙地", (232, 214, 152)),
    (3, "湿地", (104, 150, 118)), (4, "毒泉", (160, 60, 160)), (5, "森", (36, 104, 40)),
    (6, "川", (74, 136, 224)), (7, "河", (48, 98, 206)), (8, "海", (28, 48, 150)),
    (9, "荒地", (150, 122, 82)), (10, "大道", (226, 202, 64)), (11, "栈道", (186, 124, 60)),
    (12, "桥", (236, 236, 236)), (13, "浅滩", (110, 200, 220)), (14, "岸", (172, 172, 166)),
    (15, "山", (96, 78, 64)), (16, "都市", (228, 40, 40)), (17, "关", (200, 60, 60)),
    (18, "港", (200, 80, 80)), (19, "小径", (204, 170, 64)),
]
SEA, RIVER = 8, 7
MAX_CITIES = 1000


class Project:
    def __init__(self, world, game, out, section="san11pk_world"):
        self.world, self.game, self.out, self.section = Path(world), Path(game), out, section
        self.info = json.loads((self.world / "world_info.json").read_text())
        self.R, self.C = self.info["rows"], self.info["cols"]
        self.lock = threading.Lock()
        self.log, self.running = [], False

    # ---- data
    def meta(self):
        koei = json.loads((DATA / "cities_georef.json").read_text(encoding="utf-8"))
        clo, chi = self.info["china_lo"], self.info["china_hi"]
        cities = json.loads((self.world / "cities_world.json").read_text(encoding="utf-8"))
        ini = self.read_ini()
        return {
            "rows": self.R, "cols": self.C, "china_lo": clo, "china_hi": chi,
            "terrain": [{"id": i, "name": n, "color": c} for i, n, c in TERRAIN],
            "koei": [{"id": c["id"], "name": c["name"], "lo": c["lo"] + clo, "hi": c["hi"] + chi} for c in koei],
            "cities": cities, "max_cities": MAX_CITIES, "world": str(self.world), "game": str(self.game),
            "out": self.out, "ini": ini,
            "built": (self.game / self.out / "bases_cities.json").exists(),
        }

    def terrain(self):
        return np.ascontiguousarray(np.load(self.world / "world_types.npy").astype(np.uint8)).tobytes()

    def areas(self):
        """u16 area id per hex from the last build (world_shex.bin bytes 1-2), or None"""
        f = self.game / self.out / "world_shex.bin"
        if not f.exists():
            return None
        raw = np.fromfile(f, np.uint8, offset=12).reshape(self.R, self.C, 11)
        return np.ascontiguousarray(raw[..., 1].astype(np.uint16) | (raw[..., 2].astype(np.uint16) << 8)).tobytes()

    def links(self):
        f = self.game / self.out / "bases_cities.json"
        if not f.exists():
            return {}
        d = json.loads(f.read_text(encoding="utf-8"))
        return {"C": d["C"], "new": [{"id": c["id"], "neighbours": c["neighbours"]} for c in d["new"]],
                "koei": d.get("koei_neighbours", {})}

    def backup(self, name):
        f = self.world / name
        o = self.world / (name + ".orig")
        if f.exists() and not o.exists():
            shutil.copy2(f, o)

    def save_terrain(self, body):
        t = np.frombuffer(body, np.uint8)
        if t.size != self.R * self.C or t.max() > 19:
            raise ValueError("bad terrain size or value")
        self.backup("world_types.npy")
        t = t.reshape(self.R, self.C)
        old = np.load(self.world / "world_types.npy")
        np.save(self.world / "world_types.npy", t)
        # san11kit.py world lays the roads again on the terrain without roads (world_types.before_roads.npy):
        # carry the painted hexes over to it, so they survive the next build
        pre = self.world / "world_types.before_roads.npy"
        if pre.exists():
            p = np.load(pre)
            m = t != old
            p[m] = t[m]
            np.save(pre, p)
        (self.world / ".terrain_changed").write_text(time.ctime())

    def save_cities(self, cities):
        names = set()
        for i, c in enumerate(cities):
            c["id"] = 42 + i
            if not c.get("name") or len(c["name"].encode("big5", "replace")) > 4:
                raise ValueError(f"city {i}: the name must be 1-2 characters (it shows in a 4-byte field)")
            if c["name"] in names:
                raise ValueError(f"city name {c['name']} is used twice")
            names.add(c["name"])
            c["lo"], c["hi"] = int(c["lo"]), int(c["hi"])
            c.setdefault("full", c["name"]); c.setdefault("region", ""); c.setdefault("rank", 3)
        self.backup("cities_world.json")
        (self.world / "cities_world.json").write_text(json.dumps(cities, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- worldmod.ini
    def read_ini(self):
        f = self.game / "worldmod.ini"
        out, sec = {}, None
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    sec = line[1:-1]; out[sec] = {}
                elif "=" in line and sec and not line.startswith(";"):
                    k, v = line.split("=", 1); out[sec][k.strip()] = v.strip()
        return out

    def set_ini(self, section, values):
        f = self.game / "worldmod.ini"
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines() if f.exists() else []
        out, sec, done = [], None, set()
        for line in lines:
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                if sec == section:
                    out += [f"{k}={v}" for k, v in values.items() if k not in done]
                sec = s[1:-1]
            elif sec == section and "=" in s and not s.startswith(";") and s.split("=", 1)[0].strip() in values:
                k = s.split("=", 1)[0].strip()
                out.append(f"{k}={values[k]}"); done.add(k); continue
            out.append(line)
        if sec == section:
            out += [f"{k}={v}" for k, v in values.items() if k not in done]
        elif section not in self.read_ini():
            out += ["", f"[{section}]"] + [f"{k}={v}" for k, v in values.items()]
        bak = f.with_name("worldmod.ini.before-editor")       # the configuration before the first deploy
        if f.exists() and not bak.exists():
            shutil.copy2(f, bak)
        f.write_text("\n".join(out) + "\n", encoding="utf-8")

    # ---- build
    def say(self, msg):
        with self.lock:
            self.log.append(msg)
        print(msg, flush=True)

    def run(self, args):
        self.say("$ " + " ".join(str(a) for a in args))
        p = subprocess.Popen([sys.executable, *map(str, args)], cwd=TOOLS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        for line in p.stdout:
            self.say("  " + line.rstrip())
            m = re.search(r"unreachable city pairs (\d+)", line)
            if m and int(m.group(1)):
                self.say(f"  警告：有 {m.group(1)} 对城市之间没有路可走（城市链没有连到中国）。"
                         "把连接用的城市排到列表前面，或者加大城市总数 C。")
        if p.wait():
            raise RuntimeError(f"{Path(args[0]).name} failed (exit {p.returncode})")

    def patch_shex(self):
        """write the edited terrain into world_shex.bin (type byte and the movement class byte 4)"""
        t = np.load(self.world / "world_types.npy")
        f = self.world / "world_shex.bin"
        self.backup("world_shex.bin")
        raw = np.fromfile(f, np.uint8)
        rec = raw[12:].reshape(self.R, self.C, 11)
        clo, chi = self.info["china_lo"], self.info["china_hi"]
        keep = np.zeros((self.R, self.C), bool)
        keep[clo:clo + 200, chi:chi + 200] = True
        m = ~keep
        rec[..., 0][m] = t[m]
        rec[..., 4][m] = np.where(t == SEA, 4, np.where(t == RIVER, 2, 6))[m]
        raw.tofile(f)
        self.say(f"world_shex.bin: terrain of {int(m.sum())} hexes outside China rewritten")

    def build(self, C, rebuild3d, deploy):
        try:
            self.running = True
            with self.lock:
                self.log = []
            t0 = time.time()
            cities = json.loads((self.world / "cities_world.json").read_text(encoding="utf-8"))
            if not 42 <= C <= min(MAX_CITIES, 42 + len(cities)):
                raise ValueError(f"cities must be 42..{min(MAX_CITIES, 42 + len(cities))}")
            dst = self.game / self.out
            dst.mkdir(parents=True, exist_ok=True)
            changed = (self.world / ".terrain_changed").exists()
            if changed and rebuild3d:
                for n in ("world_shex.bin", "world_height.npy", "world_mat.npy", "world_info.json", "china_overrides.bin"):
                    self.backup(n)
                cache = DATA / "world_hexcache.npz"
                self.run([TOOLS / "make_world.py", self.world, "--rows", self.R, "--cols", self.C,
                          "--lon0", self.info["lon0"], "--lat0", self.info["lat0"],
                          "--china-lo", self.info["china_lo"], "--china-hi", self.info["china_hi"],
                          "--types-from", self.world / "world_types.npy", "--cache", cache])
                (self.world / ".terrain_changed").unlink()
            elif changed:
                self.patch_shex()
                (self.world / ".terrain_changed").unlink()
                self.say("note: the 3D terrain was not rebuilt; edited hexes keep their old look in the game")
            self.run([TOOLS / "gen_bases.py", self.world, "--cities", C, "--out", dst, "--game", self.game])
            self.run([TOOLS / "convert_scen.py", "--cities-json", dst / "bases_cities.json", "--out", dst, "--no-ts",
                      "--game", self.game])
            for n in ("world_mat.npy", "world_info.json"):   # world_height.npy, china_overrides.bin: written by gen_bases
                src = self.world / n
                if src.exists() and (not (dst / n).exists() or src.stat().st_mtime > (dst / n).stat().st_mtime
                                     or src.stat().st_size != (dst / n).stat().st_size):
                    shutil.copy2(src, dst / n)
                    self.say(f"copied {n}")
            if deploy:
                self.set_ini(self.section, {"data_dir": self.out, "world_terrain": 1, "bases": 1, "cities": C,
                                               "width": self.C, "height": self.R,
                                               "china_x": self.info["china_hi"], "china_y": self.info["china_lo"]})
                self.say(f"worldmod.ini [{self.section}]: data_dir={self.out}, cities={C} (the original is kept as worldmod.ini.before-editor)")
            self.say(f"done in {time.time() - t0:.0f}s. Start the game with san11pk_world.exe and begin a new game "
                     f"(saves made with another city count cannot be loaded).")
        except Exception as e:
            self.say(f"ERROR: {e}")
        finally:
            self.running = False


def make_handler(prj):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            elif isinstance(body, str):
                body = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            try:
                if path in ("/", "/index.html"):
                    return self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
                if path == "/editor.js":
                    return self.send(200, (HERE / "editor.js").read_bytes(), "text/javascript; charset=utf-8")
                if path == "/api/meta":
                    return self.send(200, prj.meta())
                if path == "/api/terrain":
                    return self.send(200, prj.terrain(), "application/octet-stream")
                if path == "/api/areas":
                    a = prj.areas()
                    return self.send(200, a, "application/octet-stream") if a else self.send(404, {"error": "not built yet"})
                if path == "/api/links":
                    return self.send(200, prj.links())
                if path == "/api/build":
                    with prj.lock:
                        return self.send(200, {"running": prj.running, "log": prj.log})
                self.send(404, {"error": "not found"})
            except Exception as e:
                self.send(500, {"error": str(e)})

        def do_PUT(self):
            n = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(n)
            try:
                if self.path == "/api/terrain":
                    prj.save_terrain(body)
                    return self.send(200, {"ok": True})
                if self.path == "/api/cities":
                    prj.save_cities(json.loads(body.decode("utf-8")))
                    return self.send(200, {"ok": True})
                self.send(404, {"error": "not found"})
            except Exception as e:
                self.send(400, {"error": str(e)})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            if self.path == "/api/build":
                if prj.running:
                    return self.send(409, {"error": "a build is running"})
                threading.Thread(target=prj.build, args=(int(body.get("cities", 42)), bool(body.get("rebuild3d")),
                                                         bool(body.get("deploy"))), daemon=True).start()
                return self.send(200, {"started": True})
            self.send(404, {"error": "not found"})
    return H


def project_game_dir():
    """game_dir from project.json (written by san11kit.py init), so the editor works without --game"""
    try:
        return json.loads((DATA.parent / "project.json").read_text(encoding="utf-8")).get("game_dir") or None
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default=str(DATA / "world"), help="world directory written by make_world.py")
    ap.add_argument("--game", default=project_game_dir(), help="game directory (an ASCII path, where worldmod.ini lives); "
                    "default: game_dir in project.json")
    ap.add_argument("--out", default="world_custom", help="data directory inside the game directory to build into")
    ap.add_argument("--section", default="san11pk_world", help="worldmod.ini section (= launcher exe name) to point at the build")
    ap.add_argument("--port", type=int, default=8611)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not a.game:
        ap.error("no game directory: pass --game or run  python san11kit.py init --game <dir>  first")
    prj = Project(a.world, a.game, a.out, a.section)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(prj))
    url = f"http://127.0.0.1:{a.port}/"
    print(f"editor: {url}  (world {a.world}, game {a.game}, builds into {a.game}/{a.out}); Ctrl+C to stop")
    if not a.no_browser:
        webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    main()
