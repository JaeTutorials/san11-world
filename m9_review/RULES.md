# Review rules: unit (部队) count constants in san11pk.exe (M9)

Context: Romance of the Three Kingdoms XI PK (san11pk.exe, 32-bit x86 MSVC). The user owns the game and mods it
(a d3d9.dll proxy patches code at runtime). Cities were raised from 42 to C (500) and forces to R; now the number
of units (部队, armies on the map) must be raised from 1000 to U (a setting, e.g. 4000).
Background, only as needed: G:\三国11威力加强版\san11pk\mapmod_re\COORDS.md (world object table), BUILDINGS.md.

## Id layout
Units (部队): getter 0x490e70 (ecx = world 0x7201958; returns NULL outside 0..999), 1000 records of 0xf4 at
  world+0x169730 = 0x736b088 .. 0x73a69a8 (next object type starts there). Find a free unit 0x491040 (loop 0..999),
  unit pointer -> id 0x4917c0 (divide by 0xf4, magic 0x4325c53f, then `cmp eax, 0x3e7`). Unit records are saved in
  save games (1000 x 98 bytes, serializer 0x497270). The AI sub-object (world+0x1f47d4) has per-unit records
  (1000 x 4 bytes). The unit array itself will be moved to the DLL; you only judge constants.
  new: units 0..U-1.
Locations (所在, e.g. person +0x9c, "where is this officer"): 0..N-1 are bases (buildings), N..N+999 are units
  (location = N + unit id); getter 0x491bb0. Sites of the form N+999 / N+1000 were already patched and are not in
  your batch, but a bare 999/1000 used as the unit part of a location id IS a unit constant (role LOC_UNIT).
NOT units, very common, decide carefully:
  - persons (武将): 1100 records 0..1099 (world+0xc0bc, 0x190 each). 850..999 are the 150 user-created officer
    slots (新武将), 1000..1099 more person slots; another person-indexed type at world+0x1f9dc4 (0x20 each) covers
    ids 850..1099 (0x491130 scans 850..999, 0x491810 ptr->id adds 0x352 = 850). 999/1000 as person id bounds -> NOT
    (note "person").
  - gameplay numbers: 1000 gold/food/troops, permille (x/1000), milliseconds, 1000 as a score/scale, percent*10,
    rounding, string/number formatting, random ranges, timers, CRT / library code.
  - unrelated object types (items 100, buildings 16384, map object slots 65535).

## For EVERY site in your batch decide
- verdict: UNIT (depends on the unit count and must change), KEEP (unit related but must stay as is, explain),
  NOT (unrelated; say what it is), UNSURE.
- role (UNIT): UNIT_COUNT (1000 -> "U"), UNIT_MAX (999 -> "U-1"), UNIT_END (1001 or other off-by-one -> "U+1" ...),
  NEG (-1000 -> "-U"), LOC_UNIT (bare 999/1000 in location-id arithmetic, give the expression in N and U, e.g.
  "N+U-1"), ARRAY_SIZE (byte size or element count of an array with one entry per unit: give the formula in U,
  e.g. 1000*4 -> "U*4"; say in the note whether the array is a stack local (function + frame offset), a heap block,
  a static (address) or embedded in a struct (which one, offset) -- embedded / static ones matter most, they must
  be relocated), OTHER (explain).
- patch: expression in U (and N for locations). Empty for KEEP/NOT.
- encoding: "imm8" or "imm32" from the instruction bytes (3d/81/68/69/b8+r/disp32 are imm32).
- note: one short sentence of evidence: what the register holds and where it comes from.

Decide by what the register holds: trace back to a unit getter (0x490e70), 0x4917c0, a loop over unit ids that
calls the getter, a unit record field, a location id (person +0x9c, unit +0x? target), a per-unit array; and
forward to where the value goes. The NEAR column lists unit/location getter calls within 20 instructions (only a
hint). Sizes like 1000*4 = 0xfa0 next to `rep stosd` / an allocation are candidates for per-unit arrays.

Tools: `bash C:/Users/sjc20/AppData/Local/Temp/claude/G----11------san11pk/d67e0319-d5a9-451c-aa9b-3206c6b83628/scratchpad/tools/show.sh <hexaddr> [before] [after]`
prints the disassembly around an address (full listing: scratchpad out/pk.asm). Grep out/pk.asm for callers
(`call 0x<addr>`). Be skeptical; read enough context, including the caller when a value is a parameter.

## Output
Write JSON Lines to scratchpad/m9/result_<batch>.jsonl, one object per site, every site of your batch exactly once:
{"addr":"0x...","value":"1000","verdict":"UNIT|KEEP|NOT|UNSURE","role":"...","patch":"...","encoding":"imm8|imm32","note":"..."}
Do not modify any other file and never run the game. Reply with a short summary: counts per verdict and role, the
UNSURE addresses, and a list of every per-unit array you saw (address or struct+offset, where it lives, element
size, which functions use it) -- those need relocation, not just a constant change.
