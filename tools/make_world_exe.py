"""Create san11pk_world.exe: a copy of san11pk.exe with two PE header changes.

  * IMAGE_FILE_LARGE_ADDRESS_AWARE  -> the 32-bit process may use up to 4 GB on 64-bit Windows
  * SizeOfStackReserve = 48 MB       -> functions that keep W*H-sized arrays on the stack fit (up to ~8M cells)

The code and data are untouched, so worldmod's build check (timestamp + SizeOfImage) still matches.
Usage: python make_world_exe.py <game_dir> [name]   (name: the new launcher, default san11pk_world.exe;
       worldmod reads the worldmod.ini section named after it)
"""
import shutil
import struct
import sys
from pathlib import Path

STACK_RESERVE = 48 << 20   # default for EVERY thread; larger values starve the 32-bit address space


def main(game_dir: Path, name: str = "san11pk_world.exe") -> None:
    src = game_dir / "san11pk.exe"
    dst = game_dir / name
    data = bytearray(src.read_bytes())
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise SystemExit("not a PE file")
    characteristics_at = e_lfanew + 4 + 18
    optional_at = e_lfanew + 24
    if struct.unpack_from("<H", data, optional_at)[0] != 0x10B:
        raise SystemExit("not a PE32 image")
    stack_reserve_at = optional_at + 72

    characteristics = struct.unpack_from("<H", data, characteristics_at)[0] | 0x20
    struct.pack_into("<H", data, characteristics_at, characteristics)
    struct.pack_into("<I", data, stack_reserve_at, STACK_RESERVE)

    tmp = dst.with_suffix(".tmp")
    tmp.write_bytes(data)
    shutil.move(tmp, dst)
    print(f"wrote {dst} (LAA on, stack reserve {STACK_RESERVE >> 20} MB)")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "."), sys.argv[2] if len(sys.argv) > 2 else "san11pk_world.exe")
