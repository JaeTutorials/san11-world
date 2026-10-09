// terrainwin: world terrain store and terrain-window filling.
//
// The stage object (0x3260860) holds a 1025x1025-vertex window of the world. Global vertex of hex
// (lo, hi): z = lo*4 + 112, x = hi*4 + 112 + 2*(lo & 1). The world terrain is kept compactly on disk
// (world_height.npy / world_mat.npy, one byte per global vertex, made by tools/make_world.py); vertex
// colour, normal and quad (texture-layer) records are synthesised here. Inside the China block the
// original Koei stage data is used unchanged (captured the first time the stage loads).
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "terrainwin.h"

namespace {

const int N = 1025;                 // window vertices per side
const int QN = 1024;                // quads per side
const size_t VREC = 10, QREC = 8;
const size_t VOFF = 0x800008, QOFF = 0x8;

struct Npy { HANDLE file = nullptr, map = nullptr; const uint8_t* data = nullptr; int rows = 0, cols = 0; };
Npy g_height, g_mat;
TraceLogFn g_log = nullptr;

// China stage as loaded from the game resources (vertex records + quad records), and every season's colours
uint8_t* g_chinaV = nullptr;        // N*N*VREC
uint8_t* g_chinaQ = nullptr;        // QN*QN*QREC
int g_chinaGZ = 0, g_chinaGX = 0;   // global vertex of China stage vertex (0,0)

// material -> RGB, learned from the stock stage (tools: terrain_fit.json)
uint8_t g_palette[64][3];

bool openNpy(const wchar_t* path, Npy& n) {
    n.file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (n.file == INVALID_HANDLE_VALUE) { n.file = nullptr; return false; }
    n.map = CreateFileMappingW(n.file, nullptr, PAGE_READONLY, 0, 0, nullptr);
    if (!n.map) return false;
    const uint8_t* base = (const uint8_t*)MapViewOfFile(n.map, FILE_MAP_READ, 0, 0, 0);
    if (!base || memcmp(base, "\x93NUMPY", 6)) return false;
    uint16_t hlen = *(const uint16_t*)(base + 8);
    const char* hdr = (const char*)base + 10;
    const char* sh = strstr(hdr, "'shape': (");
    if (!sh || !strstr(hdr, "'|u1'") || sscanf_s(sh + 10, "%d, %d", &n.rows, &n.cols) != 2) return false;
    n.data = base + 10 + hlen;
    return true;
}

inline uint8_t at(const Npy& n, int z, int x, uint8_t outside) {
    if (z < 0 || x < 0 || z >= n.rows || x >= n.cols) return outside;
    return n.data[(size_t)z * n.cols + x];
}

void defaultPalette() {
    static const struct { int m; uint8_t r, g, b; } p[] = {
        {0,162,164,162},{2,140,143,140},{3,154,154,142},{18,100,101,91},{21,112,110,97},{24,96,84,65},
        {27,95,95,92},{29,98,102,82},{30,88,93,74},{15,104,110,86},{13,110,104,92},{4,150,146,128},
        {6,96,96,90},{8,104,102,94},{20,92,92,86},{33,120,112,96},{34,126,118,100}};
    for (int i = 0; i < 64; i++) g_palette[i][0] = g_palette[i][1] = g_palette[i][2] = 110;
    for (auto& e : p) { g_palette[e.m][0] = e.r; g_palette[e.m][1] = e.g; g_palette[e.m][2] = e.b; }
}

bool inChina(int gz, int gx, int margin) {
    int kz = gz - g_chinaGZ, kx = gx - g_chinaGX;
    return kz >= 112 - margin && kz <= 912 + margin && kx >= 112 - margin && kx <= 912 + margin;
}

}  // namespace

bool terrainOpen(const wchar_t* dir, int chinaLo, int chinaHi, TraceLogFn log) {
    g_log = log;
    defaultPalette();
    wchar_t p[MAX_PATH];
    swprintf_s(p, L"%s\\world_palette.bin", dir);     // 64 x RGB, learned from the stock stage
    FILE* pf = nullptr; _wfopen_s(&pf, p, L"rb");
    if (pf) { fread(g_palette, 1, sizeof g_palette, pf); fclose(pf); }
    swprintf_s(p, L"%s\\world_height.npy", dir);
    bool ok = openNpy(p, g_height);
    swprintf_s(p, L"%s\\world_mat.npy", dir);
    ok = ok && openNpy(p, g_mat) && g_height.rows == g_mat.rows && g_height.cols == g_mat.cols;
    g_chinaGZ = chinaLo * 4;   // China stage vertex (kz, kx) is global (chinaLo*4 + kz, chinaHi*4 + kx)
    g_chinaGX = chinaHi * 4;
    if (g_log) g_log("terrain: world vertex grid %s (%dx%d)", ok ? "mapped" : "MISSING", g_height.rows, g_height.cols);
    return ok;
}

void terrainCaptureChina(const uint8_t* stage) {
    if (!g_chinaV) {
        g_chinaV = (uint8_t*)VirtualAlloc(nullptr, (size_t)N * N * VREC, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        g_chinaQ = (uint8_t*)VirtualAlloc(nullptr, (size_t)QN * QN * QREC, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
    }
    memcpy(g_chinaV, stage + VOFF, (size_t)N * N * VREC);
    memcpy(g_chinaQ, stage + QOFF, (size_t)QN * QN * QREC);
    if (g_log) g_log("terrain: China stage captured");
}

void terrainFill(uint8_t* stage, int originZ, int originX) {
    if (!g_height.data || !g_chinaV) return;
    uint8_t* V = stage + VOFF;
    uint8_t* Q = stage + QOFF;
    for (int lz = 0; lz < N; lz++) {
        int gz = originZ + lz;
        for (int lx = 0; lx < N; lx++) {
            int gx = originX + lx;
            uint8_t* r = V + ((size_t)lz * N + lx) * VREC;
            if (inChina(gz, gx, 0)) {
                memcpy(r, g_chinaV + ((size_t)(gz - g_chinaGZ) * N + (gx - g_chinaGX)) * VREC, VREC);
                continue;
            }
            uint8_t h = at(g_height, gz, gx, 0), m = at(g_mat, gz, gx, 0);
            // normal from neighbouring heights (fit against the stock stage: y = h*0.25, spacing 5, signs -1/-1)
            float dx = (at(g_height, gz, gx + 1, h) - at(g_height, gz, gx - 1, h)) * 0.25f / 10.0f;
            float dz = (at(g_height, gz + 1, gx, h) - at(g_height, gz - 1, gx, h)) * 0.25f / 10.0f;
            float inv = 1.0f / sqrtf(dx * dx + 1.0f + dz * dz);
            int shade = (int)(inv * 255.0f) - 230;     // darker on slopes
            r[0] = h;
            for (int c = 0; c < 3; c++) {
                int v = g_palette[m & 63][c] + shade;
                r[1 + c] = (uint8_t)(v < 0 ? 0 : v > 255 ? 255 : v);
            }
            r[4] = (uint8_t)(128 + 127 * dx * inv);
            r[5] = (uint8_t)(128 + 127 * inv);
            r[6] = (uint8_t)(128 + 127 * dz * inv);
            r[7] = m;
            r[8] = h;
            r[9] = 0;
        }
    }
    for (int qz = 0; qz < QN; qz++) {
        int gz = originZ + qz;
        for (int qx = 0; qx < QN; qx++) {
            int gx = originX + qx;
            uint8_t* q = Q + ((size_t)qz * QN + qx) * QREC;
            if (inChina(gz, gx, 0) && inChina(gz + 1, gx + 1, 0)) {
                memcpy(q, g_chinaQ + ((size_t)(gz - g_chinaGZ) * QN + (gx - g_chinaGX)) * QREC, QREC);
                continue;
            }
            uint8_t m = V[((size_t)qz * N + qx) * VREC + 7];
            memset(q, 0, QREC);
            q[0] = (uint8_t)(((m & 15) << 4) | 1);      // single texture layer: base material
            q[1] = (uint8_t)(0x3c | (m >> 4));
        }
    }
    if (g_log) g_log("terrain: window filled at global vertex (%d,%d)", originZ, originX);
}
