# Review rules: base/city count constants in san11pk.exe

Context: Romance of the Three Kingdoms XI PK (san11pk.exe, 32-bit x86 MSVC). The user owns the game and is
modding it to add new cities. Read first: G:\三国11威力加强版\san11pk\mapmod_re\BUILDINGS.md (the base/building
system: world object 0x7201958, getters, arrays, id layout, narrow fields, constant statistics and the
"42 is also the number of regular forces" trap) and NOTES.md.

## Current and new id layout
Today: bases (据点) ids 0..86 = cities 0..41 (C=42), gates 42..51 (G=10), ports 52..86 (P=35); N = C+G+P = 87.
Built facilities use building ids 87.. (building table 0x728b088, 16384 entries). Officer "location" encodes
0..86 = base, 87..1086 = 87 + unit id. Areas (hex bits 5..11) 0..86 = bases, 87..92 = 6 special areas.
Planned: C grows (new cities get ids 42..C-1), gates become C..C+G-1, ports C+G..N-1, N = C+G+P;
facilities start at N; location = base id (0..N-1) or N + unit id (N..N+999); special areas N..N+5.
So every constant must be rewritten as an expression in C, G, P, N (for the current game C=42, G=10, P=35, N=87).

## For EVERY site in your batch decide
- verdict: BASE (depends on the base/city/gate/port counts or id boundaries and must change), KEEP (base-related
  but must NOT change, e.g. a struct stride of 0x34 bytes per base record, an offset inside a record), NOT
  (unrelated: forces count 42, struct offsets/sizes, UI coordinates, game values, loop counts of other tables,
  item/officer/skill ids, stack offsets, CRT/library code), or UNSURE.
- role (for BASE): one of BASE_COUNT (N), BASE_MAX (N-1), CITY_COUNT (C, also "first gate id"), CITY_MAX (C-1),
  GATE_END (C+G, also "first port id"), GATE_MAX (C+G-1), FACILITY_START (N, first non-base building id),
  LOCATION_UNIT_BASE (N, unit locations start), LOCATION_MAX (N+999), AREA (special area ids N..N+5 or
  the area count), ARRAY_SIZE (byte size of an array with N or C entries, give the formula), OTHER.
- patch: the new value as an expression, e.g. "N", "N-1", "C", "C-1", "C+G", "C+G-1", "N+999", "-N", "N+1",
  "C*0x248", ""; for KEEP/NOT leave "".
- encoding: "imm8" or "imm32" (look at the instruction bytes: 83 /x ib, 6a ib, 6b /r ib are imm8; 3d/81/68/69/b8+r are imm32).
- note: one short sentence of evidence (what the compared register holds: a base id from getter 0x490d00/
  0x491770, a city index used with 0x490a10, a force id used with the force getter, a loop over cities, ...).

Key traps:
* 0x2a/0x29 are ALSO the count of regular forces (0..41) and 42..45 are barbarian forces: decide by what the
  register is (a force id/force object vs a city id/city object). Force-related -> NOT.
* 0x34 is the stride of the 87 x 0x34 AI base records at 0x73f8e16 (KEEP) and a common struct size elsewhere (NOT).
* Values in loops over all buildings (16384) or units (1000) are not base counts.
Use `bash tools/show.sh <hexaddr> <before> <after>` (from the scratchpad dir) to read more context, and grep
out/pk.asm for callers. Be skeptical; read enough context to know what the register holds.

## Output
Write JSON Lines to review_b/result_<batch>.jsonl, one object per site:
{"addr":"0x...","value":"...","verdict":"BASE|KEEP|NOT|UNSURE","role":"...","patch":"...","encoding":"imm8|imm32","note":"..."}
Every site of your batch exactly once. Do not modify any other files; do not run the game.
Reply with a short summary: counts per verdict and role, UNSURE addresses, and surprising findings
(e.g. arrays of C/N entries inside structs, bitmasks over cities, loops with unrolled counts).
