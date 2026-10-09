"""Build worldmod_bases.txt / worldmod_bases_caves.txt (M7: more bases, M7_LAYOUT.md) from
mapmod_re/m7_review/result_*.jsonl and mapmod_re/m7_struct_sites.jsonl. All values stay expressions in
C, G, P, N and DLL symbols, so the city count is a worldmod.ini setting. Phase 1 and phase 2 are both
applied (phase 2 lifts the 127 limits; it is valid for any N <= 255).

Run by build_patches.py (cwd = the work directory).
"""
import glob
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).replace(os.sep, '/')
from detour import Builder, asm  # noqa: E402

out_dir = sys.argv[1] if len(sys.argv) > 1 else 'm4b'

insn = {}
order = []
for l in open('out/pk.asm', encoding='utf-8'):
    p = l.rstrip('\n').split(None, 3)
    if len(p) >= 3:
        va = int(p[0], 16)
        insn[va] = (bytes.fromhex(p[1]), p[2], p[3] if len(p) > 3 else '')
        order.append(va)
pos = {va: i for i, va in enumerate(order)}


def norm(e):
    e = str(e).replace('//', '/').replace(' ', '')
    e = re.sub(r'\bmax\(', 'MAX(', e)
    e = re.sub(r'\bmin\(', 'MIN(', e)
    return e


review = []
for f in sorted(glob.glob(f'{PROJ}/m7_review/result_*.jsonl')):
    for l in open(f, encoding='utf-8'):
        r = json.loads(l)
        if r['verdict'] == 'BASE':
            review.append(r)
# M8 review (M8_FORCES.md, m8_review/result_*.jsonl): CITY = base constants the M7 review missed (always on);
# FORCE = force / corps count constants, written in C by the reviewers (trinity: R = C), applied with the regular
# force count R. FORCE sites are generated only when M8_FORCE_SITES is on (the force arrays must move first).
M8_FORCE_SITES = False
m8_city, m8_force = [], []
for f in sorted(glob.glob(f'{PROJ}/m8_review/result_*.jsonl')):
    for l in open(f, encoding='utf-8'):
        if not l.strip():
            continue
        r = json.loads(l)
        if r['verdict'] == 'CITY' and r.get('patch'):
            m8_city.append(r)
        elif r['verdict'] == 'FORCE' and r.get('patch') and r.get('role') not in ('PAIR', 'ARRAY_SIZE'):
            m8_force.append(dict(r, patch=re.sub(r'\bC\b', 'R', r['patch'])))
review += m8_city
if M8_FORCE_SITES:
    review += m8_force
struct_rows = [json.loads(l) for l in open(f'{PROJ}/m7_struct_sites.jsonl', encoding='utf-8') if l.strip()]
# follow-up pass after the C=210 tests (M7_LAYOUT.md §11a)
struct_rows += [json.loads(l) for l in open(f'{PROJ}/m7_struct_sites_extra.jsonl', encoding='utf-8') if l.strip()]

# ---- phase C: more than 255 bases (500 cities, N up to 545; M7_LAYOUT.md §9.6). The byte-sized ids of
# phase B (u8 + 0xff = none, ids up to 254) become 16-bit:
#  * the seven i8 id fields of the save / scenario streams use the game's int<->i16 serializer 0x48a9e0
#    instead of the u8 copy SER_U8ID (records grow; tools/convert_scen.py writes the new layout);
#  * the AI's unit records [2] and plan records [1] hold a u16 (the spare byte after each), read with
#    movsx word (none = 0xffff -> -1), so get_building is the game's own 0x490d00 again (it returns NULL
#    for -1); the stores and byte locals are widened below (PHASE_C_TEXT);
#  * the weighted pick 0x5f7530 (u8 count, u8 result) is replaced in the DLL; its callers keep eax.
for r in struct_rows:
    e = r.get('expr', '')
    if e.startswith('SER_U8ID'):
        r['expr'] = e.replace('SER_U8ID', 'SER_ID', 1)     # i16 in streams marked 'WIDE' (bases.cpp), else u8
    elif e.startswith('BLD_U8'):
        r['expr'] = e.replace('BLD_U8', '0x490d00', 1)
    elif r['kind'] == 'opcode' and e == '0xb6' and r['insn'].startswith('movsx') and 'byte ptr' in r['insn']:
        r['expr'] = '0xbf'                       # movsx r32, byte -> movsx r32, word

# fields replaced by structural rows
overridden = set()
for r in struct_rows:
    if r.get('overrides_m7_review'):
        overridden.add(int(r['va'], 16))
    for v in r.get('supersedes_m7_review', []) or []:
        overridden.add(int(v, 16) if isinstance(v, str) else v)

fields = {}          # (va, off) -> (size, expr, comment)
rewrites = []        # (va, length, asm_text) in-place, same length (nop padded)
widen = {}           # va -> expr: imm8 instruction re-encoded with an imm32 operand (needs a cave)
allocs = []          # DLL allocations described by the plan


def add_field(va, off, size, expr, comment):
    key = (va, off)
    if key in fields and fields[key][1] != expr:
        raise SystemExit(f'conflicting field {va:#x}+{off}: {fields[key][1]} vs {expr}')
    fields[key] = (size, expr, comment)


def locate(va, value, size):
    b = insn[va][0]
    pat = struct.pack({4: '<I', 2: '<H', 1: '<B'}[size], value & ((1 << (8 * size)) - 1))
    offs = [m for m in range(1, len(b) - size + 1) if b[m:m + size] == pat]
    if len(offs) != 1:
        # the immediate is the last field of the instruction
        if b[len(b) - size:] == pat:
            return len(b) - size
        raise SystemExit(f'{va:#x} {insn[va][1]} {insn[va][2]}: value {value:#x} at {offs}')
    return offs[0]


# ---- m7_review constants
for r in review:
    va = int(r['addr'], 16)
    if va in overridden:
        continue
    expr = norm(r['patch'])
    if r['encoding'] == 'imm32':
        v = int(str(r['value']), 0)
        add_field(va, locate(va, v, 4), 4, expr, f"[{r['role']}] {insn[va][1]} {insn[va][2]}")
    else:
        widen[va] = expr
# found in testing (an officer marched out of a new city): unit index <-> person location (+0x9c = N + unit)
# sites the review missed. Encoders and decoders must all use N, or a marching officer reads as being in city 87+k.
WIDEN_TEXT = {0x4a1c47: ('N', 'lea esi, [eax + {N}]'),        # unit formation 0x4a1bd0: officers' location
              0x489658: ('0-N', 'lea eax, [esi + {0-N}]'),    # person location -> unit
              0x48a339: ('0-N', 'lea eax, [esi + {0-N}]')}    # person location -> unit
for va, (expr, text) in WIDEN_TEXT.items():
    widen[va] = expr
# phase C: u16 target ids in the AI unit records (0x73f9fc0 + 4u, [2..3]) and plan records (AIRT +0x2164
# + 0x44k, [1..2]); every store, the byte locals they come from (int locals read as bytes), and the
# rebuild of the plan table 0x5e0e20 (its byte local [esp+0x13] moves to the unused word [esp+0x10])
PLAN1 = '{0x2165+(N-87)*0x34}'
PHASE_C_TEXT = {
    0x5e0e64: 'mov word ptr [eax - 3], 0',
    0x5e0ee5: 'mov word ptr [ebx], 0xffff',
    0x5e0f2c: 'mov word ptr [ebx], 0xffff',
    0x5e0f39: 'mov cx, word ptr [ebx]',
    0x5e0f3f: 'mov word ptr [esp + 0x10], cx',
    0x5e0f49: 'cmp cx, 0xffff',
    0x5e0f68: 'cmp word ptr [eax + 1], cx',
    0x5e0fda: 'mov dx, word ptr [esp + 0x10]',
    0x5e0fde: f'mov word ptr [eax + {PLAN1}], dx',
    0x5df270: 'mov word ptr [eax + 2], bx',
    0x5ef27b: 'mov word ptr [esi*4 + 0x73f9fc2], ax',
    0x5effdf: 'mov word ptr [esi*4 + 0x73f9fc2], ax',
    0x5f0406: 'mov dx, word ptr [esp + 0x14]',
    0x5f042e: 'mov word ptr [edi*4 + 0x73f9fc2], dx',
    0x5f0a08: 'mov word ptr [edi*4 + 0x73f9fc2], ax',
    0x5f108a: 'mov cx, word ptr [esp + 0x18]',
    0x5f1095: 'mov word ptr [edi*4 + 0x73f9fc2], cx',
    0x5f17ba: 'mov dx, word ptr [esp + 0x14]',
    0x5f17d5: 'mov word ptr [edi*4 + 0x73f9fc2], dx',
    0x5f20c2: 'mov word ptr [esi*4 + 0x73f9fc2], ax',
    0x5f4df0: 'mov word ptr [edi*4 + 0x73f9fc2], ax',
    0x5ee8e4: f'mov word ptr [eax + {PLAN1}], bx',
    0x5efb18: 'mov word ptr [ecx + 1], ax',
    0x5f043f: f'mov word ptr [eax + {PLAN1}], dx',
    0x5f078e: 'mov cx, word ptr [esp + 0x18]',
    0x5f079b: f'mov word ptr [eax + {PLAN1}], cx',
    0x5f0e75: f'mov word ptr [ecx + {PLAN1}], bx',
    0x5f15b2: 'mov dx, word ptr [esp + 0x14]',
    0x5f15d4: f'mov word ptr [eax + {PLAN1}], dx',
    0x5f1f0e: f'mov word ptr [esi + edi + {PLAN1}], ax',
    0x5f4ce0: 'mov ax, word ptr [esp + 0x24]',
    0x5f4ce4: f'mov word ptr [ecx + {PLAN1}], ax',
}
for va, text in PHASE_C_TEXT.items():
    widen[va] = 'TEXT'
    WIDEN_TEXT[va] = (None, text)

# ---- structural rows
HAND = {}            # hand-written in-place rewrites for rows described in prose: va -> (start, length, asm)
HAND[0x54fb99] = (0x54fb99, 0x54fbe6 - 0x54fb99,
                  'mov edx, {C}; L: cmp dword ptr [eax], ebp; jne S; mov dword ptr [eax], edi; mov dword ptr [eax - 4], ecx; '
                  'S: add eax, 0x14; dec edx; jne L')
HAND[0x58c3dd] = (0x58c3dd, 19, 'mov edi, {AIBLD16}; rep stosd; xor ebp, ebp; xor edi, edi; mov esi, {AIBLD16+8}')
HAND[0x58c452] = (0x58c452, 12, 'add dword ptr [eax + {AIBLD16+0xc}], ecx')
HAND[0x58c476] = (0x58c476, 10, 'mov edi, {AIBLD16+4}')
HAND[0x590598] = (0x590598, 6, 'add dword ptr [eax + {AIBLD16+4}], edi')
HAND[0x590711] = (0x590711, 6, 'add dword ptr [eax + {AIBLD16+4}], ebx')
HAND[0x590766] = (0x590766, 12, 'add dword ptr [eax + {AIBLD16+0xc}], ebx')
HAND[0x5df02e] = (0x5df02e, 7, 'mov eax, dword ptr [edi*4 + {AIUNIT}]')
HAND[0x5df113] = (0x5df113, 7, 'mov ecx, dword ptr [edi*4 + {AIUNIT}]')
HAND[0x5e0e3b] = (0x5e0e3b, 6, 'mov edx, {AIUNIT}')
HAND[0x5e199a] = (0x5e199a, 6, 'mov edi, {AIUNIT}')
HAND[0x63d5ee] = (0x63d5e0, 0x63d63e - 0x63d5e0,
                  'mov edx, dword ptr [esp + 4]; push esi; xor eax, eax; push edi; add ecx, 0x88098; mov esi, {N}; '
                  'L: cmp dword ptr [ecx - 8], edx; jne S; cmp dword ptr [ecx], 0; je S; mov eax, 1; '
                  'S: add ecx, 0x8c; dec esi; jne L; pop edi; pop esi; ret 4')
DETOUR_HAND = {
    # bitset<C> serializer: the two stored dwords stay; the bytes of CITYBITS beyond them take the place of
    # as many bytes of the 0xc4-byte reserved tail that follows (one 0x479620 byte each), so the stream
    # keeps its length (the TS / save layouts of convert_scen.py stay valid) and no city bit is lost
    # (streams without the 'WIDE' header mark, i.e. saves made before phase C: one byte per extra dword
    # written after the tail, as phase B did)
    0x680729: 'push {CITYBITS}; mov ecx, esi; call 0x481b50; add ebp, 0x5c; push ebp; mov ecx, esi; call 0x481b50; '
              'cmp dword ptr [{IDWIDE}], 0; je O; '
              'mov ebp, {CITYBITS+8}; L: cmp ebp, {CITYBITS+8+MAX(0,((C+7)>>3)-8)}; jae D; push ebp; mov ecx, esi; '
              'call 0x479620; inc ebp; jmp L; D: lea eax, [ebx + {0xc0-MAX(0,((C+7)>>3)-8)}]; jmp E; '
              'O: mov ebp, {CITYBITS+8}; L2: cmp ebp, {CITYBITS+4*((C+31)>>5)}; jae D2; push ebp; mov ecx, esi; '
              'call 0x479620; add ebp, 4; jmp L2; D2: lea eax, [ebx + 0xc0]; E: nop',
}

for r in struct_rows:
    va = int(r['va'], 16)
    k = r['kind']
    if k == 'alloc' and not r['insn'].startswith('push'):
        allocs.append(r)
        continue
    if k == 'cave':
        if 'new' in r:
            rewrites.append((va, int(r['size']), bytes.fromhex(r['new']), r.get('relocs', []), r['struct'][:60]))
        elif va in HAND:
            start, length, text = HAND[va]
            rewrites.append((start, length, text, None, r['struct'][:60]))
        elif va in DETOUR_HAND:
            rewrites.append((va, int(r['size']), ('DETOUR', DETOUR_HAND[va]), None, r['struct'][:60]))
        elif r['insn'].startswith('call 0x490d00'):
            add_field(va, int(r['off']), 4, norm(r['expr']), 'call BLD_U8')
        else:
            raise SystemExit(f'unhandled cave row {r["va"]}: {r["expr"][:80]}')
        continue
    size = int(r['size'])
    expr = norm(r['expr'])
    add_field(va, int(r['off']), size, expr, f"[{k}] {r['struct'][:50]}")
# phase C: two more plan [1] reads that only copy the id into a unit record (movsx byte -> movsx word)
for va in (0x5ef25e, 0x5effb8):
    assert insn[va][0][:2] == b'\x0f\xbe', hex(va)
    add_field(va, 1, 1, '0xbf', '[opcode] plan [1] read as a word (phase C)')
# the weighted pick returns an int now (DLL replacement of 0x5f7530): its callers keep eax
rewrites.append((0x5e46c9, 3, 'nop; nop; nop', None, 'weighted pick result is an int (phase C)'))
rewrites.append((0x5e48df, 3, 'nop; nop; nop', None, 'weighted pick result is an int (phase C)'))
rewrites.append((0x5e8290, 3, 'mov ecx, eax; nop', None, 'weighted pick result is an int (phase C)'))
# area -> city 0x4839f0 (u8 table, so C <= 256): a u16 table
rewrites.append((0x4839f0, 16, 'mov eax, dword ptr [esp + 4]; movzx eax, word ptr [eax*2 + {AREA2CITY}]; ret',
                 None, 'AREA2CITY u16 (phase C)'))

# ---- found in testing (not in the review): 0x492990 sorts the names of all persons and bases into
# heap buffers sized for 1100 + 87 entries (0x104-byte names, two pointer arrays)
EXTRA = [(0x49299f, 1, 4, '(1100+N)*0x104', 'person+base name buffer (0x492990)'),
         (0x4929b2, 1, 4, '(1100+N)*4', 'person+base name pointers (0x492990)'),
         (0x4929c0, 1, 4, '(1100+N)*4', 'person+base name pointers (0x492990)')]
EXTRA += [
    # found in testing: members after the embedded per-city widget (ScreenE, NewGameK) read in other forms
    (0x54ce29, 2, 4, '0x5d78+((C-42)*0xc0)', 'ScreenE: add edi,0x5d78 (16 scenario buttons after the widget)'),
    (0x54c66b, 2, 4, '0x5d78+((C-42)*0xc0)', 'ScreenE: add esi,0x5d78 (16 scenario buttons after the widget)'),
    (0x54ed3a, 2, 4, '0x34e0+((C-42)*0xc0)+(((C-42)*0x14+15)/16*16)', 'NewGameK +0x34e0 (after the widget and S)'),
    (0x54eda0, 2, 4, '0x2528+((C-42)*0xc0)', 'NewGameK: S.city[0]+0x10 (S follows the widget)'),
]
for va, off, size, expr, comment in EXTRA:
    add_field(va, off, size, expr, f'[alloc] {comment}')
# found in testing: loops over S.city[42] (0x14 each) unrolled 6x7; rewritten as C plain iterations
LOOP_S = [
    (0x54ec01, 0x54ec8c, 'mov ebp, {C}; L: mov ecx, dword ptr [eax - 4]; cmp ecx, -1; je T; cmp ecx, dword ptr [edx + 8]; jne S; '
                         'T: cmp dword ptr [eax], 0; jne S; inc edi; S: add eax, 0x14; dec ebp; jne L'),
    (0x54eda6, 0x54ee36, 'mov esi, {C}; L: mov ecx, dword ptr [eax - 4]; cmp ecx, -1; je T; cmp ecx, dword ptr [ebx + 8]; jne S; '
                         'T: cmp dword ptr [eax], 0; jne S; inc edx; S: add eax, 0x14; dec esi; jne L'),
    (0x55088c, 0x5508d8, 'mov esi, {C}; L: cmp dword ptr [ecx - 0x14], eax; jne S; cmp eax, -1; je S; inc edx; '
                         'S: add ecx, 0x14; dec esi; jne L'),
    (0x556496, 0x556505, 'mov edx, {C}; L: mov eax, dword ptr [esi + 8]; cmp eax, -1; je S; cmp dword ptr [ecx + 4], eax; jne S; '
                         'mov dword ptr [ecx], ebp; S: add ecx, 0x14; dec edx; jne L'),
]
for start, end, text in LOOP_S:
    rewrites.append((start, end - start, text, None, 'S.city[C] loop (was unrolled 6x7)'))
# gate/port boundary review (2026-10-08, m7_review/result_GP.jsonl): the two id -> index helpers have every operand
# changing, too dense for imm8 caves; rewritten whole (22 bytes + int3 padding = 0x20 each)
ID2IDX = [
    (0x4862d0, 'mov eax, dword ptr [esp + 4]; cmp eax, {C}; jl L; cmp eax, {C+G-1}; jg L; sub eax, {C}; ret; '
               'L: or eax, 0xffffffff; ret', 'building id -> gate index'),
    (0x4862f0, 'mov eax, dword ptr [esp + 4]; cmp eax, {C+G}; jl L; cmp eax, {N-1}; jg L; sub eax, {C+G}; ret; '
               'L: or eax, 0xffffffff; ret', 'building id -> port index'),
]
for start, text, comment in ID2IDX:
    rewrites.append((start, 0x20, text, None, comment))

# ---- field patch lines (fields inside an in-place rewrite are part of the rewrite)
rw_spans = [(start, length) for start, length, text, relocs, comment in rewrites]
lines = []
for (va, off), (size, expr, comment) in sorted(fields.items()):
    if any(s0 <= va < s0 + n0 for s0, n0 in rw_spans):
        continue
    b = insn[va][0] if va in insn else None
    if b is None:              # data item (not an instruction): verify the bytes from the exe
        exe = open(f'{PROJ}/backup/san11pk.exe.orig', 'rb').read()
        b = exe[va - 0x400000: va - 0x400000 + off + size]
    lines.append(f'{va:08x} {off} {size} {b.hex()} {expr} ; {comment}')

# ---- caves: imm8 -> imm32 re-encodings, grouped into detours; hand detours; in-place rewrites
open('m4b/_bases_inplace.txt', 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
bld = Builder(['out/patches_m1.txt', 'm4b/_terrain_inplace.txt', 'm4b/_bases_inplace.txt'])
taken = set()
for start, length, text, relocs, comment in rewrites:
    for v in range(start, start + length):
        taken.add(v)
field_vas = {va for (va, off) in fields}
caves_ok, caves_failed = 0, []


def imm32_text(va, expr):
    raw, mn, ops = insn[va]
    sym = '{' + expr + '}' if not expr.startswith('-') else '{0' + expr + '}'
    if mn == 'lea':           # lea r, [base +/- disp8] -> [base + disp32]; expr is the signed displacement
        new = re.sub(r' [+-] (0x[0-9a-f]+|\d+)\]$', ' + ' + sym + ']', ops)
    else:
        new = re.sub(r'(-?0x[0-9a-f]+|-?\d+)$', sym, ops)
    if new == ops:
        raise SystemExit(f'{va:#x} {mn} {ops}: no immediate to widen')
    return f'{mn} {new}'


for va in sorted(widen):
    if va in taken:
        continue
    done = False
    for back in range(0, 4):                     # start the stolen span at the instruction or a few before it
        start = order[pos[va] - back]
        span, n = [], 0
        i = pos[start]
        while n < 5 or order[i - 1] < va:
            span.append(order[i]); n += len(insn[order[i]][0]); i += 1
        if any(v in taken for v in span):
            continue                              # (other field patches in the span are carried by the cave)
        rep = {}
        for v in span:
            if v in widen:
                rep[v] = WIDEN_TEXT[v][1] if v in WIDEN_TEXT else imm32_text(v, widen[v])
        try:
            bld.detour(start, rep, f'imm8->imm32 {insn[va][1]} {insn[va][2]} = {widen[va]}', min_len=n)
        except SystemExit:
            continue
        for v in span:
            taken.add(v)
        done = True
        caves_ok += 1
        break
    if not done:
        caves_failed.append(va)

records = list(bld.records)
for start, length, text, relocs, comment in rewrites:
    old = b''.join(insn[v][0] for v in order[pos[start]:] if v < start + length) if start in pos else None
    if old is None or len(old) != length:
        raise SystemExit(f'rewrite {start:#x}: not an instruction-aligned span of {length} bytes')
    if isinstance(text, tuple):                   # true detour written by hand
        b2 = Builder.__new__(Builder)
        b2.__dict__.update(bld.__dict__); b2.records = []
        span_vas = [v for v in order[pos[start]:] if v < start + length]
        rep = {v: '' for v in span_vas}; rep[start] = text[1]
        b2.detour(start, rep, comment, min_len=length)
        records += b2.records
        continue
    if isinstance(text, bytes):
        new, fx = text, [f'@{r["off"]}={"abs" if r["size"] == 4 else "abs16"}:{norm(r["expr"])}' for r in relocs]
    else:
        syms = sorted(set(re.findall(r'\{([^{}]+)\}', text)))
        t1, t2 = text, text
        for k, s in enumerate(syms):
            t1 = t1.replace('{' + s + '}', hex(0x7f000000 + 0x100 * k))
            t2 = t2.replace('{' + s + '}', hex(0x6e000000 + 0x100 * k))
        new, n2 = asm(t1, start), asm(t2, start)
        fx = []
        for off in range(len(new) - 3):
            d1 = int.from_bytes(new[off:off + 4], 'little'); d2 = int.from_bytes(n2[off:off + 4], 'little')
            if d1 != d2 and (d1 - d2) & 0xffffffff == 0x11000000:
                k, add = divmod((d1 - 0x7f000000) & 0xffffffff, 0x100)
                e = norm(syms[k])
                fx.append(f'@{off}=abs:' + (f'({e})+{add}' if add else e))
    if len(new) > length:
        raise SystemExit(f'rewrite {start:#x}: {len(new)} bytes > {length}')
    new = new + b'\x90' * (length - len(new))
    records.append(f'REWRITE {start:08x} {length} {old.hex()} {new.hex()} {" ".join(fx)} ; {comment}')

open(f'{out_dir}/worldmod_bases.txt', 'w', encoding='utf-8').write(
    '; worldmod base-count patches (M7_LAYOUT.md), generated by gen_m7.py; do not edit\n' + '\n'.join(lines) + '\n')
open(f'{out_dir}/worldmod_bases_caves.txt', 'w', encoding='utf-8').write('\n'.join(records) + '\n')
json.dump([{k: r[k] for k in ('va', 'struct', 'expr', 'phase', 'note')} for r in allocs],
          open(f'{out_dir}/bases_allocs.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'{len(lines)} field patches, {caves_ok} imm8->imm32 caves, {len(rewrites)} rewrites, {len(allocs)} DLL allocations')
print(f'failed imm8 sites ({len(caves_failed)}): {[hex(v) for v in caves_failed[:40]]}')
bad = [hex(v) for v in caves_failed if v in PHASE_C_TEXT or v in WIDEN_TEXT]
if bad:
    raise SystemExit(f'phase C / hand-widened sites without a cave: {bad}')
