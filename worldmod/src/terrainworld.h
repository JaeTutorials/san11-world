#pragma once
// Whole-world 3D terrain (M4B.md): the stage object's four big arrays are reallocated for the world
// and filled from the world data plus Koei's China stage (see terrainworld.cpp).
#include <stdint.h>
#include "d3dtrace.h"

struct TerrainLayout {
    int VR = 0, VC = 0;            // vertex rows (lo / world x) and columns (hi / world z); VC is the row stride
    int QR = 0, QC = 0;            // quads: VR-1, VC-1
    int NCR = 0, NCC = 0, CSH = 0; // cells (4x4 quads): rows, columns, row stride 1<<CSH
    int NGR = 0, NGC = 0, GSH = 0; // object grid (half-vertex units): rows, columns, row stride 1<<GSH
    uint8_t* QB = nullptr;         // quads   QR*QC*8      (was TG+0      = 0x3260868)
    uint8_t* VB = nullptr;         // vertices VR*VC*10    (was TG+0x800000 = 0x3a60868)
    uint8_t* GB = nullptr;         // object grid u16      (was 0x4465872)
    uint8_t* CB = nullptr;         // cells 10 bytes       (was 0x44e5872)
};

bool terrainAllocate(int H, int W, TerrainLayout& out, TraceLogFn log);
// world_height.npy / world_mat.npy (global vertex grid); chinaLo/chinaHi: China block position in hexes
bool terrainOpen(const wchar_t* dir, int chinaLo, int chinaHi);
// Replacements for the K3ST and GCOL parsers: parse the China stage resource, fill the whole world.
int terrainLoadK3st(const uint8_t* data, int size);
int terrainLoadGcol(const uint8_t* data, int size);
