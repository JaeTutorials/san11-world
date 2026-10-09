# M3 (China offset) patch lines for worldmod_terrain.txt
import os
import struct
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
exe = open(os.path.join(PROJ, 'backup', 'san11pk.exe.orig'), 'rb').read()
def at(va, n): return exe[va - 0x400000: va - 0x400000 + n]
out = []
for i in range(4):
    base = 0x79C6E4 + 12 * i
    lo, hi = struct.unpack('<hh', at(base, 4))
    out.append(f'{base:08x} 0 2 {at(base, 2).hex()} CHLO+{lo} ; dike table entry {i}: lo')
    out.append(f'{base + 2:08x} 0 2 {at(base + 2, 2).hex()} CHHI+{hi} ; dike table entry {i}: hi')
for va, axis, sym in ((0x57ee0f, 'x', 'CHLO'), (0x57ee1b, 'z', 'CHHI')):
    b = at(va, 8)
    assert b[4:] == struct.pack('<f', 2560.0)
    out.append(f'{va:08x} 4 4 {b.hex()} f:20*{sym}+2560 ; opening camera target {axis}: centre of the China block')
open('m4b/m3_patches.txt', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
