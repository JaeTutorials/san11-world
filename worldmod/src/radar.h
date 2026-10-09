#pragma once
// The radar's background picture (UI image 0x11), see radar.cpp.
#include <stdint.h>
#include "d3dtrace.h"

struct RadarWorld {
    const uint8_t* hex20;   // HEX20 records (terrain type in dword +4, bits 0..4)
    int W, H;               // columns, rows
    int chinaLo, chinaHi;   // first row / column of Koei's China block (= the cell window Koei's picture shows)
};
bool radarLearn(const RadarWorld& w, TraceLogFn log);   // read Koei's picture (while it is still the original)
bool radarPaint(const RadarWorld& w, int wlo, int whi); // repaint the map area for the window whose first cell is (wlo, whi)
int radarDump(const char* path);    // write the picture's pixels to a file ("RARD", w, h, format, pool, texture, then w*h ARGB)
