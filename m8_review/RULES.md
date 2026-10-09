# Review rules: force / corps count constants in san11pk.exe (M8)

Context: Romance of the Three Kingdoms XI PK (san11pk.exe, 32-bit x86 MSVC). The user owns the game and mods it
(a d3d9.dll proxy patches code at runtime). Cities were already raised from 42 to C (500); now the force and corps
limits must follow, because in Koei's design they are tied together: one regular force and one regular corps per city.
Background, only as needed: G:\三国11威力加强版\san11pk\mapmod_re\BUILDINGS.md (world object, getters), M7_LAYOUT.md.

## Id layout
Forces (势力), getter 0x490aa0 (ecx = world 0x7201958), 47 records of 0x12c at world+0x7af8, force ptr->id 0x491270:
  original: 0..41 regular forces (42 = one per city), 42..45 barbarian forces (烏丸 羌 山越 南蠻; 0x480f10 / 0x481370
  test 42..45), 46 = the special force (bandits; 0x481390 tests == 46), 47 in total.
  new: regular 0..C-1, barbarians C..C+3, special C+4, total F = C+5.
Corps (军团), getter 0x490ad0, 47 records of 0x50 at world+0xb20c: corps 0..41 are regular corps (any regular force;
  a force has up to 8, numbered 1..8 in corps +8), corps 42..46 belong to forces 42..46 (corps id = force id).
  new: regular corps 0..C-1, C..C+4 for the barbarian / special forces, total C+5.
Force methods: vtable+0x28 returns the force id. Force struct members indexed by another force id:
  +0xc u8[47] (relations, 0x4814e0 get), +0x64 u8[47] (0x4812c0 get / 0x4814c0 set), +0x50 64-bit bit set of
  forces (0x4811b0 test). These move to DLL side tables; flag their accesses with role PAIR.
Cities (0..C-1), gates, ports were done already (M7); constants already patched are not in your batch.

## For EVERY site in your batch decide
- verdict: FORCE (depends on the force or corps count / id layout and must change), KEEP (force/corps related but must
  stay, e.g. corps number 1..8 per force, 8 players, 84 国号 names, colour indexes), CITY (a city/base constant that
  the M7 city review missed -- important, explain), NOT (unrelated), UNSURE.
- role (FORCE): FORCE_COUNT (47 -> "C+5"), FORCE_MAX (46 -> "C+4"; also "the special force id"), BARB (42..45 as
  barbarian ids: 42 -> "C", 43 -> "C+1", 44 -> "C+2", 45 -> "C+3"), REG_COUNT (42 as number of regular forces or
  corps -> "C"), REG_MAX (41 -> "C-1"), CORPS_COUNT (47 corps -> "C+5"), CORPS_MAX (46 -> "C+4"), NEG (negative forms,
  e.g. -42 -> "-C"), ARRAY_SIZE (a byte size / count of an array with one entry per force or corps, give the formula
  in C, e.g. 47*4 -> "(C+5)*4"; say in the note whether the array is a stack local, a heap block, a static, or
  embedded in a struct -- embedded / static ones are important), PAIR (accesses force x force data: the members
  above, a 47*47 matrix, a bit set of forces), OTHER (explain).
- patch: expression in C only (F = C+5 is written "C+5"). Empty for KEEP/NOT/CITY... for CITY give the city
  expression (C, C-1, N, ...) too.
- encoding: "imm8" or "imm32" from the bytes (83 /x ib, 6a ib, 6b ib, disp8 are imm8; 3d/81/68/69/b8+r/disp32 are imm32).
- note: one short sentence of evidence: what the register holds and where it comes from.

The M7 hint column (M7:NOT ...) is the earlier city review's opinion of the same site; many of those were left as
"force-related, not a city" and are now exactly what we want. Decide by what the register holds: trace back to a
force/corps getter, 0x491270, vtable+0x28, a force/corps record field (person +0x94 corps, city +0x38 corps,
building +0xc owner force, corps +4 force, unit fields) or a loop counter used as a force/corps id; and forward.
Common false positives: 0x2c/0x2e/0x2f as ',' '.' '/' characters in string code, struct offsets/strides, message
ids, skill/item/troop ids, frame-pointer locals, CRT/library code, colours, 0x2d '-' sign handling.
The NEAR flag means a force/corps getter call is within 20 instructions; it is only a hint.

Tools: `bash C:/Users/sjc20/AppData/Local/Temp/claude/G----11------san11pk/d67e0319-d5a9-451c-aa9b-3206c6b83628/scratchpad/tools/show.sh <hexaddr> [before] [after]`
prints the disassembly around an address (full listing out/pk.asm in that scratchpad). Grep out/pk.asm for callers.
Be skeptical; read enough context.

## Output
Write JSON Lines to scratchpad/m8/result_<batch>.jsonl, one object per site, every site of your batch exactly once:
{"addr":"0x...","value":"46","verdict":"FORCE|KEEP|CITY|NOT|UNSURE","role":"...","patch":"...","encoding":"imm8|imm32","note":"..."}
Do not modify any other file and never run the game. Reply with a short summary: counts per verdict and role, UNSURE
addresses, every CITY site, and a list of arrays sized by the force/corps count you saw (address, where it lives,
element size) -- those need relocation, not just a constant change.
