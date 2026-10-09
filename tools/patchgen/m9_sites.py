"""M9 (M9_UNITS.md): sites that move the unit (部队) storage out of Koei's fixed 1000 records.

The world holds 1000 units of 0xf4 bytes at world+0x169730 (0x736b088); the next object type starts right after
them, so the array moves to a DLL allocation of U records (worldmod/src/units.cpp, symbol UNITARR). The unit-count
constants (1000, 999, ...) come from the review in m9_review/; this file holds the structural part. Imported by
gen_m7.py, same row formats as m8_sites.py:

FIELD rows: (va, old value, size in bytes, new expression, comment); REWRITE rows: (start, length, asm, comment);
CAVE_TEXT rows: (va, original instruction, replacement asm) re-encoded in a cave.
"""

WORLD = 0x7201958
UBASE, USIZE = 0x736b088, 0xf4
UEND = UBASE + 1000 * USIZE          # 0x73a69a8: also where type 23 (new-officer edit data, world+0x1a5050) starts

FIELD = []
REWRITE = []
CAVE_TEXT = []


def f(va, old, expr, comment, size=4):
    FIELD.append((va, old, size, expr, comment))


# ---- world-relative (this = world): getter 0x490e70, find free 0x491040, ptr -> id 0x4917c0, location getter
# 0x491bb0, world dtor 0x492410 / ctor 0x492db0 (eh vector iterators), post-load vfunc+0x34 loop 0x493400,
# serializer 0x4937b0, EH funclet of the world ctor 0x72f0ae
for va in (0x490e85, 0x491044, 0x4917ca, 0x491bd7, 0x492508, 0x493091, 0x49363d, 0x493ae1):
    f(va, 0x169730, f'UNITARR-{WORLD:#x}', 'world unit array -> UNITARR')
f(0x72f0c0, 0x169730, f'UNITARR-{WORLD:#x}', 'EH funclet of the world ctor: unit array')
f(0x72f0b3, 1000, 'U', 'EH funclet of the world ctor: unit count (the review kept it; the array moves)')

# ---- absolute loops over all unit records (post-load list rebuild 0x493680 / 0x49375a, serializer 0x493b06):
# start, lower bound, last record, end. 0x49370e (cmp esi, 0x736b088) ends the BUILDING loop before it: kept.
for start, lo, last, end in ((0x493680, 0x493685, 0x49368d, 0x4936b6), (0x49375a, 0x493760, 0x493768, 0x493791),
                             (0x493b06, 0x493b10, 0x493b18, 0x493b40)):
    f(start, UBASE, 'UNITARR', 'unit loop start -> UNITARR')
    f(lo, UBASE, 'UNITARR', 'unit loop lower bound -> UNITARR')
    f(last, UBASE + 999 * USIZE, f'UNITARR+(U-1)*{USIZE:#x}', 'unit loop: last record')
    f(end, UEND, f'UNITARR+U*{USIZE:#x}', 'unit loop end')

# ---- 0x56dba0..0x56fe52: objects that hold a unit id (u16 at +8) index the array directly
for va in (0x56dbaa, 0x56dbda, 0x56dc5f, 0x56dd20, 0x56dd37, 0x56dd9a, 0x56ddba, 0x56dfe3, 0x56e163, 0x56e190,
           0x56e2b2, 0x56e3ff, 0x56e5f2, 0x56e73a, 0x56f13b, 0x56f16c, 0x56f28c, 0x56fbfc, 0x56fded):
    f(va, UBASE, 'UNITARR', 'unit by id -> UNITARR')
for va in (0x56dc3a, 0x56e0c7, 0x56e201, 0x56e2dc, 0x56e477, 0x56e514, 0x56e75c, 0x56f0d2, 0x56fc1c, 0x56fe52):
    f(va, UBASE + 0x3c, 'UNITARR+0x3c', 'unit position (+0x3c) by id -> UNITARR')
f(0x56dcea, UBASE + 0xcc, 'UNITARR+0xcc', 'unit +0xcc by id -> UNITARR')
for va in (0x56ddfe, 0x56f108):
    f(va, UBASE + 4, 'UNITARR+4', 'unit +4 by id -> UNITARR')

# ---- AI sub-object +0x3e94: 1000 x 4-byte per-unit records ([0] force, [1] state, [2..3] u16 target since M7
# phase C) -> AIUREC (U records). Ctor init 0x4793cf, post-load check 0x4794fc, serializer 0x47a087 (this-relative);
# the rest absolute. Phase C's u16 stores are cave texts in gen_m7.py (PHASE_C_TEXT, {AIUREC+2} when M9 is on).
AISUB = 0x73f612c
AIU0 = AISUB + 0x3e94                 # 0x73f9fc0
f(0x4793cf, 0x3e95, f'AIUREC+1-{AISUB:#x}', 'AI ctor: unit records -> AIUREC')
f(0x4794fc, 0x3e94, f'AIUREC-{AISUB:#x}', 'AI post-load check: unit records -> AIUREC')
f(0x47a087, 0x3e95, f'AIUREC+1-{AISUB:#x}', 'AI serializer: unit records -> AIUREC')
for va, k in [(0x5df095, 0), (0x5df09f, 0), (0x5df0bc, 1), (0x5df0c4, 2), (0x5e7f7d, 1), (0x5e7f8b, 2),
              (0x5ef274, 1), (0x5ef282, 0), (0x5effd1, 0), (0x5effd8, 1), (0x5f041c, 0), (0x5f0426, 1),
              (0x5f09f1, 0), (0x5f0a00, 1), (0x5f10a4, 0), (0x5f10ab, 1), (0x5f17be, 0), (0x5f17cd, 1),
              (0x5f20b3, 0), (0x5f20ba, 1), (0x5f4de1, 0), (0x5f4de8, 1)]:
    f(va, AIU0 + k, f'AIUREC+{k}', f'AI unit record [{k}] -> AIUREC')
f(0x5e0eb1, AIU0 + 2, 'AIUREC+2', 'AI unit records loop start -> AIUREC')
f(0x5e1023, AIU0 + 2 + 4000, 'AIUREC+2+U*4', 'AI unit records loop end -> AIUREC')
# (0x5f606d, 0x5f62b8, 0x5f6f1f reference 0x73faf60.., the per-city AI records after it: AICITY since M7)

# ---- record counts of the streams: the world serializer's unit loop and the AI serializer's unit records run
# over USTREAM records (the header mark's count; 1000 for Koei's files), not U
CAVE_TEXT += [
    (0x493afe, 'cmp edi, 0x3e8', 'cmp edi, dword ptr [{USTREAM}]'),
    (0x47a08d, 'mov dword ptr [esp + 0x1c], 0x3e8',
     'push eax; mov eax, dword ptr [{USTREAM}]; mov dword ptr [esp + 0x20], eax; pop eax'),
]
SKIP = {0x493afe, 0x47a08d}            # review sites handled here

# ---- 中地圖 MapUI object (vt 0x859670, ctor 0x63e5f0, heap new at 0x6375e6, M7_LAYOUT §6.1): +0x80310 holds 1000
# x 0x20 unit markers ([0] kind 2 = unit, [4] unit id); the per-base controls follow at +0x88010. The marker array
# moves to the end of the object (after M7's grown base array); the allocation grows by U*0x20 (gen_m7.py adds it to
# the M7 alloc row). Its loops use their own bases, none runs on from the building markers at +0x310.
MUOFF = '(0x8afb4+(N-87)*0x8c)'
MAPUI_ALLOC = 0x6375e6
for va, old, k in [(0x63e68a, 0x80310, 0), (0x63ea22, 0x80310, 0), (0x63f714, 0x80310, 0), (0x63f71d, 0x80310, 0),
                   (0x63fe43, 0x80314, 4)]:
    f(va, old, f'{MUOFF}+{k}', 'MapUI unit markers -> end of the object')
f(0x63f653, 0x87ff0, f'{MUOFF}+(U-1)*0x20', 'MapUI unit markers: last entry')

# ---- unit view manager (static object 0x95499b0, ctor 0x56f8b0 / dtor 0x56e1c0, about 0x15bbb0 bytes): two per-unit
# parts move to DLL allocations, the object itself stays (its other members follow them):
#  * +0: 1000 x 0x10 view wrappers ([0] model, [4] next in depth bucket, [8] u16 unit id, [0xe] flags) -> UWRAP.
#    Manager methods form wrapper i as this + i*16 (`shl idx, 4` then `add idx, this` / `[idx + this]`): those
#    become UWRAP-based (caves); four loops start at this; 26 outside sites add the absolute base.
#  * +0x5e80: node pool sub-object, 1000 x 0xc nodes (value = wrapper, prev, next) + header at +0x2edc (pool+U*0xc:
#    +0, +4 used head, +8 free head) -> UPOOL. Pool methods 0x56ee60..0x56efcc keep this = pool (header displacements
#    move); the manager's lea [this+0x5e80] and its direct used-head reads (+0x8d60, absolute 0x9552710) point at UPOOL.
MGR = 0x95499b0
for va in (0x4af072, 0x567f4d, 0x5730f0, 0x573132, 0x573312, 0x573a5e, 0x57422e, 0x57b291, 0x57fbe8, 0x5851e0, 0x585d94,
           0x58b790, 0x59f551, 0x59f59f, 0x5a00af, 0x5a4b64, 0x5a512e, 0x5a5e2f, 0x5a66fb, 0x5a8368, 0x5ab6aa, 0x5ab8ba,
           0x5abab6, 0x5ac848, 0x6a4143):
    f(va, MGR, 'UWRAP', 'unit view wrapper (absolute) -> UWRAP')
f(0x6336b1, MGR + 0xe, 'UWRAP+0xe', 'unit view wrapper flags (absolute) -> UWRAP')
# (0x57ece5 cmp edi, 0x95499b0 ends the 0x20-byte records before the manager: kept)
WRAP_TEXT = [
    # manager methods: wrapper = this + idx*16
    (0x56e46b, 'add eax, esi', 'add eax, {UWRAP}'), (0x56e508, 'add eax, esi', 'add eax, {UWRAP}'),
    (0x56f12e, 'movzx eax, word ptr [esi + edi + 8]', 'movzx eax, word ptr [esi + {UWRAP+8}]'),
    (0x56f133, 'add esi, edi', 'add esi, {UWRAP}'),
    (0x56f82b, 'mov ecx, dword ptr [esi + edi]', 'mov ecx, dword ptr [esi + {UWRAP}]'),
    (0x56f82e, 'add esi, edi', 'add esi, {UWRAP}'),
    (0x56f9ad, 'lea esi, [ecx + edi]', 'lea esi, [ecx + {UWRAP}]'),
    (0x56ffe6, 'mov eax, dword ptr [esi + ebx]', 'mov eax, dword ptr [esi + {UWRAP}]'),
    (0x56ffe9, 'add esi, ebx', 'add esi, {UWRAP}'),
    (0x57011f, 'add esi, eax', 'add esi, {UWRAP}'), (0x57025f, 'add esi, eax', 'add esi, {UWRAP}'),
    (0x57037e, 'add esi, ebx', 'add esi, {UWRAP}'),
    (0x570424, 'mov eax, dword ptr [esi + edi]', 'mov eax, dword ptr [esi + {UWRAP}]'),
    (0x570427, 'add esi, edi', 'add esi, {UWRAP}'),
    (0x570463, 'mov eax, dword ptr [esi + edi]', 'mov eax, dword ptr [esi + {UWRAP}]'),
    (0x570466, 'add esi, edi', 'add esi, {UWRAP}'),
    (0x5704c8, 'add edi, ebx', 'add edi, {UWRAP}'),
    (0x570533, 'mov ecx, dword ptr [eax + ebx]', 'mov ecx, dword ptr [eax + {UWRAP}]'),
    (0x570536, 'add eax, ebx', 'add eax, {UWRAP}'), (0x5705bf, 'add eax, ebx', 'add eax, {UWRAP}'),
    (0x5706e9, 'add esi, edi', 'add esi, {UWRAP}'), (0x570737, 'add eax, edi', 'add eax, {UWRAP}'),
    (0x5707a9, 'add esi, edi', 'add esi, {UWRAP}'), (0x5707f7, 'add eax, edi', 'add eax, {UWRAP}'),
    (0x57086d, 'add edi, esi', 'add edi, {UWRAP}'),
    (0x570961, 'mov eax, dword ptr [esi + ecx]', 'mov eax, dword ptr [esi + {UWRAP}]'),
    (0x570964, 'add esi, ecx', 'add esi, {UWRAP}'),
    (0x570a38, 'add esi, ebx', 'add esi, {UWRAP}'), (0x570a7e, 'add eax, ebx', 'add eax, {UWRAP}'),
    (0x570ad8, 'add esi, edi', 'add esi, {UWRAP}'), (0x570b1e, 'add eax, edi', 'add eax, {UWRAP}'),
    (0x570b85, 'add eax, esi', 'add eax, {UWRAP}'), (0x570bb8, 'add eax, esi', 'add eax, {UWRAP}'),
    (0x570c19, 'add esi, ebp', 'add esi, {UWRAP}'), (0x570c78, 'add eax, ebp', 'add eax, {UWRAP}'),
    (0x570d1f, 'add edi, esi', 'add edi, {UWRAP}'),
    (0x570dbd, 'mov eax, dword ptr [esi + ecx]', 'mov eax, dword ptr [esi + {UWRAP}]'),
    (0x570dc0, 'add esi, ecx', 'add esi, {UWRAP}'),
    (0x570e68, 'add esi, edi', 'add esi, {UWRAP}'), (0x570f14, 'add edi, esi', 'add edi, {UWRAP}'),
    (0x5711d8, 'add esi, ebx', 'add esi, {UWRAP}'),
    (0x57121a, 'mov ecx, dword ptr [eax + ebx]', 'mov ecx, dword ptr [eax + {UWRAP}]'),
    (0x57121d, 'add eax, ebx', 'add eax, {UWRAP}'),
    (0x571298, 'add esi, ebx', 'add esi, {UWRAP}'),
    (0x5712de, 'mov ecx, dword ptr [eax + ebx]', 'mov ecx, dword ptr [eax + {UWRAP}]'),
    (0x5712e1, 'add eax, ebx', 'add eax, {UWRAP}'),
    # loops over all wrappers that start at this (counts: m9_review)
    (0x56de45, 'mov esi, ebp', 'mov esi, {UWRAP}'),
    (0x56fcf6, 'mov esi, edi', 'mov esi, {UWRAP}'),
    (0x56f8b6, 'lea eax, [esi + 0xe]', 'mov eax, {UWRAP+0xe}'),
    (0x56f943, 'mov ecx, esi', 'mov ecx, {UWRAP}'),
]
CAVE_TEXT += WRAP_TEXT
# node pool: header displacements (pool methods, this = pool)
for va, old, k in [(0x56eea1, 0x2edc, 0), (0x56eeab, 0x2ee0, 4), (0x56eeb5, 0x2ee4, 8), (0x56eec0, 0x2ee4, 8),
                   (0x56eed8, 0x2ee0, 4), (0x56ef07, 0x2ee4, 8), (0x56ef39, 0x2ee0, 4), (0x56ef46, 0x2ee0, 4),
                   (0x56ef51, 0x2ee0, 4), (0x56ef60, 0x2ee0, 4), (0x56ef93, 0x2ee0, 4), (0x56efaf, 0x2ee4, 8),
                   (0x56efc3, 0x2ee4, 8), (0x56efcc, 0x2ee4, 8)]:
    f(va, old, f'U*0xc+{k}', 'unit view node pool header (after U nodes)')
for va in (0x4110d9, 0x573f5a, 0x587a45, 0x587b53, 0x587c03, 0x587fb3, 0x59a275, 0x5ab7c2, 0x5ab832, 0x5acf64):
    f(va, MGR + 0x8d60, 'UPOOL+U*0xc+4', 'unit view node pool: used head (absolute) -> UPOOL')
REWRITE += [
    (0x56f8d7, 6, 'mov ebp, {UPOOL}', 'unit view manager ctor: node pool -> UPOOL'),
    (0x56f98e, 6, 'mov ecx, {UPOOL}', 'unit view manager: node pool -> UPOOL'),
    (0x56f9d4, 6, 'mov ecx, {UPOOL}', 'unit view manager: node pool -> UPOOL'),
    (0x56fd2b, 6, 'mov ecx, {UPOOL}', 'unit view manager: node pool -> UPOOL'),
    (0x56f25d, 6, 'mov eax, dword ptr [{UPOOL+U*0xc+4}]', 'unit view manager: pool used head -> UPOOL'),
    (0x56f9f7, 6, 'mov edi, dword ptr [{UPOOL+U*0xc+4}]', 'unit view manager: pool used head -> UPOOL'),
    (0x56fbd9, 6, 'mov ebx, dword ptr [{UPOOL+U*0xc+4}]', 'unit view manager: pool used head -> UPOOL'),
    (0x56fdc9, 6, 'mov ebx, dword ptr [{UPOOL+U*0xc+4}]', 'unit view manager: pool used head -> UPOOL'),
]

# ---- unit snapshot (vt 0x863dd4, ctor 0x6a4180 -> init 0x6a3fd0): 1000 x 0x70 records at +4 and 1000 x 4 flags at
# +0x1b584, an object on the stack of the unit dialogs 0x61c350 / 0x624c90 (frames 0x790e0 / 0x1c548). Only seven
# methods touch the data; each starts by swapping this for a per-instance DLL buffer of the same layout sized for U
# (units.cpp snapShadow: records at +4, flags at +4+U*0x70), so the stack object keeps its size.
SNAP_ENTRY = [(0x6a3fd0, 'push ebx'), (0x6a4020, 'mov eax, dword ptr [esp + 4]'), (0x6a40a0, 'xor eax, eax'),
              (0x6a40d0, 'mov eax, dword ptr [esp + 4]'), (0x6a40f0, 'mov edx, dword ptr [esp + 4]'),
              (0x6a4200, 'push ecx'), (0x6a44d0, 'push ebx')]
CAVE_TEXT += [(va, old, 'push edx; push ecx; mov eax, {SNAPSHADOW}; call eax; add esp, 4; pop edx; mov ecx, eax; ' + old)
              for va, old in SNAP_ENTRY]
for va in (0x6a3fd7, 0x6a40a2, 0x6a40df, 0x6a40f6, 0x6a42cc):
    f(va, 0x1b584, '4+U*0x70', 'unit snapshot flags (after U records)')

# allocations made by units.cpp / bases.cpp (bytes), for the record
ALLOCS = {'UNITARR': f'U*{USIZE:#x}', 'AIUREC': 'U*4', 'AIUNIT (bases.cpp)': 'U*4', 'UWRAP': 'U*0x10',
          'UPOOL': 'U*0xc+0x10', 'snapshot shadows': '4+U*0x74 each'}
