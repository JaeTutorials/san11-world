"""Function table for a worldmod profile ("prof start" / "prof stop <file>" automation commands).

    python tools/profile_report.py <profile.bin> [--asm build/patchgen/out/pk.asm] [--top 40] [--from MS] [--to MS]

Self time: the function containing EIP. Inclusive time: every function with a frame on the stack, found
through return addresses (stack words that directly follow a call instruction). Functions are the
targets of direct calls in the listing (tools/patchgen/build_patches.py writes it).
"""
import argparse
import bisect
import collections
import os
import re
import struct

import numpy as np

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = {                       # functions documented in NOTES.md / TERRAIN_WINDOW.md / M7_LAYOUT.md
    0x567520: 'movement range search (clears HEX28)',
}


def load_listing(path):
    cache = os.path.join(PROJ, 'build', 'pk_index.npz')
    if os.path.exists(cache) and os.path.getmtime(cache) > os.path.getmtime(path):
        z = np.load(cache)
        return z['funcs'], z['rets']
    funcs, rets = set(), []
    call = re.compile(r'^call 0x([0-9a-f]+)$')
    for l in open(path, encoding='utf-8'):
        p = l.split(None, 2)
        if len(p) < 3 or not p[2].startswith('call'):
            continue
        va, n = int(p[0], 16), len(p[1]) // 2
        rets.append(va + n)
        m = call.match(p[2].strip())
        if m:
            funcs.add(int(m.group(1), 16))
    funcs, rets = np.array(sorted(funcs), np.uint32), np.array(sorted(set(rets)), np.uint32)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.savez(cache, funcs=funcs, rets=rets)
    return funcs, rets


def read_profile(path):
    data = open(path, 'rb').read()
    magic, ver, n = struct.unpack_from('<4sII', data)
    assert magic == b'WPRF' and ver == 1, 'not a worldmod profile'
    words = np.frombuffer(data, np.uint32, offset=12)
    out, i = [], 0
    for _ in range(n):
        t, eip, k = int(words[i]), int(words[i + 1]), int(words[i + 2])
        out.append((t, eip, words[i + 3:i + 3 + k]))
        i += 3 + k
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('profile')
    ap.add_argument('--asm', default=os.path.join(PROJ, 'build', 'patchgen', 'out', 'pk.asm'))
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--from', dest='t0', type=int, default=0)
    ap.add_argument('--to', dest='t1', type=int, default=1 << 31)
    a = ap.parse_args()
    funcs, rets = load_listing(a.asm)
    flist = funcs.tolist()
    retset = set(rets.tolist())

    def func_of(va):
        k = bisect.bisect_right(flist, va) - 1
        return flist[k] if k >= 0 else 0

    samples = [s for s in read_profile(a.profile) if a.t0 <= s[0] < a.t1]
    if not samples:
        raise SystemExit('no samples in range')
    selfc, incl, callers = collections.Counter(), collections.Counter(), collections.defaultdict(collections.Counter)
    outside = 0
    for t, eip, stack in samples:
        if not 0x401000 <= eip < 0x74f000:
            outside += 1
        f0 = func_of(eip) if 0x401000 <= eip < 0x74f000 else 0
        selfc[f0] += 1
        chain = [f0] + [func_of(r) for r in stack.tolist() if r in retset]
        for f in set(chain):
            incl[f] += 1
        for c, f in zip(chain[1:], chain[:-1]):      # f was called from somewhere inside c
            if c != f:
                callers[f][c] += 1
    n = len(samples)
    span = samples[-1][0] - samples[0][0]
    print(f'{n} samples over {span} ms ({outside} outside the exe: DLLs, drivers, the OS)')

    def name(f):
        return f'{f:08x} {NAMES.get(f, "")}' if f else '(outside exe)'

    print(f'\n-- self time (top {a.top})')
    for f, c in selfc.most_common(a.top):
        print(f'{100 * c / n:6.1f}%  {name(f)}')
    print(f'\n-- inclusive time (top {a.top})')
    for f, c in incl.most_common(a.top):
        top = ', '.join(f'{x:08x}' for x, _ in callers[f].most_common(3))
        print(f'{100 * c / n:6.1f}%  {name(f):48s} called from {top}')


if __name__ == '__main__':
    main()
