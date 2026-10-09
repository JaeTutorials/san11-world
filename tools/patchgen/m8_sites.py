"""M8 (M8_FORCES.md): sites that move the per-force / per-corps data out of Koei's fixed-size storage.

The constants (47 forces, 46, 42 regular, 42..45 barbarians, ...) come from the review in m8_review/; this
file holds the structural part: every reference to an array that is sized by the force or corps count is
pointed at a DLL allocation (worldmod/src/forces.cpp) of F = R+5 (or R) entries. Imported by gen_m7.py.

Each FIELD row: (va, old value, size in bytes, new expression, comment); the field is found in the
instruction bytes by its old value. REWRITE rows: (start, length, asm text with {expr}, comment).
"""

WORLD = 0x7201958
AISUB = 0x73f612c        # AI sub-object (world+0x1f47d4)
FLAG = 0x73bf304         # flag object (type 18, world+0x1bd9ac)

FIELD = []
REWRITE = []


def f(va, old, expr, comment, size=4):
    FIELD.append((va, old, size, expr, comment))


# ---- world force / corps arrays (world+0x7af8 47 x 0x12c, world+0xb20c 47 x 0x50); counts: m8_review
for va in (0x490ab3, 0x490fc4, 0x49127a, 0x4926ec, 0x492e4b, 0x49345d, 0x493862):
    f(va, 0x7af8, f'FORCEARR-{WORLD:#x}', 'world force array -> FORCEARR')
for va in (0x490ae3, 0x491004, 0x4912ca, 0x4926cf, 0x492e6a, 0x493478, 0x493886):
    f(va, 0xb20c, f'CORPSARR-{WORLD:#x}', 'world corps array -> CORPSARR')
f(0x72eef8, 0x7af8, f'FORCEARR-{WORLD:#x}', 'EH funclet of the world ctor: force array')
f(0x72ef10, 0xb20c, f'CORPSARR-{WORLD:#x}', 'EH funclet of the world ctor: corps array')

# ---- turn order: world header +0xc4 int[47] of force ids (getter 0x482610 byte index, setter 0x482960,
# ctor clear 0x482d2f, serializer 0x4832d5); the byte fields after it (+0x180 current, +0x181 count) stay
for va in (0x48261b, 0x482969, 0x482d2f, 0x4832d5):
    f(va, 0xc4, f'TURNORD-{WORLD:#x}', 'turn order int[F] -> TURNORD')

# ---- AI sub-object +0x94: 42 x 0xd4 regular-force records -> AIFREG (R records)
AIFREG0 = 0x73f61c0
for va, old in [(0x5dc7b7, 0x73f6291), (0x5e211f, 0x73f6290), (0x5e2264, 0x73f6290), (0x5e29e7, 0x73f6290),
                (0x5e2aac, 0x73f6290), (0x5e2c85, 0x73f6290), (0x5e2fdd, 0x73f6290), (0x5e3114, 0x73f6290),
                (0x5e331a, 0x73f6290), (0x5e3326, 0x73f6290), (0x5e3351, 0x73f6291), (0x5e34a8, 0x73f6290),
                (0x5e6213, 0x73f6293), (0x5e6219, 0x73f6293), (0x5e7671, 0x73f6290), (0x5e796d, 0x73f6290),
                (0x5e7973, 0x73f6290), (0x5e7996, 0x73f6291), (0x5e8159, 0x73f6291), (0x5e8e79, 0x73f6290),
                (0x5e9039, 0x73f6290), (0x5e904d, 0x73f6291), (0x5e908d, 0x73f6290), (0x5e93d4, 0x73f6290),
                (0x5e9407, 0x73f6290), (0x5e9693, 0x73f6291), (0x5e9e68, 0x73f6292), (0x5ea014, 0x73f6290),
                (0x5ea0d8, 0x73f6292), (0x5eb890, 0x73f6290), (0x5ecc64, 0x73f6290), (0x5ed8c8, 0x73f6290),
                (0x5ef50f, 0x73f6290), (0x5ef66c, 0x73f6290), (0x5ef9b4, 0x73f6290), (0x5ef9e2, 0x73f6290),
                (0x5efbf8, 0x73f6290), (0x5f016c, 0x73f6290), (0x5f1214, 0x73f6290), (0x5f2e5a, 0x73f6290),
                (0x5f67d3, 0x73f6290), (0x5f67e1, 0x73f6290), (0x5f6969, 0x73f6288), (0x5f69b8, 0x73f61c0),
                (0x5f69c3, 0x73f61c8), (0x5f69ce, 0x73f6288), (0x5f69d8, 0x73f6290), (0x5f69de, 0x73f6291),
                (0x5f6a05, 0x73f61c0), (0x5f6a3d, 0x73f61c0), (0x5f6a68, 0x73f61c0), (0x5f6a95, 0x73f61c8),
                (0x5f6acd, 0x73f61c8), (0x5f6af8, 0x73f61c8), (0x5f79c0, 0x73f6290), (0x5f79c8, 0x73f6290),
                (0x5f79d6, 0x73f6290), (0x5f7bdb, 0x73f6288), (0x5f86f0, 0x73f61c0), (0x5f978f, 0x73f6290),
                (0x5f979d, 0x73f6290), (0x5f97af, 0x73f6290)]:
    f(va, old, f'AIFREG+{old - AIFREG0:#x}', 'AI regular-force record -> AIFREG')
# folded end of the record array (0x73f6290 + 42*0xd4)
f(0x5e2b2c, 0x73f8558, 'AIFREG+0xd0+R*0xd4', 'AI force records: folded end -> AIFREG')
f(0x5e8eb1, 0x73f8558, 'AIFREG+0xd0+R*0xd4', 'AI force records: folded end -> AIFREG')
# this-relative in the AI sub-object's ctor (ebp = this): record loop base rec+8
f(0x4792c4, 0x9c, f'AIFREG+8-{AISUB:#x}', 'AI ctor: force records -> AIFREG')
# serializer 0x479680: rec = this + k*0xd4, fields at rec+0x94.. -> base AIFREG-0x94
REWRITE.append((0x479804, 13, 'imul eax, eax, 0xd4; lea ebp, [eax + {AIFREG-0x94}]',
                'AI serializer: force record k -> AIFREG'))

# ---- AI sub-object +0x235c: 47 x 0x34 corps records -> AICORPS (F records)
f(0x479339, 0x235d, f'AICORPS+1-{AISUB:#x}', 'AI ctor: corps records -> AICORPS')
f(0x479c55, 0x235d, f'AICORPS+1-{AISUB:#x}', 'AI serializer: corps records -> AICORPS')
f(0x5e7ad4, 0x73f8488, 'AICORPS', 'AI corps record [0] (force id) -> AICORPS')
f(0x5e7b1e, 0x73f8489, 'AICORPS+1', 'AI corps record [1] -> AICORPS')

# ---- flag object (0x73bf304): four per-force arrays of sub-objects -> FLAG104 / FLAG84A / FLAG84B / FLAG1004
ARR = {'FLAG104': (0x1118, 0x104), 'FLAG84A': (0x40d4, 0x84), 'FLAG84B': (0x5910, 0x84), 'FLAG1004': (0x714c, 0x1004)}


def flag_rel(va, old, name):
    lo, el = ARR[name]
    f(va, old, f'{name}+{old - lo:#x}-{FLAG:#x}', f'flag object {name}')


for va, old, name in [(0x47f491, 0x1118, 'FLAG104'), (0x47f498, 0x1118, 'FLAG104'), (0x47f4e1, 0x40d4, 'FLAG84A'),
                      (0x47f4e8, 0x40d4, 'FLAG84A'), (0x47f531, 0x5910, 'FLAG84B'), (0x47f538, 0x5910, 'FLAG84B'),
                      (0x47f581, 0x714c, 'FLAG1004'), (0x47f588, 0x714c, 'FLAG1004'), (0x47f5b9, 0x40d4, 'FLAG84A'),
                      (0x47f5f9, 0x5910, 'FLAG84B'), (0x47f8bf, 0x714c, 'FLAG1004'), (0x47f8df, 0x5910, 'FLAG84B'),
                      (0x47f8fc, 0x40d4, 'FLAG84A'), (0x47f919, 0x1118, 'FLAG104'), (0x47f9bc, 0x7150, 'FLAG1004'),
                      (0x47f9c2, 0x5914, 'FLAG84B'), (0x47f9c8, 0x111c, 'FLAG104'), (0x47fda0, 0x1118, 'FLAG104'),
                      (0x47fdc2, 0x40d4, 'FLAG84A'), (0x47fde4, 0x5910, 'FLAG84B'), (0x47fe06, 0x714c, 'FLAG1004'),
                      (0x480088, 0x7150, 'FLAG1004'), (0x480092, 0x5914, 'FLAG84B'), (0x480098, 0x111c, 'FLAG104')]:
    flag_rel(va, old, name)
# FLAG84A record k = FLAG84B record k - 0x183c in Koei's layout (lea edi,[edx-0x183c]); separate arrays now
f(0x47f9e1, -0x183c, 'FLAG84A-FLAG84B', 'flag reset: FLAG84A from FLAG84B pointer')
f(0x4800ae, -0x183c, 'FLAG84A-FLAG84B', 'flag serializer: FLAG84A from FLAG84B pointer')
# absolute addressing in 0x4a0b00..0x4a0ca0 (per-force lookups and loops over all forces)
for va, old, name in [(0x4a0b0f, 0x73c041c, 'FLAG104'), (0x4a0b15, 0x73c041c, 'FLAG104'), (0x4a0b31, 0x73c041c, 'FLAG104'),
                      (0x4a0b7e, 0x73c33d8, 'FLAG84A'), (0x4a0b84, 0x73c33d8, 'FLAG84A'), (0x4a0ba0, 0x73c33d8, 'FLAG84A'),
                      (0x4a0bee, 0x73c4c14, 'FLAG84B'), (0x4a0bf4, 0x73c4c14, 'FLAG84B'), (0x4a0c10, 0x73c4c14, 'FLAG84B'),
                      (0x4a0c5e, 0x73c6450, 'FLAG1004'), (0x4a0c64, 0x73c6450, 'FLAG1004'), (0x4a0c80, 0x73c6450, 'FLAG1004')]:
    f(va, old, name, f'flag object {name} (absolute)')
for va, old, name in [(0x4a0b49, 0x73c33d8, 'FLAG104'), (0x4a0bb8, 0x73c4c14, 'FLAG84A'),
                      (0x4a0c28, 0x73c6450, 'FLAG84B'), (0x4a0c98, 0x73f550c, 'FLAG1004')]:
    el = dict((n, e) for n, (l, e) in ARR.items())[name]
    f(va, old, f'{name}+(R+5)*{el:#x}', f'flag object {name}: loop end')

# ---- static arrays indexed by force id
# 0x9283108 int[42] (Koei: incremented for owner ids up to 46, past its end) -> SFRC1[F]
for va in (0x54aa9b, 0x54aaa2, 0x54c141, 0x54c17f):
    f(va, 0x9283108, 'SFRC1', 'static int[42] by force -> SFRC1')
# 0x7998b88 int[47] force sort rank -> SFRC2[F]
for va in (0x4cda49, 0x4cda77, 0x4cec71, 0x4cecde):
    f(va, 0x7998b88, 'SFRC2', 'static int[47] force rank -> SFRC2')
# 0x7998c48 char[47][0x40] by force -> SFRC3[F][0x40]
for va in (0x4cec13, 0x4cd957, 0x4cd968):
    f(va, 0x7998c48, 'SFRC3', 'static char[47][64] by force -> SFRC3')
# 0x9c4a608 int[47] by force (sort callbacks 0x688b40 / 0x688be0) -> SFRC4[F]
for va in (0x68867d, 0x688795, 0x688ba4, 0x688bab, 0x688c44, 0x688c4b):
    f(va, 0x9c4a608, 'SFRC4', 'static int[47] by force -> SFRC4')

# allocations made by forces.cpp (bytes), for the record
ALLOCS = {
    'FORCEARR': 'F*0x12c', 'CORPSARR': 'F*0x50', 'FREL': 'F*F', 'FA64': 'F*F', 'TURNORD': 'F*4',
    'AIFREG': 'R*0xd4', 'AICORPS': 'F*0x34', 'FLAG104': 'F*0x104', 'FLAG84A': 'F*0x84', 'FLAG84B': 'F*0x84',
    'FLAG1004': 'F*0x1004', 'SFRC1': 'F*4', 'SFRC2': 'F*4', 'SFRC3': 'F*0x40', 'SFRC4': 'F*4',
}

# ---- stack-local arrays sized by the force count (16 arrays in 14 functions): every access goes to a
# slot of STKARR (0x2000 bytes each, enough for 1005 forces x 8 bytes) instead of the frame. Accesses found
# with the frame-offset tracker (scratchpad m8/stackarr.py); the offsets that differ from the clearing lea
# (pushed arguments in between) were checked by hand. (va, original, replacement)
STKSLOTS = 32
STACK = [
    (0x4ab871, 'lea edi, [esp + 0x38]', 'mov edi, {STKARR+0x0*0x2000}'),   # fn 0x4ab770
    (0x4ab8e5, 'mov dword ptr [esp + eax*4 + 0x38], 1', 'mov dword ptr [eax*4 + {STKARR+0x0*0x2000}], 1'),   # fn 0x4ab770
    (0x4ab938, 'mov ecx, dword ptr [esp + eax*4 + 0x38]', 'mov ecx, dword ptr [eax*4 + {STKARR+0x0*0x2000}]'),   # fn 0x4ab770
    (0x4cc1aa, 'lea edi, [esp + 0x14]', 'mov edi, {STKARR+0x1*0x2000}'),   # fn 0x4cc130
    (0x4cc206, 'mov dword ptr [esp + 0x14], ebp', 'mov dword ptr [{STKARR+0x1*0x2000}], ebp'),   # fn 0x4cc130
    (0x4cc247, 'mov dword ptr [esp + ebx*4 + 0x14], esi', 'mov dword ptr [ebx*4 + {STKARR+0x1*0x2000}], esi'),   # fn 0x4cc130
    (0x4cc28a, 'mov dword ptr [esp + ebx*4 + 0x14], esi', 'mov dword ptr [ebx*4 + {STKARR+0x1*0x2000}], esi'),   # fn 0x4cc130
    (0x4cc2c0, 'mov esi, dword ptr [esp + edi*4 + 0x14]', 'mov esi, dword ptr [edi*4 + {STKARR+0x1*0x2000}]'),   # fn 0x4cc130
    (0x58d1e3, 'lea edi, [esp + 0x18]', 'mov edi, {STKARR+0x2*0x2000}'),   # fn 0x58d1d0
    (0x58d233, 'mov ebx, dword ptr [esp + edi*4 + 0x18]', 'mov ebx, dword ptr [edi*4 + {STKARR+0x2*0x2000}]'),   # fn 0x58d1d0
    (0x58d252, 'mov dword ptr [esp + edi*4 + 0x18], esi', 'mov dword ptr [edi*4 + {STKARR+0x2*0x2000}], esi'),   # fn 0x58d1d0
    (0x58d38d, 'mov ecx, dword ptr [esp + ebx*4 + 0x18]', 'mov ecx, dword ptr [ebx*4 + {STKARR+0x2*0x2000}]'),   # fn 0x58d1d0
    (0x58d1ee, 'lea edi, [esp + 0xd4]', 'mov edi, {STKARR+0x3*0x2000}'),   # fn 0x58d1d0
    (0x58d256, 'mov ecx, dword ptr [esp + edi*4 + 0xd4]', 'mov ecx, dword ptr [edi*4 + {STKARR+0x3*0x2000}]'),   # fn 0x58d1d0
    (0x58d25d, 'lea eax, [esp + edi*4 + 0xd4]', 'lea eax, [edi*4 + {STKARR+0x3*0x2000}]'),   # fn 0x58d1d0
    (0x58d2cb, 'mov ebp, dword ptr [esp + ebx*4 + 0xd4]', 'mov ebp, dword ptr [ebx*4 + {STKARR+0x3*0x2000}]'),   # fn 0x58d1d0
    (0x59920c, 'lea edi, [esp + 0x20]', 'mov edi, {STKARR+0x4*0x2000}'),   # fn 0x599190
    (0x599264, 'lea edi, [esp + edi*4 + 0x20]', 'lea edi, [edi*4 + {STKARR+0x4*0x2000}]'),   # fn 0x599190
    (0x599275, 'lea ecx, [esp + 0x20]', 'mov ecx, {STKARR+0x4*0x2000}'),   # fn 0x599190
    (0x59929d, 'mov edi, dword ptr [esp + esi*4 + 0x20]', 'mov edi, dword ptr [esi*4 + {STKARR+0x4*0x2000}]'),   # fn 0x599190
    (0x5992c3, 'cmp dword ptr [esp + ecx + 0x20], edx', 'cmp dword ptr [ecx + {STKARR+0x4*0x2000}], edx'),   # fn 0x599190
    (0x59ae60, 'lea edi, [esp + 0x50]', 'mov edi, {STKARR+0x5*0x2000}'),   # fn 0x59ae30
    (0x59ae7c, 'lea ecx, [esp + 0x54]', 'mov ecx, {STKARR+0x5*0x2000}'),   # fn 0x59ae30
    (0x59aea4, 'cmp dword ptr [esp + eax*4 + 0x50], 6', 'cmp dword ptr [eax*4 + {STKARR+0x5*0x2000}], 6'),   # fn 0x59ae30
    (0x59af29, 'cmp dword ptr [esp + edi*4 + 0x50], 2', 'cmp dword ptr [edi*4 + {STKARR+0x5*0x2000}], 2'),   # fn 0x59ae30
    (0x59ae6b, 'lea edi, [esp + 0xf8]', 'mov edi, {STKARR+0x6*0x2000}'),   # fn 0x59ae30
    (0x59ae74, 'lea eax, [esp + 0xf8]', 'mov eax, {STKARR+0x6*0x2000}'),   # fn 0x59ae30
    (0x59b03d, 'mov ecx, dword ptr [esp + eax*4 + 0xf8]', 'mov ecx, dword ptr [eax*4 + {STKARR+0x6*0x2000}]'),   # fn 0x59ae30
    (0x59b5d3, 'lea edi, [esp + 0x70]', 'mov edi, {STKARR+0x7*0x2000}'),   # fn 0x59b510
    (0x59b606, 'lea eax, [esp + 0x7c]', 'mov eax, {STKARR+0x7*0x2000}'),   # fn 0x59b510
    (0x59b66f, 'mov ebp, dword ptr [esp + ebx*4 + 0x70]', 'mov ebp, dword ptr [ebx*4 + {STKARR+0x7*0x2000}]'),   # fn 0x59b510
    (0x59b678, 'cmp ebp, dword ptr [esp + eax*4 + 0x70]', 'cmp ebp, dword ptr [eax*4 + {STKARR+0x7*0x2000}]'),   # fn 0x59b510
    (0x59b718, 'cmp dword ptr [esp + ebx*4 + 0x70], 3', 'cmp dword ptr [ebx*4 + {STKARR+0x7*0x2000}], 3'),   # fn 0x59b510
    (0x59b799, 'mov eax, dword ptr [esp + eax*4 + 0x70]', 'mov eax, dword ptr [eax*4 + {STKARR+0x7*0x2000}]'),   # fn 0x59b510
    (0x59b5de, 'lea edi, [esp + 0x118]', 'mov edi, {STKARR+0x8*0x2000}'),   # fn 0x59b510
    (0x59b5fe, 'lea eax, [esp + 0x120]', 'mov eax, {STKARR+0x8*0x2000}'),   # fn 0x59b510
    (0x59b696, 'mov eax, dword ptr [esp + ebx*4 + 0x118]', 'mov eax, dword ptr [ebx*4 + {STKARR+0x8*0x2000}]'),   # fn 0x59b510
    (0x5bcd15, 'lea edi, [esp + 0x10]', 'mov edi, {STKARR+0x9*0x2000}'),   # fn 0x5bcce0
    (0x5bcd6d, 'mov dword ptr [esp + edi*4 + 0x10], ecx', 'mov dword ptr [edi*4 + {STKARR+0x9*0x2000}], ecx'),   # fn 0x5bcce0
    (0x5bcd9d, 'mov eax, dword ptr [esp + eax*4 + 0x10]', 'mov eax, dword ptr [eax*4 + {STKARR+0x9*0x2000}]'),   # fn 0x5bcce0
    (0x5bcdf5, 'lea edi, [esp + 0x10]', 'mov edi, {STKARR+0xa*0x2000}'),   # fn 0x5bcdc0
    (0x5bce4d, 'mov dword ptr [esp + edi*4 + 0x10], ecx', 'mov dword ptr [edi*4 + {STKARR+0xa*0x2000}], ecx'),   # fn 0x5bcdc0
    (0x5bceaa, 'mov eax, dword ptr [esp + eax*4 + 0x10]', 'mov eax, dword ptr [eax*4 + {STKARR+0xa*0x2000}]'),   # fn 0x5bcdc0
    (0x5cd3ed, 'lea edi, [esp + 0x14]', 'mov edi, {STKARR+0xb*0x2000}'),   # fn 0x5cd3b0
    (0x5cd459, 'mov dword ptr [esp + esi*4 + 0x14], edi', 'mov dword ptr [esi*4 + {STKARR+0xb*0x2000}], edi'),   # fn 0x5cd3b0
    (0x5cd4a9, 'mov ecx, dword ptr [esp + eax*4 + 0x14]', 'mov ecx, dword ptr [eax*4 + {STKARR+0xb*0x2000}]'),   # fn 0x5cd3b0
    (0x5e302d, 'lea edi, [esp + 0x80]', 'mov edi, {STKARR+0xc*0x2000}'),   # fn 0x5e2f70
    (0x5e3085, 'mov dword ptr [esp + eax*4 + 0x80], 1', 'mov dword ptr [eax*4 + {STKARR+0xc*0x2000}], 1'),   # fn 0x5e2f70
    (0x5e32c6, 'cmp dword ptr [esp + esi*4 + 0x80], ebx', 'cmp dword ptr [esi*4 + {STKARR+0xc*0x2000}], ebx'),   # fn 0x5e2f70
    (0x5e90fe, 'lea edi, [esp + 0x68]', 'mov edi, {STKARR+0xd*0x2000}'),   # fn 0x5e8e50
    (0x5e9184, 'mov dword ptr [esp + eax*4 + 0x60], edi', 'mov dword ptr [eax*4 + {STKARR+0xd*0x2000}], edi'),   # fn 0x5e8e50
    (0x5e929b, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e9310, 'mov dword ptr [esp + esi*4 + 0x60], ebx', 'mov dword ptr [esi*4 + {STKARR+0xd*0x2000}], ebx'),   # fn 0x5e8e50
    (0x5e9339, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e9342, 'mov dword ptr [esp + esi*4 + 0x60], eax', 'mov dword ptr [esi*4 + {STKARR+0xd*0x2000}], eax'),   # fn 0x5e8e50
    (0x5e9352, 'lea eax, [esp + 0x64]', 'mov eax, {STKARR+0xd*0x2000}'),   # fn 0x5e8e50
    (0x5e947b, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e9489, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e9497, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e94a5, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e94b3, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e94c1, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e94cf, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e94dd, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e94eb, 'mov eax, dword ptr [esp + esi*4 + 0x60]', 'mov eax, dword ptr [esi*4 + {STKARR+0xd*0x2000}]'),   # fn 0x5e8e50
    (0x5e9639, 'lea eax, [esp + 0x60]', 'mov eax, {STKARR+0xd*0x2000}'),   # fn 0x5e8e50
    (0x5e9500, 'lea edi, [esp + 0x108]', 'mov edi, {STKARR+0xe*0x2000}'),   # fn 0x5e8e50
    (0x5e958b, 'mov ecx, dword ptr [esp + edi*4 + 0x108]', 'mov ecx, dword ptr [edi*4 + {STKARR+0xe*0x2000}]'),   # fn 0x5e8e50
    (0x5e9592, 'lea eax, [esp + edi*4 + 0x108]', 'lea eax, [edi*4 + {STKARR+0xe*0x2000}]'),   # fn 0x5e8e50
    (0x5e95c0, 'mov eax, dword ptr [esp + esi*4 + 0x108]', 'mov eax, dword ptr [esi*4 + {STKARR+0xe*0x2000}]'),   # fn 0x5e8e50
    (0x5e963e, 'lea ecx, [esp + 0x10c]', 'mov ecx, {STKARR+0xe*0x2000}'),   # fn 0x5e8e50
    (0x5f9bb3, 'lea edi, [esp + 0x20]', 'mov edi, {STKARR+0xf*0x2000}'),   # fn 0x5f9b60
    (0x5f9c4f, 'lea esi, [esp + esi*4 + 0x24]', 'lea esi, [esi*4 + {STKARR+0xf*0x2000}]'),   # fn 0x5f9b60
    (0x5f9c6e, 'lea edi, [esp + 0x20]', 'mov edi, {STKARR+0xf*0x2000}'),   # fn 0x5f9b60
    (0x5f9cc4, 'mov ecx, dword ptr [esp + esi*4 + 0x20]', 'mov ecx, dword ptr [esi*4 + {STKARR+0xf*0x2000}]'),   # fn 0x5f9b60
    (0x5f9cca, 'mov dword ptr [esp + esi*4 + 0x20], 0', 'mov dword ptr [esi*4 + {STKARR+0xf*0x2000}], 0'),   # fn 0x5f9b60
]
ALLOCS['STKARR'] = 'STKSLOTS*0x2000'
# four of those stores are 4-byte instructions with branch targets both at them and right after them, so no
# 5-byte jump fits: forces.cpp turns them into int3 and performs the store in a vectored exception handler
# (worldmod/src/forces.cpp STACK_TRAPS). They stay out of the cave list.
STACK_TRAP = {0x58d252, 0x5cd459, 0x5e9310, 0x5e9342}
STACK = [r for r in STACK if r[0] not in STACK_TRAP]

# 0x551bd0: 47 x 8 (ruler, value) list on the stack at [esp+0x54], filled by 0x5410a0 and walked through a pointer
# kept by the dialog (0x541080): both address computations -> STKARR slot 16 (the area is reused later in the
# function for other locals, which stay on the stack)
STACK += [
    (0x551cdc, 'lea ecx, [esp + 0x58]', 'mov ecx, {STKARR+0x10*0x2000}'),
    (0x551d14, 'lea edx, [esp + 0x54]', 'mov edx, {STKARR+0x10*0x2000}'),
]

# new-game setup dialog (NewGameJ, vt 0x842de0, one instance on the stack of 0x556d20): 47 x 0x184 per-force
# records at +0x34e8 -> DLGREC (F records). Every reference (class analysis of M7, scratchpad m7l/xp/res_J.pkl,
# plus the stack-relative one in 0x556d20); the M7 displacement patches of these instructions are superseded.
STACK += [
    (0x5565f2, 'add esi, 0x34e8', 'mov esi, {DLGREC}'),
    (0x5513fe, 'add esi, 0x34e8', 'mov esi, {DLGREC}'),
    (0x5541c6, 'lea esi, [edi + 0x34ec]', 'mov esi, {DLGREC+4}'),
    (0x54f445, 'lea ebp, [ecx + 0x364c]', 'mov ebp, {DLGREC+0x164}'),
    (0x556d9d, 'lea ecx, [esp + 0x45ac]', 'mov ecx, {DLGREC}'),
]
ALLOCS['DLGREC'] = '(R+5)*0x184+0x200'

# sites left at Koei's values in stage 1:
#  * the force snapshot object (vt 0x862928, 47 x 0xa0 + int[47], stack instances in 0x622a30 and 0x61c35e) and
#    the dialog that uses it (0x695ae0..0x697c00, 0x6a39f3): bounds stay 47/46, so forces 47+ cannot be picked
#    in that screen (no out-of-range access);
#  * the force-description accessors of the scenario header (42 records of 0x171): Koei allowed ids up to 46
#    (past the 42 records); now only 0..41, other forces get no description.
KEEP_RANGES = [(0x695ae0, 0x697c00)]
KEEP_SITES = {0x6a39f3,
              0x480d6f}     # scenario-header serializer: the 42 force descriptions stay 42 (file and memory)
FIXED = {0x4804c8: '41', 0x4804f8: '41'}

# 0x4ccf2a: sort key of non-regular forces = 0x7fffffd0 + force id; keep the largest key below 2^31
f(0x4ccf2a, 0x7fffffd0, '0x7fffffd0+42-R', 'sort key of non-regular forces (no signed overflow)')

# ======================================================================= stage 2: R up to 249 (F <= 254)
BYTE_OK = {0x482614}           # cmp al, F (unsigned jae): an unsigned byte holds F up to 255

# ---- the force bit sets become F-bit rows (forces.cpp): FMASK (force +0x50), AIM0 / AIM1 (AI force records +0/+8),
# FBITS (flag bitset<47> of the composite 0x9c43e80). Accessors 0x4811b0, 0x4b4f40, 0x5f69a0..0x5f6ae0 and the
# +0x50 serializer call are replaced in forces.cpp / worldmod.cpp; the rest is patched here.
ROW = '((R+36)/32)*4'              # bytes per bit-set row (W dwords, W = (F+31)/32)
FIELD = [r for r in FIELD if r[0] != 0x5f86f0]
REWRITE.append((0x5f86ea, 11, 'imul eax, eax, {' + ROW + '}; add eax, {AIM0}',
                'inline test of AI force record bit set +0 -> AIM0 row'))
# AI sub-object serializer: the two 2-dword loops over a record's bit sets -> W dwords each from AIM0 / AIM1
# (ebp = 1 afterwards, as the second loop left it)
REWRITE.append((0x479815, 0x4798c8 - 0x479815,
                'mov eax, dword ptr [esp + 0x14]; push eax; push esi; mov eax, {SER_AIM}; call eax; add esp, 8; mov ebp, 1',
                'AI serializer: force record bit sets -> AIM0 / AIM1 rows'))
# flag bitset<47> (only instance: composite +0x58): test / set on FBITS (like CITYBITS in M7)
REWRITE.append((0x680190, 0x6801e0 - 0x680190,
                'mov ecx, dword ptr [esp + 4]; cmp ecx, {R+5}; jae L0; bt dword ptr [{FBITS}], ecx; sbb eax, eax; '
                'neg eax; ret 4; L0: xor eax, eax; ret 4', 'flag bitset<F>: test on FBITS'))
REWRITE.append((0x6801e0, 0x680234 - 0x6801e0,
                'mov ecx, dword ptr [esp + 4]; cmp ecx, {R+5}; jae L0; mov eax, dword ptr [esp + 8]; '
                'test byte ptr [eax], 1; je L1; bts dword ptr [{FBITS}], ecx; ret 8; L1: btr dword ptr [{FBITS}], ecx; '
                'L0: ret 8', 'flag bitset<F>: set on FBITS'))

# (va, original, replacement) re-encoded in caves
CAVE_TEXT = [
    # consistency check 0x482050: the two bit-set row pointers
    (0x48228a, 'add edi, 0x50', 'push eax; push ecx; push edx; push edi; mov eax, {FROWPTR}; call eax; add esp, 4; mov edi, eax; '
                                'pop edx; pop ecx; pop eax'),
    (0x4822a5, 'lea eax, [esi + 0x50]', 'push ecx; push edx; push esi; mov eax, {FROWPTR}; call eax; add esp, 4; pop edx; pop ecx'),
    # attribute codes "base + force id" (decoder 0x4c4260, blocks of 47): forces 47+ get no code (-1)
    (0x4c22a8, 'add eax, 0xe0', 'cmp eax, 0x2f; jl K; or eax, 0xffffffff; jmp D; K: add eax, 0xe0; D: nop'),
    (0x4c22d3, 'add eax, 0xb1', 'cmp eax, 0x2f; jl K; or eax, 0xffffffff; jmp D; K: add eax, 0xb1; D: nop'),
    (0x4c22fe, 'add eax, 0x82', 'cmp eax, 0x2f; jl K; or eax, 0xffffffff; jmp D; K: add eax, 0x82; D: nop'),
    (0x4c2386, 'add eax, 0xe0', 'cmp eax, 0x2f; jl K; or eax, 0xffffffff; jmp D; K: add eax, 0xe0; D: nop'),
    (0x4c2398, 'add eax, 0xb1', 'cmp eax, 0x2f; jl K; or eax, 0xffffffff; jmp D; K: add eax, 0xb1; D: nop'),
    (0x4c23aa, 'add eax, 0x82', 'cmp eax, 0x2f; jl K; or eax, 0xffffffff; jmp D; K: add eax, 0x82; D: nop'),
    (0x5bd26c, 'add eax, 0x82', 'cmp eax, 0x2f; jl K; or ecx, 0xffffffff; or edx, 0xffffffff; or eax, 0xffffffff; '
                                'jmp D; K: add eax, 0x82; D: nop'),
]

# byte-sized force / corps ids in the streams: unsigned byte, 0xff = none (forces.cpp limit F <= 254), so the file
# formats stay as they are (Koei's values 0..46 and -1 read the same)
for va, what in [(0x47c996, 'city +0x38 corps'), (0x47e4f1, 'corps +4 force'), (0x481e0e, 'force +0x94 force'),
                 (0x4832e3, 'world header turn order (force ids)'), (0x4881b8, 'building +0xc owner force'),
                 (0x48b8b7, 'person +0x94 corps'), (0x48bb07, 'person +0x160 force'),
                 (0x48de22, 'gate/port +0x20 corps'), (0x497362, 'unit +0x44 force')]:
    f(va, (0x48a970 - (va + 5)) & 0xffffffff, f'SER_U8ID-{va + 5:#x}', f'stream id field {what}: u8 (0xff = none)')
# byte-sized force ids read as signed bytes in memory (AI base / unit records): movsx -> movzx (0xff = none is then
# 255, past every bound, the same branch as -1 took)
for va in (0x479483, 0x479502, 0x5df095):
    f(va, 0xbe, '0xb6', 'AI record force byte: movsx -> movzx', size=1)
