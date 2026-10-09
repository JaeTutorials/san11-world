#pragma once
// The 中地圖 (strategic overview screen) for the whole world, see midmap.cpp.
#include <stdint.h>
#include "d3dtrace.h"

struct MidmapWorld {
    const uint8_t* hex20;       // HEX20 records (terrain type in dword +4, bits 0..4)
    const uint8_t* area20;      // u16 area of every hex at the byte offset of its HEX20 record + 4 (AREA20)
    int W, H;                   // columns (hi), rows (lo)
    int chinaLo, chinaHi;       // Koei's 200x200 block
    int C, N;                   // cities, bases
    const int32_t* area2base;   // area -> base id (negative: none), N + 6 entries
};

void midmapSetup(const MidmapWorld& w, const wchar_t* gameDir, TraceLogFn log);
void midmapSetCityArray(uint8_t* cities);              // city records (0x248 each, name at +4), for labels
bool midmapReady();

// view of the 600x600 map area: centre (lo, hi) in hexes and pixels per hex
void midmapView(float* lo, float* hi, float* scale);
void midmapSetView(float lo, float hi, float scale);
void midmapZoom(int mx, int my, int wheelDelta);        // (mx, my): map-area pixel under the cursor
void midmapPan(int dx, int dy);
float midmapScale();
bool midmapHexToPixel(int lo, int hi, float margin, float* px, float* py);   // false: outside the area (by margin)
bool midmapPixelToHex(float mx, float my, int* lo, int* hi);

// paint the map area (600x600 ARGB, pitch in pixels); baseColour[b]: tint of base b (alpha = strength, 0 = none)
void midmapRender(uint32_t* dst, int pitch, const uint32_t* baseColour, bool borders, bool roads);
void midmapRenderNames(uint32_t* dst, int pitch);
