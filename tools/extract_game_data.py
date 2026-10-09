"""从你自己的《三国志11威力加强版》安装目录里提取地图生成要用的数据。

    python tools/extract_game_data.py --game "C:/San11PK"

这些数据属于光荣，不随本项目发布，所以每个使用者都要用自己的游戏提取一次：
  data/china_shex.npy     光荣中国地图的 200×200 格地形（资源 0x12B7 SHEX0008，每格 11 字节）
  data/china_k3st_v.npy   光荣中国舞台的 1025×1025 个 3D 顶点（资源 0x12B9 K3ST0006，每个 8 字节：
                          高度、RGB、法线、材质）
世界地图生成器（make_world.py）用它们学习光荣的画风，并把中国原样嵌进世界。

资源包 Media/san11pkres.bin 的格式：'LINK'，u32 条目数，从第 16 字节起每条 (u32 偏移, u32 长度)。
"""
import argparse
import struct
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"

SHEX_ID, K3ST_ID = 0x12B7, 0x12B9


def read_resource(pack, rid):
    with open(pack, "rb") as f:
        head = f.read(16)
        if head[:4] != b"LINK":
            raise SystemExit(f"{pack} 不是 LINK 资源包")
        count = struct.unpack_from("<I", head, 4)[0]
        if rid >= count:
            raise SystemExit(f"资源包里没有 {rid:#x} 号资源（只有 {count} 条）")
        f.seek(16 + 8 * rid)
        off, size = struct.unpack("<II", f.read(8))
        f.seek(off)
        return f.read(size)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--game", required=True, help="游戏目录（含 Media/san11pkres.bin）")
    ap.add_argument("--out", default=str(DATA), help="输出目录（默认 data/）")
    a = ap.parse_args()
    pack = Path(a.game) / "Media" / "san11pkres.bin"
    if not pack.exists():
        raise SystemExit(f"找不到 {pack}：--game 要指向游戏安装目录")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    shex = read_resource(pack, SHEX_ID)
    if shex[:8] != b"SHEX0008" or len(shex) < 8 + 200 * 200 * 11:
        raise SystemExit(f"资源 {SHEX_ID:#x} 不是 SHEX0008（{shex[:8]!r}），游戏版本可能不同")
    np.save(out / "china_shex.npy", np.frombuffer(shex, np.uint8, 200 * 200 * 11, 8).reshape(200, 200, 11))

    k3st = read_resource(pack, K3ST_ID)
    if k3st[:8] != b"K3ST0006" or len(k3st) < 8 + 1025 * 1025 * 8:
        raise SystemExit(f"资源 {K3ST_ID:#x} 不是 K3ST0006（{k3st[:8]!r}），游戏版本可能不同")
    np.save(out / "china_k3st_v.npy", np.frombuffer(k3st, np.uint8, 1025 * 1025 * 8, 8).reshape(1025, 1025, 8))
    print(f"已提取：{out / 'china_shex.npy'}、{out / 'china_k3st_v.npy'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
