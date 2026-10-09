// The 中地圖 (strategic overview screen) for the whole world.
//
// Koei's screen (research/midmap_re.md) composes a 628x628 picture on the CPU into a shared texture
// whenever it opens or a background mode changes (0x640260): a hand-painted China (midmap.wft image 0),
// an 8-bit picture of the area ids (image 1) tinted per area in the background mode's colour, and a roads
// overlay (image 2). Base markers are sprites placed with a fixed transform (0x63ee40: 3 pixels per hex).
// None of the art covers the world, so worldmod paints the map area (the inner 600x600 pixels) itself,
// from the live game data, at any zoom: Koei's parchment, sea and mountain textures (cut from image 0),
// rivers, roads, each area tinted with the colour Koei's own function gives for the current background
// mode, black area borders, and city names when zoomed in. The markers stay Koei's sprites: the
// transform 0x63ee40 and its inverse 0x63d320 are replaced with the view's (worldmod.cpp).
#define NOMINMAX
#include <windows.h>
#include <stdio.h>
#include <math.h>
#include <algorithm>
#include <vector>
#include "midmap.h"

static MidmapWorld g_w;
static TraceLogFn g_log = nullptr;
static bool g_ready = false;
static float g_lo = 0, g_hi = 0, g_scale = 3.0f;      // view centre (hex units) and pixels per hex
static const int MAP = 600;                            // the map area of the panel (inner 600x600)
static const float MIN_SCALE = 0.32f, MAX_SCALE = 16.0f;
static uint8_t* g_cityArr = nullptr;

// textures cut from Koei's picture (midmap.wft image 0, BGRA 628x628)
static const int PATCH = 64;
static uint32_t g_land[PATCH * PATCH], g_sea[PATCH * PATCH], g_mount[PATCH * PATCH];
static bool g_haveArt = false;

static const uint32_t BUILDINGS = 0x728b088;           // 0x4000 x 0x38: +8 type (0 city, 1 gate, 2 port), +0x1e lo, +0x20 hi
static inline int bldType(int id) { return *(int32_t*)(uintptr_t)(BUILDINGS + id * 0x38 + 8); }
static inline int bldLo(int id) { return *(int16_t*)(uintptr_t)(BUILDINGS + id * 0x38 + 0x1e); }
static inline int bldHi(int id) { return *(int16_t*)(uintptr_t)(BUILDINGS + id * 0x38 + 0x20); }

static bool loadArt(const wchar_t* gameDir) {
    // Media\san11pkres.bin: 'LINK', u32 count, (offset, size) pairs from byte 16; entry 0x12f9 = midmap.wft:
    // 'WFTX0010', u32 size, u32 images, then per image u16 w, u16 h, u32 format + pixels
    wchar_t p[MAX_PATH]; swprintf_s(p, L"%s\\Media\\san11pkres.bin", gameDir);
    HANDLE f = CreateFileW(p, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
    if (f == INVALID_HANDLE_VALUE) return false;
    bool ok = false;
    uint32_t ent[2]; DWORD n = 0;
    LARGE_INTEGER at; at.QuadPart = 16 + 8 * 0x12f9;
    if (SetFilePointerEx(f, at, nullptr, FILE_BEGIN) && ReadFile(f, ent, 8, &n, nullptr) && n == 8 && ent[1] > 24 + 628 * 628 * 4) {
        std::vector<uint8_t> d(24 + 628 * 628 * 4);
        at.QuadPart = ent[0];
        if (SetFilePointerEx(f, at, nullptr, FILE_BEGIN) && ReadFile(f, d.data(), (DWORD)d.size(), &n, nullptr) && n == d.size() &&
            !memcmp(d.data(), "WFTX0010", 8) && *(uint16_t*)&d[16] == 628 && *(uint16_t*)&d[18] == 628 && *(uint32_t*)&d[20] == 32) {
            const uint32_t* img = (const uint32_t*)&d[24];
            auto cut = [&](uint32_t* dst, int x0, int y0) {
                for (int y = 0; y < PATCH; y++) for (int x = 0; x < PATCH; x++) dst[y * PATCH + x] = img[(y0 + y) * 628 + x0 + x] | 0xff000000;
            };
            cut(g_land, 220, 250);     // plain parchment
            cut(g_sea, 540, 120);      // sea with Koei's swirls
            cut(g_mount, 150, 20);     // painted relief along the edge of Koei's map
            ok = true;
        }
    }
    CloseHandle(f);
    return ok;
}

void midmapSetup(const MidmapWorld& w, const wchar_t* gameDir, TraceLogFn log) {
    g_w = w; g_log = log;
    g_lo = w.chinaLo + 100.0f; g_hi = w.chinaHi + 100.0f;
    g_haveArt = loadArt(gameDir);
    if (!g_haveArt) {                                  // flat colours
        for (int i = 0; i < PATCH * PATCH; i++) { g_land[i] = 0xffcac4b7; g_sea[i] = 0xff0f2932; g_mount[i] = 0xff796057; }
    }
    g_ready = w.hex20 && w.area20 && w.area2base && w.W > 0 && w.H > 0;
    if (g_log) g_log("midmap: %s (%dx%d hexes, C=%d N=%d), Koei's textures %s", g_ready ? "ready" : "NOT ready", w.H, w.W, w.C, w.N,
                     g_haveArt ? "loaded" : "NOT found (flat colours)");
}
void midmapSetCityArray(uint8_t* p) { g_cityArr = p; }
bool midmapReady() { return g_ready; }

// ---------------------------------------------------------------- view
static void clampView() {
    g_scale = std::max(MIN_SCALE, std::min(MAX_SCALE, g_scale));
    float half = MAP * 0.5f / g_scale;
    g_lo = (half * 2 >= g_w.H) ? g_w.H * 0.5f : std::max(half, std::min(g_lo, g_w.H - half));
    g_hi = (half * 2 >= g_w.W) ? g_w.W * 0.5f : std::max(half, std::min(g_hi, g_w.W - half));
}
void midmapView(float* lo, float* hi, float* scale) { *lo = g_lo; *hi = g_hi; *scale = g_scale; }
void midmapSetView(float lo, float hi, float scale) { g_lo = lo; g_hi = hi; g_scale = scale; clampView(); }
void midmapZoom(int mx, int my, int wheel) {           // (mx, my): map-area pixel under the cursor
    float lo = g_lo + (mx - MAP * 0.5f) / g_scale, hi = g_hi + (my - MAP * 0.5f) / g_scale;
    g_scale = std::max(MIN_SCALE, std::min(MAX_SCALE, g_scale * powf(1.25f, wheel / 120.0f)));
    g_lo = lo - (mx - MAP * 0.5f) / g_scale; g_hi = hi - (my - MAP * 0.5f) / g_scale;   // keep that hex under the cursor
    clampView();
}
void midmapPan(int dx, int dy) { g_lo -= dx / g_scale; g_hi -= dy / g_scale; clampView(); }
float midmapScale() { return g_scale; }

// hex -> map-area pixel (the hex's centre); false when outside the map area by more than margin
bool midmapHexToPixel(int lo, int hi, float margin, float* px, float* py) {
    *px = (lo + 0.5f - g_lo) * g_scale + MAP * 0.5f;
    *py = (hi + 0.5f + 0.5f * (lo & 1) - g_hi) * g_scale + MAP * 0.5f;
    return *px >= margin && *py >= margin && *px < MAP - margin && *py < MAP - margin;
}
bool midmapPixelToHex(float mx, float my, int* lo, int* hi) {
    float fl = g_lo + (mx - MAP * 0.5f) / g_scale, fh = g_hi + (my - MAP * 0.5f) / g_scale;
    int l = (int)floorf(fl);
    int h = (int)floorf(fh - 0.5f * (l & 1));
    if (l < 0 || l >= g_w.H || h < 0 || h >= g_w.W) return false;
    *lo = l; *hi = h; return true;
}

// ---------------------------------------------------------------- rendering
static inline uint32_t mix(uint32_t a, uint32_t b, int t) {   // t/256 of b
    uint32_t o = 0xff000000;
    for (int s = 0; s < 24; s += 8) {
        int x = (a >> s) & 255, y = (b >> s) & 255;
        o |= (uint32_t)((x * (256 - t) + y * t) >> 8) << s;
    }
    return o;
}
static inline uint32_t tex(const uint32_t* p, int x, int y) {   // mirrored tiling, fixed to the world
    int u = ((x % (2 * PATCH)) + 2 * PATCH) % (2 * PATCH), v = ((y % (2 * PATCH)) + 2 * PATCH) % (2 * PATCH);
    if (u >= PATCH) u = 2 * PATCH - 1 - u;
    if (v >= PATCH) v = 2 * PATCH - 1 - v;
    return p[v * PATCH + u];
}

static const uint32_t RIVER = 0xff64625a, RIVER_SHADOW = 0xff2c2b26, STREAM = 0xff8c8a7e, ROAD = 0xffe2c88c,
                      BORDER = 0xff000000, OUTSIDE = 0xff0b1418, COAST = 0xffe8e2d4;

// Paint the map area into dst (ARGB, pitch in pixels). baseColour[b] = ARGB tint of base b (alpha used, 0 =
// none) as Koei's background-mode function gives it; borders: draw area borders (all modes but "none").
void midmapRender(uint32_t* dst, int pitch, const uint32_t* baseColour, bool borders, bool roads) {
    if (!g_ready) return;
    const int N = g_w.N, W = MAP, H = MAP;
    std::vector<uint32_t> areaCol(N + 6, 0);
    for (int a = 0; a < N + 6; a++) {
        int b = g_w.area2base[a];
        if (b >= 0 && b < N) areaCol[a] = baseColour[b];
    }
    // per pixel: hex terrain and area (kept for two rows to find borders and edges)
    std::vector<int> cur(W), prev(W, -3), curT(W), prevT(W, -1);
    std::vector<char> curC(W), prevC(W);                // the pixel's hex is in Koei's China block
    const float inv = 1.0f / g_scale;
    const float lo0 = g_lo - W * 0.5f * inv, hi0 = g_hi - H * 0.5f * inv;
    const float tk = std::min(3.0f, g_scale);           // texture pixels per hex: Koei's 3, or one per screen pixel when zoomed out
    for (int y = 0; y < H; y++) {
        float fh = hi0 + (y + 0.5f) * inv;
        uint32_t* row = dst + (size_t)y * pitch;
        for (int x = 0; x < W; x++) {
            float fl = lo0 + (x + 0.5f) * inv;
            int lo = (int)floorf(fl);
            int hi = (int)floorf(fh - 0.5f * (lo & 1));
            if (lo < 0 || lo >= g_w.H || hi < 0 || hi >= g_w.W) { cur[x] = -2; curT[x] = -1; row[x] = OUTSIDE; continue; }
            size_t idx = (size_t)lo * g_w.W + hi;
            int t = g_w.hex20[idx * 20 + 4] & 31;
            int area = *(const uint16_t*)(g_w.area20 + idx * 20 + 4);
            int tx = (int)floorf(fl * tk), ty = (int)floorf(fh * tk);
            uint32_t c;
            bool water = t == 6 || t == 7 || t == 8;
            if (t == 8) c = tex(g_sea, tx, ty);
            else if (t == 7) c = RIVER;
            else if (t == 6) c = mix(tex(g_land, tx, ty), STREAM, 170);
            else {
                c = tex(g_land, tx, ty);
                if (t == 15) c = mix(mix(c, 0xff000000, 18), tex(g_mount, tx, ty), 50);   // mountains: a little of Koei's relief
            }
            uint32_t tint = (t != 8 && t != 7 && area < N + 6) ? areaCol[area] : 0;
            if (tint >> 24) c = mix(c, tint, (int)(tint >> 24));
            if (roads && (t == 10 || t == 11 || t == 12)) c = mix(c, ROAD, 200);
            cur[x] = water ? -1 : (area >= N ? -4 : area); curT[x] = t;          // -4: special areas (tribes, land of no city)
            curC[x] = lo >= g_w.chinaLo && lo < g_w.chinaLo + 200 && hi >= g_w.chinaHi && hi < g_w.chinaHi + 200;
            row[x] = c;
        }
        // edges (against the pixel to the left and the one above): coasts, river banks, area borders
        for (int x = 0; x < W; x++) {
            int a = cur[x];
            if (a == -2) continue;
            int l = x > 0 ? cur[x - 1] : a, u = y > 0 ? prev[x] : a;
            int lt = x > 0 ? curT[x - 1] : curT[x], ut = y > 0 ? prevT[x] : curT[x];
            if (l == -2 || u == -2) continue;
            int t = curT[x];
            if (t == 7 && ut != 7 && ut != 8 && ut >= 0) row[x] = RIVER_SHADOW;          // the shaded north bank
            else if (t == 8 && ut != 8 && ut >= 0) row[x] = mix(row[x], 0xff000000, 140);
            else if (t != 8 && ((ut == 8) || (lt == 8))) row[x] = COAST;                   // light rim along the sea
            else if (borders && g_scale >= 0.6f) {
                // between two territories; between a territory and land of no city too, except where Koei's
                // areas end at the edge of his block (that edge would show as a straight line)
                auto edge = [&](int b, bool bChina) {
                    if (a == b || a == -1 || b == -1) return false;
                    if (a >= 0 && b >= 0) return true;
                    if (a >= 0 && b == -4) return !curC[x];
                    if (a == -4 && b >= 0) return !bChina;
                    return false;
                };
                if ((x > 0 && edge(l, curC[x - 1])) || (y > 0 && edge(u, prevC[x]))) row[x] = BORDER;
            }
        }
        prev.swap(cur); prevT.swap(curT); prevC.swap(curC);
    }
}

// city names (GDI on a DIB), when zoomed in far enough to have room for them
void midmapRenderNames(uint32_t* dst, int pitch) {
    if (!g_ready || g_scale < 5.0f || !g_cityArr) return;
    const int W = MAP, H = MAP;
    BITMAPINFO bi = {};
    bi.bmiHeader.biSize = sizeof bi.bmiHeader; bi.bmiHeader.biWidth = W; bi.bmiHeader.biHeight = -H;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32; bi.bmiHeader.biCompression = BI_RGB;
    void* bits = nullptr;
    HDC dc = CreateCompatibleDC(nullptr);
    HBITMAP bm = dc ? CreateDIBSection(dc, &bi, DIB_RGB_COLORS, &bits, nullptr, 0) : nullptr;
    if (!bm) { if (dc) DeleteDC(dc); return; }
    HGDIOBJ old = SelectObject(dc, bm);
    memset(bits, 0, (size_t)W * H * 4);
    int fh = (int)std::min(18.0f, std::max(12.0f, g_scale * 1.6f));
    HFONT font = CreateFontW(-fh, 0, 0, 0, FW_BOLD, 0, 0, 0, CHINESEBIG5_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, L"MingLiU");
    HGDIOBJ oldf = SelectObject(dc, font);
    SetBkMode(dc, TRANSPARENT); SetTextColor(dc, RGB(255, 255, 255));
    for (int b = 0; b < g_w.C; b++) {
        if (bldType(b) != 0) continue;
        float px, py;
        if (!midmapHexToPixel(bldLo(b), bldHi(b), -40, &px, &py)) continue;
        char nb[6] = {}; memcpy(nb, g_cityArr + (size_t)b * 0x248 + 4, 5);
        wchar_t wn[8] = {};
        int len = MultiByteToWideChar(950, 0, nb, -1, wn, 8) - 1;
        if (len <= 0) continue;
        SIZE sz; GetTextExtentPoint32W(dc, wn, len, &sz);
        TextOutW(dc, (int)px - sz.cx / 2, (int)py + 10, wn, len);                     // below Koei's 16-pixel marker
    }
    GdiFlush();
    const uint32_t* t = (const uint32_t*)bits;
    for (int y = 1; y < H - 1; y++) for (int x = 1; x < W - 1; x++) {             // dark text with a light halo
        size_t i = (size_t)y * W + x;
        int v = t[i] & 255;
        int halo = (int)std::max(std::max(t[i - 1] & 255, t[i + 1] & 255), std::max(t[i - W] & 255, t[i + W] & 255));
        uint32_t& d = dst[(size_t)y * pitch + x];
        if (halo > v) d = mix(d, 0xfff4ecd8, halo * 3 / 4);
        if (v) d = mix(d, 0xff1a1410, v);
    }
    SelectObject(dc, oldf); DeleteObject(font);
    SelectObject(dc, old); DeleteObject(bm); DeleteDC(dc);
}
