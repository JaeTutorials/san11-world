"""打发布包：版本库里的全部文件 + 编译好的 worldmod/build/d3d9.dll，压成一个 zip。

    python tools/make_release.py [--version v0.1] [--out dist]

GitHub Actions（.github/workflows/release.yml）在推送 v* 标签时自动运行它，再把 zip 传到 Releases。
本地运行前先编译 DLL（python san11kit.py dll 或 worldmod\\build.bat）。

只打包 git 跟踪的文件，所以 .gitignore 排除的东西（光荣的数据、生成的大文件、project.json）不会进包；
另外再按文件名检查一遍，发现游戏文件就拒绝打包。
"""
import argparse
import fnmatch
import subprocess
import sys
import zipfile
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
DLL = "worldmod/build/d3d9.dll"
# 光荣的文件和从中提取的数据：绝不能进发布包
FORBIDDEN = ["*.exe", "*.s11", "*.S11", "san11pkres.bin", "*china_shex*", "*china_k3st*", "*.wft", "*.bin.orig"]

NOTES = """\
三国志11威力加强版 世界地图开发工具包 {ver}

**下载 `{zip}`**（下面「Source code」两个包不含编译好的 d3d9.dll，开发者才用）。

需要：Windows、正版《三国志11威力加强版》、Python 3.9 以上。解压到任意目录后，在那个目录里打开命令提示符：

```bat
pip install -r requirements.txt
python san11kit.py init --game "C:/San11PK"
python san11kit.py doctor
python san11kit.py download
python san11kit.py setup
python san11kit.py world --fresh
python san11kit.py play
```

每一步的说明见包里的 `docs/快速上手.md`。包里不含任何光荣的游戏文件，中国地图由 `setup` 从你自己的游戏里提取。
d3d9.dll 由 GitHub Actions 从本版本的源码自动编译（提交 {commit}）。
"""


def git(*args):
    return subprocess.run(["git", *args], cwd=PROJ, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", help="版本号，默认取 git describe（比如 v0.1）")
    ap.add_argument("--out", default="dist", help="输出目录")
    a = ap.parse_args()

    ver = a.version or git("describe", "--tags", "--always", "--dirty").strip()
    commit = git("rev-parse", "--short", "HEAD").strip()
    files = [f for f in git("-c", "core.quotepath=off", "ls-files", "-z").split("\0") if f]
    bad = [f for f in files if any(fnmatch.fnmatch(Path(f).name, p) for p in FORBIDDEN)]
    if bad:
        sys.exit("拒绝打包：这些像是游戏文件或从游戏里提取的数据：\n  " + "\n  ".join(bad))
    dll = PROJ / DLL
    if not dll.exists() or b"worldmod" not in dll.read_bytes():
        sys.exit(f"没有编译好的 {DLL}：先运行  python san11kit.py dll  或  worldmod\\build.bat")
    if DLL in files:
        sys.exit(f"{DLL} 不应该进版本库（检查 .gitignore）")

    out = PROJ / a.out
    out.mkdir(parents=True, exist_ok=True)
    top = f"san11-world-{ver}"
    zpath = out / f"{top}.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files + [DLL]:
            z.write(PROJ / f, f"{top}/{f}")
    (out / "release_notes.md").write_text(NOTES.format(ver=ver, zip=zpath.name, commit=commit), encoding="utf-8")
    print(f"{zpath}  {len(files) + 1} 个文件，{zpath.stat().st_size / 1e6:.1f} MB")
    print(f"{out / 'release_notes.md'}")


if __name__ == "__main__":
    main()
