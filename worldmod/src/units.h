#pragma once
// More units (部队) than Koei's 1000 (units.cpp, M9_UNITS.md).
#include <stdint.h>
#include "d3dtrace.h"

struct Units {
    int U = 1000;                    // unit records; locations N..N+U-1 are units
    uint8_t* UNITARR = nullptr;      // U x 0xf4 (world+0x169730 in Koei's layout)
    uint8_t* AIUREC = nullptr;       // U x 4 AI per-unit records (AI sub-object +0x3e94)
    int* USTREAM = nullptr;          // unit records in the stream being read / written (1000 for Koei's files)
    uint8_t* UWRAP = nullptr;        // U x 0x10 view wrappers (unit view manager 0x95499b0 +0)
    uint8_t* UPOOL = nullptr;        // node pool: U x 0xc nodes + 0x10 header (manager +0x5e80)
};

// thiscall entry hook of the unit snapshot methods (vt 0x863dd4): this -> per-instance buffer sized for U
extern "C" uint8_t* __cdecl snapShadow(uint8_t* self);

bool unitsSetup(int U, Units& u, TraceLogFn log);
// after a stream has been read (0x493BCE): records USTREAM..U-1 got no data, reset them as the serializer resets
// the ones it reads (vtable+0x20); constructed but never reset, a record passes for a live unit led by person 0
void unitsResetTail(const Units& u);
