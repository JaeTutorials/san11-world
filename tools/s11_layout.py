"""s11_layout.py - byte layout of San11PK .s11 world files and every hex-position field in them.

Covers (see mapmod_re/COORDS.md):
  * scenario files  media/scenario/Scen%03d.s11   (stream kind 0x16; also 2/3/0x17)
  * save files      SaveData/Save%03d.s11         (kind 0x1a written by 0x43bb90; 6/0x11 assumed identical)
  * stage files     media/script/data/TS%06d.s11  (kind 0x0c / 0x1b, save-format world)
The master file Scenario.s11 (kind 0x18) holds no positions.

A position is two int16 in the file: lo ("y", array row, grows east) then hi ("x", grows south).
In memory it is one dword (lo | hi<<16).  (-1,-1) = invalid / unused slot: never translate it.

usage:  python s11_layout.py FILE [FILE...]      -> prints layout + position summary (+terrain check)
        python s11_layout.py --dump FILE         -> one line per valid position field
Only reads files.
"""
import struct, sys, os, collections

HDR = 90                      # common file header (0x43b330)
KIND_SCEN = {2, 3, 0x16, 0x17}
KIND_SAVE = {6, 0x11, 0x1a}   # save loader 0x43ba50, save-info header 345 B
KIND_TS = {0x0c, 0x1b}        # TS loader 0x43bc60, TS header 256 B
KIND_MASTER = {4, 0x18}

def header(D):
    bom, kind = struct.unpack_from('<II', D, 0)
    v1, v2, h24, xor, seed = struct.unpack_from('<5I', D, 0x18)
    return dict(kind=kind, v1=v1, v2=v2, xor=xor, seed=seed, magic=D[8:0x18].split(b'\0')[0])

def scen_sections():
    """Scen*.s11: (name, file offset, count, record size)."""
    s = [('filehdr', 0, 1, 90),
         ('scen_info', 90, 1, 595),          # 0x480ca0: i8,i16 year,i8,i8,char17,char363, i8[42] owner @0x1db, pos[42] @0x205
         ('force_desc', 685, 42, 369),       # 0x480d50 tail: 42 x (u8 + char[368])
         ('world_head', 16183, 1, 11),       # 0x483120 common part
         ('building', 16194, 87, 18),        # 0x488160, only ids 0..86 in scenario streams
         ('person', 17760, 850, 152),        # 0x48b760, ids < 850 only
         ('item', 146960, 100, 57),
         ('force', 152660, 47, 72),
         ('army', 156044, 47, 8),
         ('city', 156420, 42, 81),
         ('gate', 159822, 10, 64),
         ('port', 160462, 35, 64),
         ('type14', 162702, 84, 87)]         # 84 x 0x68 objects (state titles)
    return s, 170010

def world_save_sections(v1, v2, base):
    """Save-format world (kinds 6/0xc/0x11/0x1a/0x1b) starting at file offset `base`."""
    F = 72 - (0 if v1 >= 1 else 4) + 59 + ((58 + (24 if v2 > 0 else 0)) if v1 >= 1 else 0)
    A = 8 + (2 if v1 >= 1 else 4) + 4 + 1
    # type 18 (0x480040) + its tail 0x680600 (0x9c43e80, 256 B: derived from TS file sizes)
    T18 = 8 + 256 + 4096 + 47 * 4608 + 4 + 1023 + (2050 if (v1 >= 1 and v2 > 1) else 0) + 4 + 256
    order = [('world_head', 1, 2212), ('building', 16384, 18), ('person', 1100, 203), ('item', 100, 57),
             ('force', 47, F), ('army', 47, A), ('city', 42, 107), ('gate', 10, 70), ('port', 35, 70),
             ('type14', 84, 87), ('unit', 1000, 98), ('new_person', 150, 0x247), ('obj_1ba5ea', 50, 0x109),
             ('type18', 1, T18), ('ai', 1, 20020), ('hexmap', 40000, 4)]
    o = base; out = []
    for n, c, s in order:
        out.append((n, o, c, s)); o += c * s
    return out, o

def sections(D):
    h = header(D)
    k = h['kind']
    if k in KIND_SCEN:
        return h, scen_sections()
    if k in KIND_SAVE:
        return h, world_save_sections(h['v1'], h['v2'], HDR + 345)   # save-info 0x480e00: pos[42] at +177
    if k in KIND_TS:
        return h, world_save_sections(h['v1'], h['v2'], HDR + 256)   # TS header 0x480b50
    raise ValueError('kind %#x has no world/position data' % k)

def positions(D):
    """Yield (file_offset_of_lo, field, index, lo, hi) for every position field (valid or not)."""
    h, (secs, end) = sections(D)
    S = {n: (o, c, s) for n, o, c, s in secs}
    def pair(off): return struct.unpack_from('<hh', D, off)
    if h['kind'] in KIND_SCEN:
        for i in range(42):
            off = 0x205 + 4 * i; yield (off, 'scen_info.city_pos', i) + pair(off)
    if h['kind'] in KIND_SAVE:
        for i in range(42):
            off = HDR + 177 + 4 * i; yield (off, 'save_info.city_pos', i) + pair(off)
    o, c, s = S['building']
    for i in range(c):
        off = o + s * i + 13; yield (off, 'building+0x1e', i) + pair(off)
    if 'unit' in S:
        o, c, s = S['unit']
        for i in range(c):
            off = o + s * i + 24; yield (off, 'unit+0x3c(pos)', i) + pair(off)
            off = o + s * i + 28; yield (off, 'unit+0x38(target)', i) + pair(off)

def shex_terrain():
    try:
        B = os.path.join(os.path.dirname(__file__), '..', '..', 'Media', 'san11pkres.bin')
        f = open(B, 'rb'); n = struct.unpack('<I', f.read(16)[4:8])[0]
        ent = [struct.unpack('<II', f.read(8)) for _ in range(n)]
        o, s = ent[0x12b7]; f.seek(o); d = f.read(s)
        return d[8:] if d[:8] == b'SHEX0008' else None
    except OSError:
        return None

def main(argv):
    dump = '--dump' in argv
    files = [a for a in argv if a != '--dump']
    sh = shex_terrain()
    for fn in files:
        D = open(fn, 'rb').read()
        h, (secs, end) = sections(D)
        print('%s: kind %#x v%d/%d xor=%d size %d (layout end %d)%s' % (
            os.path.basename(fn), h['kind'], h['v1'], h['v2'], h['xor'], len(D), end,
            '' if end == len(D) else '  <-- SIZE MISMATCH'))
        if h['xor']:
            print('  XOR keystream enabled: values below are encrypted'); continue
        if not dump:
            for n, o, c, s in secs: print('  %-12s @%#08x  %5d x %d' % (n, o, c, s))
        cnt = collections.Counter(); terr = collections.Counter()
        for off, what, i, lo, hi in positions(D):
            ok = 0 <= lo < 200 and 0 <= hi < 200
            cnt[(what, ok)] += 1
            if ok and sh: terr[(what, sh[(lo * 200 + hi) * 11])] += 1
            if dump and ok: print('%#08x %-20s %5d  lo=%3d hi=%3d' % (off, what, i, lo, hi))
        if not dump:
            for (what, ok), v in sorted(cnt.items()): print('  %-20s %s %d' % (what, 'valid ' if ok else 'invalid', v))
            if sh:
                b = collections.Counter({t: v for (w, t), v in terr.items() if w == 'building+0x1e'})
                print('  terrain under valid building positions:', dict(sorted(b.items())))

if __name__ == '__main__':
    main(sys.argv[1:])
