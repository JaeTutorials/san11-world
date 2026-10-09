"""san11kit.py 和地图编辑器共用的构建步骤。

每一步都只是按顺序调用 tools/ 里的一个脚本，所以想知道某一步具体做了什么，打开对应的脚本看开头的说明即可：

  extract_game_data.py   从你的游戏里提取中国地图（光荣的数据，不随项目发布）
  make_world.py          用公开的高程、河流数据生成整个世界的地形，画风校准成光荣的样子
  select_cities.py       按重要程度和间距挑选新城市
  gen_bases.py           划分每座城的领地、生成城市相邻表和游戏要用的各种表
  connect_cities.py      沿城市之间的连线修路（主径、栈道、渡所）
  convert_scen.py        把光荣的 14 个剧本转换成新的城市数
  scenario_build.py      把你写的剧本 JSON 编进剧本文件
"""
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
PROJ = TOOLS.parent
DATA = PROJ / "data"
WORLDMOD = PROJ / "worldmod"

EXE_STAMP, EXE_IMAGE = 1168334429, 0x9883000          # 本 MOD 支持的 san11pk.exe（PE 时间戳、映像大小）
PATCH_TABLES = ["worldmod_patches.txt", "worldmod_caves.txt", "worldmod_bases.txt", "worldmod_bases_caves.txt",
                "worldmod_terrain.txt", "worldmod_terrain_caves.txt"]
ETOPO_TIF = DATA / "raw" / "etopo" / "ETOPO_2022_v1_60s_N90W180_surface.tif"
ETOPO_NPY = DATA / "etopo60s_i16.npy"
DOWNLOADS = {   # 公开数据：NOAA ETOPO 2022（公有领域）、Natural Earth 1:10m（公有领域）
    ETOPO_TIF: "https://www.ngdc.noaa.gov/thredds/fileServer/global/ETOPO2022/60s/60s_surface_elev_gtif/"
               "ETOPO_2022_v1_60s_N90W180_surface.tif",
    DATA / "raw" / "ne_rivers" / "ne_10m_rivers_lake_centerlines.zip":
        "https://naciscdn.org/naturalearth/10m/physical/ne_10m_rivers_lake_centerlines.zip",
    DATA / "raw" / "ne_lakes" / "ne_10m_lakes.zip": "https://naciscdn.org/naturalearth/10m/physical/ne_10m_lakes.zip",
}


class StepError(Exception):
    pass


def say(msg):
    print(msg, flush=True)


def run(script, *args, log=say):
    """运行 tools/ 里的一个脚本，把输出逐行转给 log；失败时抛出 StepError"""
    cmd = [sys.executable, str(TOOLS / script), *map(str, args)]
    log("$ " + " ".join([script, *map(str, args)]))
    p = subprocess.Popen(cmd, cwd=TOOLS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    for line in p.stdout:
        log("  " + line.rstrip())
    if p.wait():
        raise StepError(f"{script} 失败（返回码 {p.returncode}），错误信息见上面")


# ---------------------------------------------------------------- 项目配置
DEFAULT_PROJECT = {
    "game_dir": "",                     # 游戏目录（建议用纯英文路径，比如目录联接 C:/San11PK）
    "world_dir": "data/world",          # 世界地图的工作目录（生成的中间文件，在本项目里）
    "data_name": "world_custom",        # 游戏目录里的数据目录名
    "cities": 500,                      # 城市总数（含光荣的 42 座），42~1000
    "forces": 42,                       # 常规势力（= 常规军团）数，42~249 且不超过城市数；另有 4 个异族和 1 个贼（M8_FORCES.md）
    "spacing": 14,                      # 城市最小间距（格），光荣中国约 13~21
    "exe": "san11pk_world.exe",         # 用哪个启动程序玩（它在 worldmod.ini 里有同名的一节）
    "save_dir": "",                     # 存档目录（空 = 游戏默认的「我的文档」）
    "scenarios": [],                    # 要编进去的剧本 JSON
}


def load_project(path):
    p = Path(path)
    if not p.exists():
        raise StepError(f"找不到项目文件 {p}：先运行  python san11kit.py init --game <游戏目录>")
    cfg = {**DEFAULT_PROJECT, **json.loads(p.read_text(encoding="utf-8"))}
    cfg["_path"] = p
    return cfg


def project_path(cfg, key):
    v = Path(cfg[key])
    return v if v.is_absolute() else (PROJ / v)


def game_dir(cfg):
    g = Path(cfg["game_dir"])
    if not (g / "Media").is_dir():
        raise StepError(f"{g} 不是游戏目录（里面应该有 Media 文件夹）：请改 project.json 的 game_dir")
    return g


def section_of(cfg):
    return Path(cfg["exe"]).stem


# ---------------------------------------------------------------- 检查
def exe_build(path):
    """(ok, 说明)：worldmod 只支持一个特定版本的 san11pk.exe"""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
        e = struct.unpack_from("<I", head, 0x3C)[0]
        stamp = struct.unpack_from("<I", head, e + 8)[0]
        image = struct.unpack_from("<I", head, e + 24 + 56)[0]
    except (OSError, struct.error):
        return False, "读不了"
    if stamp == EXE_STAMP and image == EXE_IMAGE:
        return True, "版本正确"
    return False, f"版本不对（时间戳 {stamp}、映像大小 {image:#x}，需要 {EXE_STAMP}、{EXE_IMAGE:#x}）"


def is_ascii_path(p):
    try:
        str(p).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


# ---------------------------------------------------------------- worldmod.ini
def ini_read(game):
    f = Path(game) / "worldmod.ini"
    out, sec = {}, None
    if f.exists():
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                sec = s[1:-1]; out[sec] = {}
            elif "=" in s and sec and not s.startswith(";"):
                k, v = s.split("=", 1); out[sec][k.strip()] = v.strip()
    return out


def ini_set(game, section, values, log=say):
    """改 worldmod.ini 里一节的若干个键（第一次改之前把原文件留一份 worldmod.ini.before-kit）"""
    f = Path(game) / "worldmod.ini"
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines() if f.exists() else []
    out, sec, done = [], None, set()
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if sec == section:
                out += [f"{k}={v}" for k, v in values.items() if k not in done]
                done |= set(values)
            sec = s[1:-1]
        elif sec == section and "=" in s and not s.startswith(";") and s.split("=", 1)[0].strip() in values:
            k = s.split("=", 1)[0].strip()
            out.append(f"{k}={values[k]}"); done.add(k); continue
        out.append(line)
    if sec == section:
        out += [f"{k}={v}" for k, v in values.items() if k not in done]
    elif section not in ini_read(game):
        out += ["", f"[{section}]"] + [f"{k}={v}" for k, v in values.items()]
    bak = f.with_name("worldmod.ini.before-kit")
    if f.exists() and not bak.exists():
        shutil.copy2(f, bak)
    f.write_text("\n".join(out) + "\n", encoding="utf-8")
    log(f"worldmod.ini [{section}]: " + ", ".join(f"{k}={v}" for k, v in values.items()))


# ---------------------------------------------------------------- 准备数据
def prepare_dem(log=say):
    """ETOPO 2022 GeoTIFF -> data/etopo60s_i16.npy（int16 米，21600×10800）"""
    if ETOPO_NPY.exists():
        return
    if not ETOPO_TIF.exists():
        raise StepError(f"缺少高程数据 {ETOPO_TIF}：运行  python san11kit.py download  或手动下载\n  {DOWNLOADS[ETOPO_TIF]}")
    import numpy as np
    import tifffile
    log("转换 ETOPO 高程数据（约 1 分钟）……")
    a = tifffile.imread(ETOPO_TIF)
    np.save(ETOPO_NPY, np.round(a).astype(np.int16))
    log(f"已写入 {ETOPO_NPY}")


def missing_downloads():
    return [(p, u) for p, u in DOWNLOADS.items() if not p.exists() and not (p == ETOPO_TIF and ETOPO_NPY.exists())]


def download(log=say):
    import urllib.request
    for p, u in missing_downloads():
        p.parent.mkdir(parents=True, exist_ok=True)
        log(f"下载 {u}")
        tmp = p.with_suffix(p.suffix + ".part")
        urllib.request.urlretrieve(u, tmp)
        tmp.replace(p)
        log(f"  -> {p}（{p.stat().st_size >> 20} MB）")


# ---------------------------------------------------------------- 世界
def build_world(cfg, fresh=False, reselect=False, log=say):
    """生成世界数据，写进 <game_dir>/<data_name>。
    fresh：地形从头生成（之后也会重新选城）；reselect：按 cities_*.json 重新选城（会覆盖编辑器里改过的城市表）。
    平时（两个都不加）沿用 world_dir 里现有的地形和城市表，只重新划领地、修路、转换剧本。"""
    t0 = time.time()
    g = game_dir(cfg)
    world = project_path(cfg, "world_dir")
    dst = g / cfg["data_name"]
    C = int(cfg["cities"])
    if not 42 <= C <= 1000:
        raise StepError(f"cities 要在 42~1000 之间（{C}）")
    R = int(cfg.get("forces", 42))
    if not 42 <= R <= min(249, C):
        raise StepError(f"forces 要在 42~{min(249, C)} 之间（最多 249，且不超过城市数 {C}）（{R}）")
    for f in ("china_shex.npy", "china_k3st_v.npy"):
        if not (DATA / f).exists():
            raise StepError(f"缺少 data/{f}：先运行  python san11kit.py setup")
    world.mkdir(parents=True, exist_ok=True)
    cache = DATA / "world_hexcache.npz"
    if fresh or not (world / "world_types.npy").exists():
        prepare_dem(log)
        run("make_world.py", world, "--cache", cache, log=log)
        (world / "world_types.before_roads.npy").unlink(missing_ok=True)
        reselect = True
    if reselect or not (world / "cities_world.json").exists():
        run("select_cities.py", world, "--spacing", cfg["spacing"], "--max", C - 42, log=log)
    have = len(json.loads((world / "cities_world.json").read_text(encoding="utf-8")))
    if have < C - 42:
        raise StepError(f"城市表里只有 {have} 座新城，凑不够 {C} 座：减小 cities，或用 --reselect 重新选城（可以减小 spacing）")
    links = world / "_links"
    run("gen_bases.py", world, "--cities", C, "--out", links, "--game", g, log=log)
    if (world / "world_types.before_roads.npy").exists():   # roads are always laid from the terrain without roads
        shutil.copy2(world / "world_types.before_roads.npy", world / "world_types.npy")
    run("connect_cities.py", world, "--links", links / "bases_cities.json", log=log)
    run("make_world.py", world, "--types-from", world / "world_types.npy", "--cache", cache, log=log)
    dst.mkdir(parents=True, exist_ok=True)
    run("gen_bases.py", world, "--cities", C, "--out", dst, "--game", g, log=log)
    run("convert_scen.py", "--cities-json", dst / "bases_cities.json", "--out", dst, "--no-ts", "--game", g,
        "--forces", R, log=log)
    shutil.rmtree(dst / "scenario_base", ignore_errors=True)    # scenario_build.py starts from the fresh files
    for f in ("world_mat.npy", "world_info.json"):
        shutil.copy2(world / f, dst / f)
    info = json.loads((world / "world_info.json").read_text())
    values = {"world_terrain": 1, "data_dir": cfg["data_name"], "width": info["cols"], "height": info["rows"],
              "china_x": info["china_hi"], "china_y": info["china_lo"], "bases": 1, "cities": C, "forces": R, "auto_skip": 1}
    if cfg.get("save_dir"):
        values["save_dir"] = cfg["save_dir"]
    ini_set(g, section_of(cfg), values, log)
    log(f"世界数据已生成：{dst}（{C} 座城，用时 {time.time() - t0:.0f} 秒）")


def build_scenarios(cfg, files=None, log=say):
    g = game_dir(cfg)
    dst = g / cfg["data_name"]
    for f in files or cfg.get("scenarios", []):
        p = Path(f)
        p = p if p.is_absolute() else PROJ / p
        run("scenario_build.py", p, "--data", dst, log=log)


# ---------------------------------------------------------------- 部署
def deploy_mod(cfg, log=say):
    """把 worldmod（d3d9.dll + 补丁表）装进游戏目录，并准备好启动程序"""
    g = game_dir(cfg)
    dll = WORLDMOD / "build" / "d3d9.dll"
    if not dll.exists():
        raise StepError("没有编译好的 worldmod/build/d3d9.dll：下载发布包里的 d3d9.dll 放到 worldmod/build/，"
                        "或者装好 Visual Studio 生成工具后运行  python san11kit.py dll")
    ok, why = exe_build(g / "san11pk.exe")
    if not ok:
        raise StepError(f"{g / 'san11pk.exe'}：{why}。worldmod 只支持这一个版本，其它版本会被它拒绝打补丁")
    old = g / "d3d9.dll"
    if old.exists() and b"worldmod" not in old.read_bytes() and not (g / "d3d9.dll.before-kit").exists():
        shutil.copy2(old, g / "d3d9.dll.before-kit")
        log("游戏目录里原来的 d3d9.dll 已备份为 d3d9.dll.before-kit")
    try:
        shutil.copy2(dll, old)
    except PermissionError:                       # the game is running: the loaded DLL can be renamed, not replaced
        old.replace(g / "d3d9.dll.in-use")
        shutil.copy2(dll, old)
    for t in PATCH_TABLES:
        shutil.copy2(WORLDMOD / t, g / t)
    exe = g / cfg["exe"]
    if not exe.exists():
        run("make_world_exe.py", g, cfg["exe"], log=log)
    ini = ini_read(g)
    if "mod" not in ini:
        ini_set(g, "mod", {"enable": 1, "verify_only": 0}, log)
    if not is_ascii_path(g):
        log("注意：游戏目录的路径里有中文。游戏在这种路径下读不了剧本，请建一个英文路径的目录联接：\n"
            f'  mklink /J C:\\San11PK "{g}"\n  然后把 project.json 的 game_dir 改成 C:/San11PK')
    log(f"worldmod 已装进 {g}")
