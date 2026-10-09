"""add_force.py - add a new force (势力) with its own officers and cities to a converted scenario.

    python tools/add_force.py SPEC.json SCEN.s11 [SCEN.s11 ...] [--cities-json bases_cities.json]

SPEC (example: tools/forces/europe.json):
  force       free force id 0..41 (ruler -1 in the scenario)
  corps       free corps (军团) id 0..41
  kokugo      国号 record (type 14) to rename and give the force, e.g. 42 (Koei's placeholders 42..83); -1 = none
  name        国号 name (Big5, <= 2 characters)
  color       force colour (Koei uses 0..41; normally the force id)
  desc        text for the scenario's force description slot (shown when choosing a force); stars = its first byte
  cities      [{"city": id or name, "troops", "gold", "food"}]; they must be unowned in the scenario
  officers    [{"slot": person id, "sei", "mei", "face", "stats": [统率 武力 智力 政治 魅力],
               "apt": [枪 戟 弩 骑 兵器 水军] (0..3 = C..S), "city": id or name, "ruler": true}]
              slots must be Koei's unused placeholders (身分 0xff, no affiliation): 670..699 史實01..30.
              Not 700..799: the game treats those ids as special NPCs (tribe chiefs, bandits; 0x489ce0) and leaves
              them out of every officer list. 800..849 (古代) are 古武将 slots (0x489c80).

Record layouts (scenario stream, decoded from the serialisers; see M7_LAYOUT.md §8 and COORDS.md §2):
  (converted scenarios have wide ids, convert_scen.py: the id fields marked i16* were i8 in Koei's files)
  force 73 B (0x481d30): i16 ruler +4 | i16 strategist +8 | u8[47] relations +0xc | i8 rank +0x3c |
      i8 国号 +0x40 | i8 colour +0x44 | i8 target type +0x48 | i16* target +0x4c | u32[2] +0x50 | u32[2] +0x58
  corps 10 B (0x47e4c0): i8 force +4 | i8 number in force +8 | i16 leader +0xc | i8 +0x10 | i16* +0x14 | i8 +0x18 | i16* +0x1c
  person 152 B (0x48b760): char[5] 姓, char[5] 名, char[5] 字, char[25] reading, 13 B, i16 face @53, i8 sex,
      i16 appearance year/birth/death @56, i8, i16 blood/father/mother @63, u8, i16 spouse/sworn @70, u8 相性 @74,
      i16[5] liked @75, i16[5] disliked @85, i8 corps @95 (+0x94), i16 affiliation @96, i16 location @98,
      i8 身分 @100 (0 君主 1 都督 3 一般 6 未登场 7 未发现 0xff none), i8 @101, i16 @102, u8 loyalty @104,
      u16 merit @105, i8[6] aptitudes @107, u8[5] stats @113, i8[5] growth @118, i8[12] @123 (特技 @124), 17 B
  city 81 B (0x47c900): i8 corps +0x38 | u32 +0x3c | u32 troops, gold, food @5 | u32[12] equipment @17 | ...
  building 18 B: u8 type | i8 force @1 | ...
  type 14 (国号) 87 B: char name @0 ... ; 42..83 are Koei's unnamed placeholders
The force has no capital field: the game takes the ruler's city (person +0x98).
Each file is patched in place; the original is kept once as FILE.before_force.
"""
import argparse
import json
import shutil
import struct
import sys
from pathlib import Path

from convert_scen import ConvError, scen_layout

HERE = Path(__file__).resolve().parent
PERSON = 152
TEMPLATE_PERSON = 156      # 嚴綱: a plain officer (no 特技) whose remaining bytes the new officers copy
TEMPLATE_CITY = 1          # 北平: equipment / order values for the force's cities


def big5(s, n):
    b = s.encode('cp950')
    if len(b) > n - 1:
        raise ConvError(f'{s!r} is {len(b)} bytes, the field holds {n - 1} + NUL')
    return b + bytes(n - len(b))


def city_ids(cities_json):
    names = {}
    koei = json.loads((HERE.parent / 'data' / 'cities_georef.json').read_text(encoding='utf-8'))
    for k in koei:
        names[k['name']] = k['id']
    if cities_json:
        for c in json.loads(Path(cities_json).read_text(encoding='utf-8'))['new']:
            names[c['name']] = c['id']
    return names


def layout_of(D):
    """find C, N from the file size (scenario: 170010 + 18 (N-87) + 81 (C-42), N = C + 45)"""
    for C in range(42, 1001):
        L, end = scen_layout(C, C + 45, wide=True)
        if end == len(D):
            return L, C, C + 45
    raise ConvError(f'size {len(D)} is not a (converted) scenario')


def recs(D, L, name):
    o, c, s = L[name]
    return o, c, s


def patch(D, spec, names):
    D = bytearray(D)
    L, C, N = layout_of(D)

    def at(name, i):
        o, c, s = L[name]
        if not 0 <= i < c:
            raise ConvError(f'{name} {i} out of range')
        return o + s * i

    def cid(x):
        v = names.get(x, x) if isinstance(x, str) else x
        if not isinstance(v, int) or not 0 <= v < C:
            raise ConvError(f'unknown city {x!r}')
        return v

    fid, kid, color = spec['force'], spec['corps'], spec.get('color', spec['force'])
    fo = at('force', fid)
    if struct.unpack_from('<h', D, fo)[0] != -1:
        raise ConvError(f'force {fid} already has a ruler')
    ko = at('army', kid)
    if D[ko] != 0xff:
        raise ConvError(f'corps {kid} is in use')
    offs = spec['officers']
    rulers = [o for o in offs if o.get('ruler')]
    if len(rulers) != 1:
        raise ConvError('exactly one officer must be the ruler')
    ruler = rulers[0]['slot']
    cities = [cid(c['city']) for c in spec['cities']]
    for c in cities:
        bo = at('building', c)
        if D[bo + 1] != 0xff or D[at('city', c)] != 0xff:
            raise ConvError(f'city {c} is owned in this scenario')
    tp = bytes(D[at('person', TEMPLATE_PERSON):at('person', TEMPLATE_PERSON) + PERSON])
    tc = bytes(D[at('city', TEMPLATE_CITY):at('city', TEMPLATE_CITY) + 81])

    # officers
    for o in offs:
        po = at('person', o['slot'])
        if D[po + 100] != 0xff or struct.unpack_from('<h', D, po + 96)[0] != -1:
            raise ConvError(f"person {o['slot']} is not an unused placeholder")
        if 700 <= o['slot'] <= 849:
            raise ConvError(f"person {o['slot']}: ids 700..849 are special NPC / 古武将 slots, use 670..699")
        c = cid(o['city'])
        if c not in cities:
            raise ConvError(f"officer {o['sei']}{o['mei']}: city {c} is not one of the force's cities")
        r = bytearray(tp)
        r[0:5] = big5(o['sei'], 5); r[5:10] = big5(o['mei'], 5); r[10:15] = bytes(5)
        r[15:40] = bytes(25)                                   # reading: none
        struct.pack_into('<h', r, 53, o['face'])
        r[55] = o.get('sex', 0)
        birth = o.get('birth', 150)
        struct.pack_into('<hhh', r, 56, o.get('appear', birth + 16), birth, o.get('death', 240))
        struct.pack_into('<hhh', r, 63, o['slot'], -1, -1)    # blood line = self, no parents
        struct.pack_into('<hh', r, 70, -1, -1)                # no spouse, no sworn brother
        r[74] = o.get('aishou', 75)
        struct.pack_into('<5h', r, 75, -1, -1, -1, -1, -1)    # liked
        struct.pack_into('<5h', r, 85, -1, -1, -1, -1, -1)    # disliked
        r[95] = kid
        struct.pack_into('<hh', r, 96, c, c)
        r[100] = 0 if o.get('ruler') else 3
        r[104] = 100
        struct.pack_into('<H', r, 105, 10000 if o.get('ruler') else 3000)
        r[107:113] = bytes(o['apt'])
        r[113:118] = bytes(o['stats'])
        r[124] = o.get('skill', 0xff)                          # 特技 (+0xe8), none
        if o.get('ruler'):
            r[148] = 200                                       # +0x124 (200 for Koei's rulers)
        D[po:po + PERSON] = r

    # corps: force, first corps of the force, leader = ruler
    D[ko:ko + 10] = bytes([fid, 1]) + struct.pack('<h', ruler) + bytes([0]) + struct.pack('<h', 0x1c) + bytes([0]) + struct.pack('<h', -1)

    # force
    rel = [50] * 47
    rel[fid] = 100
    for k in range(42, 47):
        rel[k] = 0                                             # tribes and bandits, as for Koei's forces
    kok = spec.get('kokugo', -1)
    f = struct.pack('<hh', ruler, -1) + bytes(rel) + bytes([9, kok & 0xff, color, 0]) + struct.pack('<h', -1) + bytes(16)
    assert len(f) == 73
    D[fo:fo + 73] = f
    for k in range(47):                                        # everybody else's view of the new force
        if k != fid:
            o2 = at('force', k)
            if struct.unpack_from('<h', D, o2)[0] != -1 and k < 42:
                D[o2 + 4 + fid] = 50

    # 国号
    if kok >= 0:
        to = at('type14', kok)
        D[to:to + 5] = big5(spec['name'], 5)

    # force description (scenario selection)
    if spec.get('desc') and fid < 42:
        do = L['force_desc'][0] + 369 * fid
        D[do] = spec.get('stars', 3)
        D[do + 1:do + 369] = big5(spec['desc'], 368)

    # cities
    for c, x in zip(cities, spec['cities']):
        D[at('building', c) + 1] = fid
        co = at('city', c)
        r = bytearray(D[co:co + 81])
        r[0] = kid
        struct.pack_into('<III', r, 5, x.get('troops', 10000), x.get('gold', 2000), x.get('food', 30000))
        r[17:65] = tc[17:65]                                   # equipment as in 北平
        r[73:75] = tc[73:75]
        D[co:co + 81] = r
    return bytes(D), C, N


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('spec')
    ap.add_argument('scen', nargs='+')
    ap.add_argument('--cities-json', help='bases_cities.json, to name new cities in the spec')
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding='utf-8'))
    names = city_ids(a.cities_json)
    try:
        for p in map(Path, a.scen):
            bak = p.with_name(p.name + '.before_force')
            src = bak if bak.exists() else p
            E, C, N = patch(src.read_bytes(), spec, names)
            if not bak.exists():
                shutil.copy2(p, bak)
            p.write_bytes(E)
            print(f'{p.name}: force {spec["force"]} ({spec.get("name", "")}) with {len(spec["officers"])} officers '
                  f'in {len(spec["cities"])} cities (C={C}); original kept as {bak.name}')
    except ConvError as e:
        print('error:', e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
