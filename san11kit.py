"""三国志11 世界地图开发工具包 —— 总入口。

    python san11kit.py init --game "C:/San11PK"     第一次用：生成 project.json
    python san11kit.py doctor                       检查环境，告诉你还缺什么
    python san11kit.py download                     下载公开的高程和河流数据（约 470 MB）
    python san11kit.py setup                        从你的游戏提取数据，把 MOD 装进游戏目录
    python san11kit.py world [--fresh|--reselect]   生成世界数据（--fresh：地形从头生成；--reselect：重新自动选城）
    python san11kit.py scenario [剧本.json ...]      把剧本 JSON 编进剧本文件（不写文件名就编 project.json 里列的）
    python san11kit.py cities [--find 羅馬]          列出城市的编号和名字
    python san11kit.py forces [--base 0]            列出某个剧本里现在的势力
    python san11kit.py editor                       打开地图和城市编辑器（浏览器）
    python san11kit.py play                         启动游戏
    python san11kit.py dll                          编译 worldmod（需要 Visual Studio 生成工具，一般不用）

所有设置都在 project.json 里（用文本编辑器打开改即可），说明见 docs/快速上手.md。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJ / "tools"))
import pipeline as P  # noqa: E402


def cmd_init(a):
    p = Path(a.project)
    if p.exists() and not a.force:
        print(f"{p} 已经存在（要重写请加 --force）")
        return 1
    g = Path(a.game)
    if not (g / "Media").is_dir():
        print(f"{g} 不是游戏目录：里面应该有 Media 文件夹和 san11pk.exe")
        return 1
    cfg = dict(P.DEFAULT_PROJECT)
    cfg.update({"game_dir": g.as_posix(), "world_dir": "data/world", "data_name": "world_custom",
                "scenarios": ["scenarios/europe_184.json"], "save_dir": "UserData_kit"})
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {p}。下一步：python san11kit.py doctor")
    if not P.is_ascii_path(g):
        print("注意：游戏目录的路径里有中文，游戏会读不了剧本。建一个英文路径的目录联接（管理员命令行）：\n"
              f'  mklink /J C:\\San11PK "{g}"\n然后把 project.json 的 game_dir 改成 C:/San11PK')
    return 0


def cmd_doctor(a):
    ok = True

    def line(good, text, fix=""):
        nonlocal ok
        ok &= good
        print(("  [好] " if good else "  [缺] ") + text + ("" if good or not fix else f"\n        → {fix}"))
    print("Python 和库：")
    line(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}", "需要 Python 3.9 或更新")
    for mod in ("numpy", "scipy", "shapefile", "tifffile", "PIL"):
        try:
            __import__(mod)
            line(True, mod)
        except ImportError:
            line(False, mod, "pip install -r requirements.txt")
    print("项目：")
    try:
        cfg = P.load_project(a.project)
        line(True, f"project.json（游戏目录 {cfg['game_dir']}，{cfg['cities']} 座城）")
    except P.StepError as e:
        line(False, "project.json", str(e))
        return 1
    g = Path(cfg["game_dir"])
    print("游戏：")
    line((g / "Media").is_dir(), f"游戏目录 {g}", "改 project.json 的 game_dir")
    line(P.is_ascii_path(g), "游戏目录是英文路径", f'建目录联接：mklink /J C:\\San11PK "{g}"')
    good, why = P.exe_build(g / "san11pk.exe")
    line(good, f"san11pk.exe {why}", "worldmod 只支持这一个版本")
    line((g / cfg["exe"]).exists(), f"启动程序 {cfg['exe']}", "python san11kit.py setup")
    dll = g / "d3d9.dll"
    line(dll.exists() and b"worldmod" in dll.read_bytes(), "游戏目录里的 worldmod（d3d9.dll）", "python san11kit.py setup")
    print("数据：")
    for f in ("china_shex.npy", "china_k3st_v.npy"):
        line((P.DATA / f).exists(), f"data/{f}（从你的游戏提取）", "python san11kit.py setup")
    for p, u in P.DOWNLOADS.items():
        have = p.exists() or (p == P.ETOPO_TIF and P.ETOPO_NPY.exists())
        line(have, f"{p.relative_to(P.PROJ)}（公开数据）", "python san11kit.py download")
    world = P.project_path(cfg, "world_dir")
    line((world / "world_types.npy").exists(), f"世界地形 {cfg['world_dir']}", "python san11kit.py world --fresh")
    line((g / cfg["data_name"] / "bases_tables.bin").exists(), f"游戏里的世界数据 {cfg['data_name']}", "python san11kit.py world")
    print("全部就绪，可以 python san11kit.py play" if ok else "按上面「→」的提示补齐后再运行一次 doctor")
    return 0 if ok else 1


def cmd_download(a):
    todo = P.missing_downloads()
    if not todo:
        print("公开数据都已经有了")
        return 0
    for p, u in todo:
        print(f"  {u}\n    -> {p}")
    if not a.yes and input("下载以上文件？[y/N] ").strip().lower() != "y":
        return 1
    P.download()
    P.prepare_dem()
    return 0


def cmd_setup(a):
    cfg = P.load_project(a.project)
    g = P.game_dir(cfg)
    if not all((P.DATA / f).exists() for f in ("china_shex.npy", "china_k3st_v.npy")):
        P.run("extract_game_data.py", "--game", g)
    if P.ETOPO_TIF.exists():
        P.prepare_dem()
    P.deploy_mod(cfg)
    return 0


def cmd_world(a):
    cfg = P.load_project(a.project)
    if a.cities:
        cfg["cities"] = a.cities
    P.build_world(cfg, fresh=a.fresh, reselect=a.reselect)
    if cfg.get("scenarios"):
        P.build_scenarios(cfg)
    print("完成。启动：python san11kit.py play（要开新游戏；城市数不同的存档互不通用）")
    return 0


def cmd_scenario(a):
    cfg = P.load_project(a.project)
    P.build_scenarios(cfg, a.files or None)
    return 0


def _data(cfg):
    return P.game_dir(cfg) / cfg["data_name"]


def cmd_cities(a):
    cfg = P.load_project(a.project)
    info = _data(cfg) / "world_info.json"
    clo, chi = (lambda i: (i["china_lo"], i["china_hi"]))(json.loads(info.read_text())) if info.exists() else (0, 0)
    rows = [(k["id"], k["name"], k["lo"] + clo, k["hi"] + chi, "光荣") for k in
            json.loads((P.DATA / "cities_georef.json").read_text(encoding="utf-8"))]
    bc = _data(cfg) / "bases_cities.json"
    if bc.exists():
        rows += [(c["id"], c["name"], c["lo"], c["hi"], "新") for c in json.loads(bc.read_text(encoding="utf-8"))["new"]]
    for cid, name, lo, hi, src in rows:
        if a.find and a.find not in name:
            continue
        print(f"{cid:4d}  {name:4s}  ({lo},{hi})  {src}")
    return 0


def cmd_forces(a):
    cfg = P.load_project(a.project)
    P.run("scenario_build.py", "--data", _data(cfg), "--base", a.base)
    return 0


def cmd_editor(a):
    cfg = P.load_project(a.project)
    return subprocess.call([sys.executable, str(PROJ / "tools" / "editor" / "server.py"),
                            "--world", str(P.project_path(cfg, "world_dir")), "--game", cfg["game_dir"],
                            "--out", cfg["data_name"], "--section", P.section_of(cfg)])


def cmd_play(a):
    cfg = P.load_project(a.project)
    g = P.game_dir(cfg)
    exe = g / cfg["exe"]
    if not exe.exists():
        print(f"没有 {exe}：先运行 python san11kit.py setup")
        return 1
    subprocess.Popen([str(exe)], cwd=str(g))
    print(f"已启动 {exe}")
    return 0


def cmd_dll(a):
    cfg = P.load_project(a.project)
    r = subprocess.call(["cmd", "/c", str(P.WORLDMOD / "build.bat")])
    if r:
        print("编译失败：需要安装 Visual Studio 2022 生成工具（C++ 桌面开发）")
        return r
    P.deploy_mod(cfg)
    return 0


def main():
    ap = argparse.ArgumentParser(description="三国志11 世界地图开发工具包", formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("--project", default=str(PROJ / "project.json"), help="项目文件（默认 project.json）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init", help="生成 project.json"); s.add_argument("--game", required=True); s.add_argument("--force", action="store_true")
    sub.add_parser("doctor", help="检查环境")
    s = sub.add_parser("download", help="下载公开数据"); s.add_argument("--yes", action="store_true")
    sub.add_parser("setup", help="提取游戏数据，安装 MOD")
    s = sub.add_parser("world", help="生成世界数据"); s.add_argument("--fresh", action="store_true"); s.add_argument("--cities", type=int)
    s.add_argument("--reselect", action="store_true")
    s = sub.add_parser("scenario", help="编译剧本"); s.add_argument("files", nargs="*")
    s = sub.add_parser("cities", help="列出城市"); s.add_argument("--find")
    s = sub.add_parser("forces", help="列出剧本里的势力"); s.add_argument("--base", type=int, default=0)
    sub.add_parser("editor", help="地图和城市编辑器")
    sub.add_parser("play", help="启动游戏")
    sub.add_parser("dll", help="编译 worldmod")
    a = ap.parse_args()
    try:
        return globals()["cmd_" + a.cmd](a)
    except P.StepError as e:
        print("错误：", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
