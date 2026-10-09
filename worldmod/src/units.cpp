// units: memory for more units (部队) than Koei's 1000 (M9_UNITS.md).
//
// The world object keeps 1000 unit records of 0xf4 bytes at world+0x169730; the next object type follows right
// after them, so the array moves here (U records, constructed and destroyed by the world's own ctor / dtor through
// the patched eh vector iterators). The AI sub-object's per-unit records (4 bytes each) move with it. Files keep
// one record per unit in the save stream; USTREAM is the record count of the stream being read or written (the
// header mark says how many, Koei's files and files made with U = 1000 have 1000), so older saves still load.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "units.h"

namespace {

uint8_t* alloc(size_t size) {
    size = (size + 15) & ~(size_t)15;
    return (uint8_t*)VirtualAlloc(nullptr, size + 64, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);   // zero-filled
}

const uint32_t UNIT_SIZE = 0xf4;
int g_ustream = 1000;
TraceLogFn g_log = nullptr;

// unit snapshot objects (vt 0x863dd4) live on the stack of two dialogs with room for 1000 units; their seven data
// methods run on a buffer of the same layout (records 0x70 at +4, flags at +4+U*0x70) kept per object address
struct Shadow { uint8_t* self; uint8_t* buf; };
Shadow g_shadow[16];
int g_nshadow = 0, g_nextShadow = 0;
size_t g_shadowSize = 0;

}  // namespace

extern "C" uint8_t* __cdecl snapShadow(uint8_t* self) {
    for (int i = 0; i < g_nshadow; i++)
        if (g_shadow[i].self == self || g_shadow[i].buf == self) return g_shadow[i].buf;
    uint8_t* b = alloc(g_shadowSize);
    if (!b) { if (g_log) g_log("ERROR: units: snapshot buffer allocation failed"); return self; }
    int k = g_nshadow < 16 ? g_nshadow++ : g_nextShadow++ % 16;   // old buffers stay allocated (still in use?)
    g_shadow[k] = { self, b };
    return b;
}

bool unitsSetup(int U, Units& u, TraceLogFn log) {
    // location ids N+unit are 16-bit in the wide streams (N <= 1045) and every unit takes a map-object slot
    // (65535, shared with up to 16384 buildings)
    const int maxU = 30000;
    if (U < 1000 || U > maxU) { if (log) log("units: unit count %d not supported (1000..%d), using 1000", U, maxU); U = 1000; }
    u.U = U;
    u.UNITARR = alloc((size_t)U * UNIT_SIZE);
    u.AIUREC = alloc((size_t)U * 4);
    u.USTREAM = &g_ustream;
    u.UWRAP = alloc((size_t)U * 0x10);
    u.UPOOL = alloc((size_t)U * 0xc + 0x10);
    g_log = log;
    g_shadowSize = 4 + (size_t)U * 0x74;
    if (!u.UNITARR || !u.AIUREC || !u.UWRAP || !u.UPOOL) { if (log) log("units: allocation failed"); return false; }
    if (log) log("units: U=%d, arrays allocated (UNITARR %p, AIUREC %p)", U, u.UNITARR, u.AIUREC);
    return true;
}

typedef void(__thiscall* UnitResetFn)(void*, int);
void unitsResetTail(const Units& u) {
    for (int i = *u.USTREAM; i < u.U; i++) {
        uint8_t* p = u.UNITARR + (size_t)i * UNIT_SIZE;
        uint8_t* vt = *(uint8_t**)p;
        if (vt) (*(UnitResetFn*)(vt + 0x20))(p, 0);
    }
}
