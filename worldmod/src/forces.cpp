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

// ---- four stores into the stack-array slots that are 4-byte instructions with branch targets at them and
// right after them (no 5-byte jump fits): int3 + this vectored handler (tools/patchgen/m8_sites.py STACK_TRAP)
volatile LONG g_trapHits = 0;           // stores performed by the handler (debug: "forces" automation command)
namespace {
enum { EAX, EBX, ECX, EDX, ESI, EDI };
struct StackTrap { uint32_t at; int slot, idx, src; uint8_t bytes[4]; };
const StackTrap kTraps[] = {
    { 0x58d252, 2, EDI, ESI, { 0x89, 0x74, 0xbc, 0x18 } },     // mov [esp+edi*4+0x18], esi
    { 0x5cd459, 11, ESI, EDI, { 0x89, 0x7c, 0xb4, 0x14 } },    // mov [esp+esi*4+0x14], edi
    { 0x5e9310, 13, ESI, EBX, { 0x89, 0x5c, 0xb4, 0x60 } },    // mov [esp+esi*4+0x60], ebx
    { 0x5e9342, 13, ESI, EAX, { 0x89, 0x44, 0xb4, 0x60 } },    // mov [esp+esi*4+0x60], eax
};
DWORD reg(const CONTEXT* c, int r) {
    switch (r) { case EAX: return c->Eax; case EBX: return c->Ebx; case ECX: return c->Ecx;
                 case EDX: return c->Edx; case ESI: return c->Esi; default: return c->Edi; }
}
LONG CALLBACK trapHandler(EXCEPTION_POINTERS* e) {
    if (e->ExceptionRecord->ExceptionCode != EXCEPTION_BREAKPOINT || !g_f) return EXCEPTION_CONTINUE_SEARCH;
    uint32_t at = (uint32_t)(uintptr_t)e->ExceptionRecord->ExceptionAddress;
    for (const auto& t : kTraps) {
        if (t.at != at) continue;
        CONTEXT* c = e->ContextRecord;
        DWORD i = reg(c, t.idx);
        if (i < 0x2000 / 4) *(DWORD*)(g_f->STKARR + t.slot * 0x2000 + i * 4) = reg(c, t.src);
        InterlockedIncrement(&g_trapHits);
        c->Eip = at + 4;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}
}  // namespace

bool forcesInstallTraps() {
    for (const auto& t : kTraps) if (memcmp((void*)(uintptr_t)t.at, t.bytes, 4)) return false;
    if (!AddVectoredExceptionHandler(1, trapHandler)) return false;
    for (const auto& t : kTraps) {
        DWORD old; VirtualProtect((void*)(uintptr_t)t.at, 1, PAGE_EXECUTE_READWRITE, &old);
        *(uint8_t*)(uintptr_t)t.at = 0xcc;
        VirtualProtect((void*)(uintptr_t)t.at, 1, old, &old);
    }
    return true;
}

bool forcesSetup(int R, Forces& f, TraceLogFn log) {
    g_log = log;
    // stage 1 allows up to 59: 64 forces, so the force bit sets stay 64-bit and every id and patched constant fits
    // in a signed byte (M8_FORCES.md)
    const int maxR = 59;
    if (R < 42 || R > maxR) { if (log) log("forces: regular force count %d not supported yet (42..%d), using 42", R, maxR); R = 42; }
    f.R = R; f.F = R + 5;
    const int F = f.F;
    f.FORCEARR = alloc(F * FORCE_SIZE);
    f.CORPSARR = alloc(F * CORPS_SIZE);
    f.FREL = alloc(F * F);
    f.FA64 = alloc(F * F);
    // the other per-force / per-corps storage (tools/patchgen/m8_sites.py); all of it is constructed or
    // cleared by the game at run time, the static arrays get their original image as far as it goes
    f.TURNORD = alloc(F * 4);
    f.AIFREG = alloc(R * 0xd4);
    f.AICORPS = alloc(F * 0x34);
    f.FLAG104 = alloc(F * 0x104);
    f.FLAG84A = alloc(F * 0x84);
    f.FLAG84B = alloc(F * 0x84);
    f.FLAG1004 = alloc(F * 0x1004);
    f.SFRC1 = alloc(F * 4);
    f.SFRC2 = alloc(F * 4);
    f.SFRC3 = alloc(F * 0x40);
    f.SFRC4 = alloc(F * 4);
    f.STKARR = alloc(32 * 0x2000);
    f.DLGREC = alloc(F * 0x184 + 0x200);
    if (!f.TURNORD || !f.AIFREG || !f.AICORPS || !f.FLAG104 || !f.FLAG84A || !f.FLAG84B || !f.FLAG1004 ||
        !f.SFRC1 || !f.SFRC2 || !f.SFRC3 || !f.SFRC4 || !f.STKARR || !f.DLGREC) { if (log) log("forces: allocation failed"); return false; }
    memcpy(f.SFRC1, (void*)0x9283108, 42 * 4);
    memcpy(f.SFRC2, (void*)0x7998b88, 47 * 4);
    memcpy(f.SFRC3, (void*)0x7998c48, 47 * 0x40);
    memcpy(f.SFRC4, (void*)0x9c4a608, 47 * 4);
    if (R == 42) {          // the original layout: keep the original image (constructed at run time anyway)
        memcpy(f.FORCEARR, (void*)0x7209450, 47 * FORCE_SIZE);
        memcpy(f.CORPSARR, (void*)0x720cb64, 47 * CORPS_SIZE);
    }
    f.GET_REL = (void*)forceGetRel; f.SET_REL = (void*)forceSetRel;
    f.GET_A64 = (void*)forceGetA64; f.SET_A64 = (void*)forceSetA64;
    f.SER_FREL = (void*)forceSerRel; f.SER_FA64 = (void*)forceSerA64;
    g_f = &f;
    bool ok = f.FORCEARR && f.CORPSARR && f.FREL && f.FA64;
    if (log) log("forces: R=%d F=%d, arrays %s (FORCEARR %p, STKARR %p, trap counter %p)", R, F, ok ? "allocated" : "FAILED", f.FORCEARR, f.STKARR, (void*)&g_trapHits);
    return ok;
}
