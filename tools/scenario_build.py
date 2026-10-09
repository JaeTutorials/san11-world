"""剧本编译器：用一个 JSON 文件描述你的剧本改动（新势力、新武将、城市归属、剧本标题……），
写进世界版的剧本文件 Scen*.s11。

    python tools/scenario_build.py scenarios/europe_184.json --data C:/San11PK/world_custom

--data 是世界数据目录（san11kit.py world 生成的那个，里面有 scenario/ 和 bases_cities.json）。
第一次运行时把原始剧本复制到 <data>/scenario_base/，以后每次都从那份干净的副本重新生成，
所以 JSON 改了以后直接再运行一次就行，不会越改越乱。

JSON 格式（完整说明见 docs/剧本制作.md，例子见 scenarios/ 目录）：
{
  "base": 0,                          // 在哪个原版剧本上改：0 = 184年 黄巾之乱，1 = 190年 反董卓联合军……（见 --list-scenarios）
  "title": "欧亚风云",                 // 可选：剧本标题（最多 8 个汉字）
  "description": "……",               // 可选：剧本说明
  "forces": [ {                       // 新势力，可以有多个
      "name": "歐洲",                  // 国号（1~2 个字）
      "ruler": "凱撒",                 // 君主：下面 officers 里的一个名字
      "color": 12,                     // 可选：势力颜色编号 0~54，不写就自动选一个没人用的
      "stars": 3, "intro": "……",       // 可选：选势力画面的难度星级和介绍文字
      "cities": [ {"city": "羅馬", "troops": 20000, "gold": 5000, "food": 60000} ],
      "officers": [ {"name": "凱撒", "city": "羅馬", "stats": [95,78,92,90,96], "apt": [3,2,2,3,2,1],
                     "face": 680, "sex": 0, "birth": 150} ],
      "existing_officers": [ {"name": "趙雲", "city": "羅馬"} ],   // 可选：把还没登场或在野的原版武将拉进来
      "relations": {"馬騰": 80}        // 可选：和其他势力（按君主名）的友好度 0~100
  } ]
}
名字一律用繁体字（游戏用 Big5 编码）。新武将最多 30 个（光荣留的空位「史實01~30」）。
"""
import argparse
import json
import shutil
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from convert_scen import scen_layout  # noqa: E402

PERSON = 152
TEMPLATE_PERSON = 156          # 嚴綱：没有特技的普通武将，新武将其余字节照抄他
TEMPLATE_CITY = 1              # 北平：新势力城市的兵装照抄这里
FREE_SLOTS = range(670, 700)   # 「史實01~30」：光荣留的空武将槽（700~799 是异族头目等特殊人物，列表里不显示）
KOKUGO_FREE = range(42, 84)    # 国号表里光荣留的空位
DEFAULT_FACES = [680, 678, 682, 681, 679, 683, 684, 685]
COMPOUND = ("諸葛", "司馬", "夏侯", "公孫", "太史", "皇甫", "歐陽", "上官", "令狐", "東方", "司徒", "鍾離", "宇文", "慕容")
SCENARIOS = ["184年 黃巾之亂", "190年 反董卓聯合軍", "194年 群雄割據", "200年 官渡之戰", "207年 三顧茅廬",
             "211年 劉備入蜀", "225年 南蠻征伐", "251年 英雄集結", "198年 呂布討伐戰", "203年 袁家之戰",
             "217年 漢中爭奪戰", "187年 何進包圍網", "191年 局勢掌控者", "251年 女流之戰"]
SCEN_FILES = ["Scen000.s11", "SCEN001.S11", "SCEN002.S11", "SCEN003.S11", "SCEN004.S11", "SCEN005.S11",
              "SCEN006.S11", "SCEN007.S11", "Scen008.s11", "Scen009.s11", "Scen010.s11", "Scen011.s11",
              "Scen012.s11", "Scen013.s11"]
STATUS = {0: "君主", 1: "都督", 2: "太守", 3: "一般", 4: "在野", 5: "俘虜", 6: "未登場", 7: "未發現", 255: "（空）"}


class BuildError(Exception):
    pass


def big5(text, size, what):
    try:
        b = text.encode("cp950")
    except UnicodeEncodeError:
        bad = "".join(ch for ch in text if not _enc_ok(ch))
        raise BuildError(f"{what}「{text}」里的「{bad}」不在繁体 Big5 字库里：请改用繁体字（例如 凯→凱、罗→羅）")
    if len(b) > size - 1:
        raise BuildError(f"{what}「{text}」太长：最多 {(size - 1) // 2} 个汉字")
    return b + bytes(size - len(b))


def _enc_ok(ch):
    try:
        ch.encode("cp950")
        return True
    except UnicodeEncodeError:
        return False


def split_name(o):
    if "sei" in o and "mei" in o:
        return o["sei"], o["mei"]
    name = o["name"]
    for c in COMPOUND:
        if name.startswith(c) and len(name) > 2:
            return c, name[2:]
    return name[:1], name[1:]


class Scenario:
    def __init__(self, data, data_dir):
        self.D = bytearray(data)
        mark = bytes(data[0x2c:0x30])           # "WIDE", or "WF" + u16 regular forces (M8_FORCES.md)
        self.R = struct.unpack("<H", mark[2:])[0] if mark[:2] == b"WF" else 42
        self.F = self.R + 5
        for C in range(42, 1001):
            L, end = scen_layout(C, C + 45, wide=True, R=self.R)
            if end == len(data):
                self.L, self.C, self.N = L, C, C + 45
                break
        else:
            raise BuildError("这个文件不是世界版剧本（请先运行 san11kit.py world 生成数据目录）")
        self.cities = self._city_names(data_dir)

    def _city_names(self, data_dir):
        names = {}
        for k in json.loads((HERE.parent / "data" / "cities_georef.json").read_text(encoding="utf-8")):
            names[k["name"]] = k["id"]
        bc = Path(data_dir) / "bases_cities.json"
        if bc.exists():
            for c in json.loads(bc.read_text(encoding="utf-8"))["new"]:
                names[c["name"]] = c["id"]
        return names

    def at(self, sect, i):
        o, c, s = self.L[sect]
        if not 0 <= i < c:
            raise BuildError(f"{sect} 编号 {i} 超出范围")
        return o + s * i

    def i16(self, off):
        return struct.unpack_from("<h", self.D, off)[0]

    def person_name(self, i):
        o = self.at("person", i)
        return (bytes(self.D[o:o + 5]).split(b"\0")[0] + bytes(self.D[o + 5:o + 10]).split(b"\0")[0]).decode("cp950", "replace")

    def person_by_name(self, name):
        hits = [i for i in range(850) if self.person_name(i) == name]
        if not hits:
            raise BuildError(f"剧本里找不到武将「{name}」（名字要用繁体，和游戏里一样）")
        return hits[0]

    def city_id(self, x):
        if isinstance(x, int):
            v = x
        elif x in self.cities:
            v = self.cities[x]
        else:
            raise BuildError(f"找不到城市「{x}」：请用 san11kit.py cities 查看城市名（繁体）")
        if not 0 <= v < self.C:
            raise BuildError(f"城市编号 {v} 超出范围 0~{self.C - 1}")
        return v

    def force_ruler(self, f):
        return self.i16(self.at("force", f))

    def used_forces(self):
        return [f for f in range(self.R) if self.force_ruler(f) != -1]


def build(spec, scn):
    D, at = scn.D, scn.at
    log = []
    # ---- scenario header: title, description
    if "title" in spec:
        D[0x5F:0x5F + 17] = big5(spec["title"], 17, "剧本标题")
    if "description" in spec:
        D[0x70:0x70 + 363] = big5(spec["description"], 363, "剧本说明")
    used_slots = set()
    tp = bytes(D[at("person", TEMPLATE_PERSON):at("person", TEMPLATE_PERSON) + PERSON])
    tc = bytes(D[at("city", TEMPLATE_CITY):at("city", TEMPLATE_CITY) + 81])
    F, R = scn.F, scn.R
    used_kokugo = {D[at("force", f) + 4 + F + 1] for f in range(F) if scn.force_ruler(f) != -1}
    used_colors = {D[at("force", f) + 4 + F + 2] for f in range(F) if scn.force_ruler(f) != -1}
    created = []
    for fs in spec.get("forces", []):
        fname = fs.get("name", "?")
        # ---- ids: force, corps, 国号, colour
        fid = next((f for f in range(R) if scn.force_ruler(f) == -1), None)
        kid = next((k for k in range(R) if D[at("army", k)] == 0xff), None)
        kok = next((k for k in KOKUGO_FREE if k not in used_kokugo), None)
        if fid is None or kid is None or kok is None:
            raise BuildError(f"势力已满：这个剧本最多 {R} 个常规势力（project.json 的 forces 可以调大，最大 59）")
        used_kokugo.add(kok)
        color = fs.get("color")
        if color is None:
            color = next(c for c in range(55) if c not in used_colors)
        if not 0 <= color <= 54:
            raise BuildError(f"势力「{fname}」的颜色 {color} 不在 0~54 之间")
        used_colors.add(color)
        # ---- cities
        cities = []
        for cs in fs.get("cities", []):
            c = scn.city_id(cs["city"])
            if D[at("building", c) + 1] != 0xff or D[at("city", c)] != 0xff:
                raise BuildError(f"城市「{cs['city']}」在这个剧本里已经有主人了：新势力只能占无主的城")
            cities.append((c, cs))
        if not cities:
            raise BuildError(f"势力「{fname}」至少要有一座城")
        city_ids = [c for c, _ in cities]

        def officer_city(o, who):
            c = scn.city_id(o["city"]) if "city" in o else city_ids[0]
            if c not in city_ids:
                raise BuildError(f"武将「{who}」所在的城「{o.get('city')}」不是势力「{fname}」的城")
            return c
        # ---- new officers
        members = []                     # (slot, name)
        for n, o in enumerate(fs.get("officers", [])):
            sei, mei = split_name(o)
            who = sei + mei
            slot = o.get("slot")
            if slot is None:
                slot = next((s for s in FREE_SLOTS if s not in used_slots and
                             D[at("person", s) + 100] == 0xff and scn.i16(at("person", s) + 96) == -1), None)
                if slot is None:
                    raise BuildError("新武将的空位用完了：一个剧本最多 30 个新武将（可以改用 existing_officers 拉原版武将）")
            elif 700 <= slot < 850:
                raise BuildError(f"武将「{who}」：700~849 号是异族头目等特殊人物和古武将，在武将列表里不显示")
            used_slots.add(slot)
            c = officer_city(o, who)
            stats = o.get("stats", [60, 60, 60, 60, 60])
            apt = o.get("apt", [1, 1, 1, 1, 1, 1])
            if len(stats) != 5 or not all(1 <= v <= 120 for v in stats):
                raise BuildError(f"武将「{who}」的 stats 要写 5 个 1~120 的数：统率、武力、智力、政治、魅力")
            if len(apt) != 6 or not all(0 <= v <= 3 for v in apt):
                raise BuildError(f"武将「{who}」的 apt 要写 6 个 0~3 的数（0=C 1=B 2=A 3=S）：枪、戟、弩、骑、兵器、水军")
            r = bytearray(tp)
            r[0:5] = big5(sei, 5, "姓"); r[5:10] = big5(mei, 5, "名"); r[10:15] = bytes(5)
            r[15:40] = bytes(25)
            struct.pack_into("<h", r, 53, o.get("face", DEFAULT_FACES[n % len(DEFAULT_FACES)]))
            r[55] = o.get("sex", 0)
            birth = o.get("birth", 150)
            struct.pack_into("<hhh", r, 56, o.get("appear", birth + 16), birth, o.get("death", 240))
            struct.pack_into("<hhh", r, 63, slot, -1, -1)
            struct.pack_into("<hh", r, 70, -1, -1)
            r[74] = o.get("aishou", 75)
            struct.pack_into("<5h", r, 75, -1, -1, -1, -1, -1)
            struct.pack_into("<5h", r, 85, -1, -1, -1, -1, -1)
            r[95] = kid
            struct.pack_into("<hh", r, 96, c, c)
            r[100] = 3
            r[104] = o.get("loyalty", 100)
            struct.pack_into("<H", r, 105, 3000)
            r[107:113] = bytes(apt)
            r[113:118] = bytes(stats)
            r[124] = o.get("skill", 0xff)
            D[at("person", slot):at("person", slot) + PERSON] = r
            members.append((slot, who))
        # ---- existing Koei officers (not yet appeared, or free)
        for o in fs.get("existing_officers", []):
            i = scn.person_by_name(o["name"])
            po = at("person", i)
            st = D[po + 100]
            if st not in (4, 6, 7):
                raise BuildError(f"原版武将「{o['name']}」在这个剧本里是「{STATUS.get(st, st)}」：只能拉在野、未登场或未发现的武将")
            c = officer_city(o, o["name"])
            D[po + 95] = kid
            struct.pack_into("<hh", D, po + 96, c, c)
            D[po + 100] = 3
            D[po + 104] = o.get("loyalty", 100)
            year = struct.unpack_from("<h", D, 0x5B)[0]
            if struct.unpack_from("<h", D, po + 56)[0] > year:
                struct.pack_into("<h", D, po + 56, year)                 # appears now
            members.append((i, o["name"]))
        # ---- ruler
        ruler_name = fs.get("ruler") or (members[0][1] if members else None)
        ruler = next((s for s, nm in members if nm == ruler_name), None)
        if ruler is None:
            raise BuildError(f"势力「{fname}」的君主「{ruler_name}」必须是它自己的 officers 或 existing_officers 里的一个")
        D[at("person", ruler) + 100] = 0
        struct.pack_into("<H", D, at("person", ruler) + 105, 10000)
        D[at("person", ruler) + 148] = 200
        # ---- corps, force, 国号, description
        D[at("army", kid):at("army", kid) + 10] = (bytes([fid, 1]) + struct.pack("<h", ruler) + bytes([0]) +
                                                    struct.pack("<h", 0x1c) + bytes([0]) + struct.pack("<h", -1))
        rel = [50] * F
        rel[fid] = 100
        for k in range(R, F):
            rel[k] = 0
        fo = at("force", fid)
        D[fo:fo + 4 + F + 22] = struct.pack("<hh", ruler, -1) + bytes(rel) + bytes([9, kok, color, 0]) + struct.pack("<h", -1) + bytes(16)
        for k in scn.used_forces():
            if k != fid:
                D[at("force", k) + 4 + fid] = 50
        to = at("type14", kok)
        D[to:to + 5] = big5(fname, 5, "国号")
        if fs.get("intro") and fid < 42:                    # the scenario has 42 descriptions (forces 0..41)
            do = scn.L["force_desc"][0] + 369 * fid
            D[do] = fs.get("stars", 3)
            D[do + 1:do + 369] = big5(fs["intro"], 368, "势力介绍")
        # ---- cities
        for c, cs in cities:
            D[at("building", c) + 1] = fid
            co = at("city", c)
            r = bytearray(D[co:co + 81])
            r[0] = kid
            struct.pack_into("<III", r, 5, cs.get("troops", 10000), cs.get("gold", 2000), cs.get("food", 30000))
            r[17:65] = tc[17:65]
            r[73:75] = tc[73:75]
            D[co:co + 81] = r
            if c < 42:
                D[0x1DB + c] = color                               # owner's colour on the scenario preview
        created.append((fid, fname, ruler, [n for _, n in members], [cs["city"] for _, cs in cities]))
    # ---- relations (after every force exists, so they can name each other)
    rulers = {scn.person_name(scn.force_ruler(f)): f for f in scn.used_forces()}
    for fs in spec.get("forces", []):
        me = next(f for f, n, *_ in created if n == fs.get("name", "?"))
        for other, v in fs.get("relations", {}).items():
            if other not in rulers:
                raise BuildError(f"relations 里的「{other}」不是任何势力的君主")
            o = rulers[other]
            v = max(0, min(100, int(v)))
            D[at("force", me) + 4 + o] = v
            D[at("force", o) + 4 + me] = v
    return created


def list_scenario(scn):
    print(f"城市 {scn.C} 座。势力：")
    for f in scn.used_forces():
        fo = scn.at("force", f)
        kok = scn.D[fo + 4 + scn.F + 1]
        name = "—"
        if kok < 84:
            to = scn.at("type14", kok)
            name = bytes(scn.D[to:to + 5]).split(b"\0")[0].decode("cp950", "replace")
        own = [c for c in range(scn.C) if scn.D[scn.at("building", c) + 1] == f]
        print(f"  {f:2d} {name:4s} 君主 {scn.person_name(scn.force_ruler(f))}  城 {len(own)} 座")
    free = [s for s in FREE_SLOTS if scn.D[scn.at("person", s) + 100] == 0xff]
    print(f"新武将空位还剩 {len(free)} 个")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec", nargs="?", help="剧本 JSON（不写则只列出 --base 剧本的现状）")
    ap.add_argument("--data", help="世界数据目录，如 C:/San11PK/world_custom")
    ap.add_argument("--base", type=int, help="只列出这个原版剧本的势力（0~13）")
    ap.add_argument("--list-scenarios", action="store_true", help="列出 14 个原版剧本的编号")
    a = ap.parse_args()
    if a.list_scenarios:
        for i, s in enumerate(SCENARIOS):
            print(f"{i:2d}  {s}  ({SCEN_FILES[i]})")
        return 0
    if not a.data:
        ap.error("需要 --data（世界数据目录）")
    data = Path(a.data)
    sdir, bdir = data / "scenario", data / "scenario_base"
    try:
        spec = json.loads(Path(a.spec).read_text(encoding="utf-8")) if a.spec else {"base": a.base or 0}
        base = int(spec.get("base", 0))
        if not 0 <= base < len(SCEN_FILES):
            raise BuildError(f"base 要写 0~13（{base}）")
        fn = SCEN_FILES[base]
        src = bdir / fn
        if not src.exists():
            if not (sdir / fn).exists():
                raise BuildError(f"{sdir / fn} 不存在：请先运行 san11kit.py world")
            bdir.mkdir(exist_ok=True)
            shutil.copy2(sdir / fn, src)
        if not a.spec:                                    # show the scenario as it is now
            list_scenario(Scenario((sdir / fn).read_bytes(), data))
            return 0
        scn = Scenario(src.read_bytes(), data)
        created = build(spec, scn)
        (sdir / fn).write_bytes(bytes(scn.D))
        print(f"已写入 {sdir / fn}（基于 {SCENARIOS[base]}）")
        for fid, name, ruler, members, cities in created:
            print(f"  势力 {name}（编号 {fid}）：君主 {scn.person_name(ruler)}，武将 {len(members)} 人，城 {'、'.join(map(str, cities))}")
    except BuildError as e:
        print("错误：", e, file=sys.stderr)
        return 1
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        print(f"错误：剧本 JSON 写得不对：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
