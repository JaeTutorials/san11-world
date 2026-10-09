"""Detour compiler for worldmod.

Builds CAVE records: an instruction span at `site` is replaced by `jmp cave` (+ nops); the cave runs
replacement code plus the remaining original instructions and jumps back. Caves are position
independent: rel32 references to exe code and abs32 references to worldmod symbols are emitted as
fixups that the DLL resolves at load time.

Record (one line):
  CAVE <site> <steal_len> <old_bytes> <cave_bytes> [@<off>=rel:<hexaddr> | @<off>=abs:<expr>]... ; comment

Usage from Python:
  b = Builder()
  b.detour(0x41f8de, {0x41f8de: "sub eax, dword ptr [{WINCELL}]"}, "cell -> hex uses window origin")
  b.write(path)
In replacement asm, {NAME} is a worldmod symbol (an address resolved by the DLL's Eval), e.g. a
global variable such as WINOV, or a helper function.
"""
import bisect
import re

from keystone import KS_ARCH_X86, KS_MODE_32, Ks

LISTING = 'out/pk.asm'
PATCHES = 'out/patches_m1.txt'

_ks = Ks(KS_ARCH_X86, KS_MODE_32)
REL_BRANCH = re.compile(r'^(j\w+|call|loop\w*|jecxz)$')


def asm(text, base):
    enc, _ = _ks.asm(text, addr=base)
    return bytes(enc or b'')


class Builder:
    def __init__(self, patch_files=None):
        self.insns = {}          # va -> (bytes, mnemonic, operands)
        self.order = []
        targets = set()
        for l in open(LISTING, encoding='utf-8'):
            p = l.rstrip('\n').split(None, 3)
            if len(p) < 3:
                continue
            va = int(p[0], 16)
            ops = p[3] if len(p) > 3 else ''
            self.insns[va] = (bytes.fromhex(p[1]), p[2], ops)
            self.order.append(va)
            m = re.fullmatch(r'0x([0-9a-f]+)', ops.strip())
            if REL_BRANCH.match(p[2]) and m:
                targets.add(int(m.group(1), 16))
        self.targets = sorted(targets)
        # patch-table fields (va -> (off, size, expr)) so stolen instructions keep their patches
        self.patched = {}
        for l in (l for f in (patch_files or [PATCHES]) for l in open(f, encoding='utf-8')):
            f = l.split(';')[0].split()
            if len(f) >= 5:
                self.patched[int(f[0], 16)] = (int(f[1]), int(f[2]), ' '.join(f[4:]))
        self.records = []

    def _span(self, site, min_len=5):
        i = self.order.index(site)
        span, n = [], 0
        while n < min_len:
            va = self.order[i]
            span.append(va)
            n += len(self.insns[va][0])
            i += 1
        return span, n

    def detour(self, site, replace, comment='', min_len=5):
        """replace: {va: asm} for instructions in the stolen span that should change; other stolen
        instructions are carried over unchanged. Returns the cave's byte length."""
        span, steal = self._span(site, min_len)
        # nothing may jump into the middle of the stolen span
        lo = bisect.bisect_right(self.targets, site)
        hi = bisect.bisect_left(self.targets, site + steal)
        inside = self.targets[lo:hi]
        if inside:
            raise SystemExit(f'detour {site:#x}: branch targets inside stolen span: {[hex(t) for t in inside]}')
        # {NAME} or {EXPR}: a worldmod symbol or any expression the DLL's evaluator accepts
        symbols = sorted(set(re.findall(r'\{([^{}]+)\}', ' '.join(replace.values()))))
        old = b''.join(self.insns[va][0] for va in span)

        def build(base, symbase):
            out, fix_patch = b'', []
            for va in span:
                raw, mn, ops = self.insns[va]
                if va in replace:
                    text = replace[va]
                    for k, s in enumerate(symbols):
                        text = text.replace('{' + s + '}', hex(symbase + 0x100 * k))
                    code = asm(text, base + len(out))
                elif REL_BRANCH.match(mn):
                    code = asm(f'{mn} {ops}', base + len(out))
                else:
                    code = raw                        # verbatim: keeps patch-table offsets valid
                    if va in self.patched:
                        off, size, expr = self.patched[va]
                        fix_patch.append((len(out) + off, size, expr))
                out += code
            out += asm(f'jmp {site + steal:#x}', base + len(out))
            return out, fix_patch

        A, B = 0x10000000, 0x20000000
        S1, S2 = 0x7f000000, 0x6e000000
        c1, fp = build(A, S1)
        c2, _ = build(B, S1)
        c3, _ = build(A, S2)
        if not (len(c1) == len(c2) == len(c3)):
            raise SystemExit(f'detour {site:#x}: encoding length changed with base')
        fix = []
        for off in range(0, len(c1) - 3):
            d1 = int.from_bytes(c1[off:off + 4], 'little')
            d2 = int.from_bytes(c2[off:off + 4], 'little')
            d3 = int.from_bytes(c3[off:off + 4], 'little')
            if d1 != d2 and (d1 - d2) & 0xffffffff == (B - A) & 0xffffffff:
                fix.append(f'@{off}=rel:{(d1 + A + off + 4) & 0xffffffff:x}')
            if d1 != d3 and (d1 - d3) & 0xffffffff == (S1 - S2) & 0xffffffff:
                k = ((d1 - S1) & 0xffffffff) // 0x100
                add = (d1 - S1) & 0xff
                e = symbols[k].replace(' ', '')
                if add:
                    e = f'({e})+{add}'
                fix.append(f'@{off}=abs:{e}')
        for off, size, expr in fp:
            kind = {4: 'abs', 2: 'abs16', 1: 'abs8'}.get(size)
            if not kind:
                raise SystemExit(f'detour {site:#x}: patched field of size {size} not supported')
            fix.append(f'@{off}={kind}:{expr.replace(" ", "")}')
        self.records.append(f'CAVE {site:08x} {steal} {old.hex()} {c1.hex()} {" ".join(fix)} ; {comment}')
        return len(c1)

    def write(self, path):
        open(path, 'w').write('\n'.join(self.records) + '\n')
        print(f'{len(self.records)} cave records -> {path}')
