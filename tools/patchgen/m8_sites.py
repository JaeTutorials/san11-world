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
