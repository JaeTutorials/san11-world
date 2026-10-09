// forces: memory and replacement functions for more forces and corps than Koei's 47 (M8_FORCES.md).
//
// Koei's limits are tied to the city count: forces 0..41 are regular (one per city), 42..45 the barbarians,
// 46 the bandits; corps 0..41 regular, 42..46 belong to forces 42..46. With R regular forces (R = C when
// the "trinity" is complete) the layout becomes regular 0..R-1, barbarians R..R+3, bandits R+4, F = R+5
// forces and F corps. The patch tables use the symbol R; the arrays and the force x force tables are here.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>
#include "forces.h"

namespace {

TraceLogFn g_log = nullptr;
Forces* g_f = nullptr;

uint8_t* alloc(size_t size) {
    size = (size + 15) & ~(size_t)15;
    return (uint8_t*)VirtualAlloc(nullptr, size + 64, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);   // zero-filled
}

const uint32_t FORCE_SIZE = 0x12c, CORPS_SIZE = 0x50;

// force id of a force object in FORCEARR, -1 for any other pointer (copies, NULL)
int forceId(const uint8_t* self) {
    if (!g_f || self < g_f->FORCEARR) return -1;
    uint32_t d = (uint32_t)(self - g_f->FORCEARR);
    if (d % FORCE_SIZE || d / FORCE_SIZE >= (uint32_t)g_f->F) return -1;
    return (int)(d / FORCE_SIZE);
}

// the two force x force byte tables that were u8[47] members (+0x0c relations, +0x64)
uint8_t* cell(uint8_t* table, const uint8_t* self, int other, int member) {
    int id = forceId(self);
    if (id >= 0) return table + id * g_f->F + other;
    return other < 47 ? (uint8_t*)self + member + other : nullptr;   // an object outside the array: Koei's layout
}

typedef int(__thiscall* VFn)(void*);
inline int vcall(void* obj, int slot) { return (*(VFn**)obj)[slot](obj); }

}  // namespace

// thiscall(force, other) ret 4 -> relation (0x4814e0)
uint8_t __fastcall forceGetRel(uint8_t* self, int, int other) {
    if (other < 0 || other >= g_f->F) return 0;
    uint8_t* p = cell(g_f->FREL, self, other, 0x0c);
    return p ? *p : 0;
}

// thiscall(force, other, value) ret 8 (0x481ac0): values above 100 are ignored
void __fastcall forceSetRel(uint8_t* self, int, int other, int value) {
    if (other < 0 || other >= g_f->F || (uint8_t)value > 100) return;
    if (uint8_t* p = cell(g_f->FREL, self, other, 0x0c)) *p = (uint8_t)value;
}

// thiscall(force, other) ret 4 (0x4812c0): 0 unless the force is in use (vtable+8)
uint8_t __fastcall forceGetA64(uint8_t* self, int, int other) {
    if (!vcall(self, 2) || other < 0 || other >= g_f->F) return 0;
    uint8_t* p = cell(g_f->FA64, self, other, 0x64);
    return p ? *p : 0;
}

// thiscall(force, other, value) ret 8 (0x4814c0)
void __fastcall forceSetA64(uint8_t* self, int, int other, int value) {
    if (other < 0 || other >= g_f->F) return;
    if (uint8_t* p = cell(g_f->FA64, self, other, 0x64)) *p = (uint8_t)value;
}

// after Koei's reset of a force (0x481020 clears both members): clear its rows
void forceClearRows(uint8_t* self) {
    int id = forceId(self);
    if (id < 0) return;
    memset(g_f->FREL + id * g_f->F, 0, g_f->F);
    memset(g_f->FA64 + id * g_f->F, 0, g_f->F);
}

// one byte through a game stream exactly like the per-byte loop of 0x481ae0
// (stream +8: 1 = reading; +0x68: obfuscation on; 0x43a820 next key byte, 0x46ff20 read, 0x470180 write)
static void serByte(uint8_t* stream, uint8_t* p) {
    typedef uint8_t(__thiscall* KeyFn)(void*);
    typedef void(__thiscall* IoFn)(void*, void*, int);
    KeyFn key = (KeyFn)0x43a820;
    int reading = *(int*)(stream + 8) == 1, obf = *(int*)(stream + 0x68) != 0;
    if (!reading && obf) *p ^= key(stream);
    if (reading) ((IoFn)0x46ff20)(stream, p, 1); else ((IoFn)0x470180)(stream, p, 1);
    if (reading && obf) *p ^= key(stream);
}

// thiscall(stream, member pointer) ret 4, called from the force serializer 0x481d30 in place of 0x481ae0
// for the two force x force members: F bytes (the stream's force count) from the side table
static void serRow(uint8_t* stream, uint8_t* member, uint8_t* table, int off) {
    int id = forceId(member - off);
    for (int k = 0; k < g_f->F; k++) {
        uint8_t scratch = 0;
        serByte(stream, id >= 0 ? table + id * g_f->F + k : (k < 47 ? member + k : &scratch));
    }
}
void* __fastcall forceSerRel(uint8_t* stream, int, uint8_t* member) { serRow(stream, member, g_f->FREL, 0x0c); return stream; }
void* __fastcall forceSerA64(uint8_t* stream, int, uint8_t* member) { serRow(stream, member, g_f->FA64, 0x64); return stream; }

bool forcesSetup(int R, Forces& f, TraceLogFn log) {
    g_log = log;
    if (R < 42 || R > 59) { if (log) log("forces: invalid regular force count %d (42..59 until the force bit sets are widened)", R); return false; }
    f.R = R; f.F = R + 5;
    const int F = f.F;
    f.FORCEARR = alloc(F * FORCE_SIZE);
    f.CORPSARR = alloc(F * CORPS_SIZE);
    f.FREL = alloc(F * F);
    f.FA64 = alloc(F * F);
    if (R == 42) {          // the original layout: keep the original image (constructed at run time anyway)
        memcpy(f.FORCEARR, (void*)0x7209450, 47 * FORCE_SIZE);
        memcpy(f.CORPSARR, (void*)0x720cb64, 47 * CORPS_SIZE);
    }
    f.GET_REL = (void*)forceGetRel; f.SET_REL = (void*)forceSetRel;
    f.GET_A64 = (void*)forceGetA64; f.SET_A64 = (void*)forceSetA64;
    f.SER_FREL = (void*)forceSerRel; f.SER_FA64 = (void*)forceSerA64;
    g_f = &f;
    bool ok = f.FORCEARR && f.CORPSARR && f.FREL && f.FA64;
    if (log) log("forces: R=%d F=%d, arrays %s", R, F, ok ? "allocated" : "FAILED");
    return ok;
}
