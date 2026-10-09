"""Regenerate worldmod's patch tables from the site lists in mapmod_re.

    python tools/patchgen/build_patches.py [--out DIR]

Inputs (all in mapmod_re):
  backup/san11pk.exe.orig          the unmodified exe (disassembled once into the work directory)
  worldmod/worldmod_patches.txt    M1 tables (array relocation); read only, to keep stolen fields patched
  m4b_sites.jsonl                  whole-world terrain sites (M4B.md)
  m7_review/result_*.jsonl         base-id sites (M7_LAYOUT.md)
  m7_struct_sites.jsonl, m7_struct_sites_extra.jsonl   per-base structure members (M7_LAYOUT.md 9, 11a)
Outputs (DIR, default worldmod/):
  worldmod_terrain.txt, worldmod_terrain_caves.txt, worldmod_bases.txt, worldmod_bases_caves.txt

Every value is an expression (C, G, P, N, CHLO, QB, ...) that the DLL evaluates at load time, so the
outputs do not depend on the city count or the world size; rerun only after editing a site list.
Needs: pip install pefile capstone keystone-engine
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))


def run(script, *args, cwd):
    print(f'== {script} {" ".join(args)}')
    subprocess.run([sys.executable, os.path.join(HERE, script), *args], cwd=cwd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(PROJ, 'worldmod'))
    ap.add_argument('--work', default=os.path.join(PROJ, 'build', 'patchgen'))
    a = ap.parse_args()
    out, work = os.path.abspath(a.out), os.path.abspath(a.work)
    for d in (out, os.path.join(work, 'out'), os.path.join(work, 'm4b')):
        os.makedirs(d, exist_ok=True)
    listing = os.path.join(work, 'out', 'pk.asm')
    if not os.path.exists(listing):
        run('disasm.py', os.path.join(PROJ, 'backup', 'san11pk.exe.orig'), listing, cwd=work)
    shutil.copyfile(os.path.join(PROJ, 'worldmod', 'worldmod_patches.txt'), os.path.join(work, 'out', 'patches_m1.txt'))
    run('m3_lines.py', cwd=work)
    run('gen_terrain.py', out, cwd=work)
    run('gen_m7.py', out, cwd=work)
    print(f'done -> {out}')


if __name__ == '__main__':
    main()
