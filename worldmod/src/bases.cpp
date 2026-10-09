// bases: memory and helpers for more bases (cities) than Koei's 42 / 87 (M7_LAYOUT.md).
//
// The patch tables worldmod_bases*.txt rewrite every place that depends on the city count C or the
// base count N (= C + 10 gates + 35 ports) and point the game at the arrays allocated here. With
// C = 42 every expression gives back the original value and the arrays hold the original contents.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "bases.h"

namespace {

TraceLogFn g_log = nullptr;

uint8_t* alloc(size_t size) {
    size = (size + 15) & ~(size_t)15;
    return (uint8_t*)VirtualAlloc(nullptr, size + 64, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);   // zero-filled
}

size_t A4(size_t x) { return (x + 3) & ~(size_t)3; }

// copy the original contents of a relocated array (as much as fits)
void copyOld(uint8_t* to, uint32_t from, size_t oldSize, size_t newSize) {
    memcpy(to, (void*)(uintptr_t)from, oldSize < newSize ? oldSize : newSize);
}

// thiscall(world, id) -> building, like 0x490d00, but the u8 "none" value 0xff gives NULL
__declspec(naked) void bldU8() {
    __asm {
        cmp dword ptr [esp + 4], 0xff
        je none
        mov eax, 0x490d00
        jmp eax
    none:
        xor eax, eax
        ret 4
    }
}

// thiscall(stream, int* value) ret 4: copy of the i8 field serializer 0x48a970 whose read path loads
// the byte unsigned (ids up to 254) and maps 0xff to -1; the file format does not change
__declspec(naked) void serU8Id() {
    __asm {
        push ebx
        mov ebx, dword ptr [esp + 8]
        mov al, byte ptr [ebx]
        push esi
        mov esi, ecx
        mov byte ptr [esp + 0xc], al
        mov eax, dword ptr [esi + 8]
        test eax, eax
        jne l1
        mov eax, dword ptr [esi + 0x68]
        test eax, eax
        je l1
        mov eax, 0x43a820
        call eax
        xor byte ptr [esp + 0xc], al
    l1:
        cmp dword ptr [esi + 8], 1
        push 1
        jne l2
        lea ecx, [esp + 0x10]
        push ecx
        mov ecx, esi
        mov eax, 0x46ff20
        call eax
        jmp l3
    l2:
        lea edx, [esp + 0x10]
        push edx
        mov ecx, esi
        mov eax, 0x470180
        call eax
    l3:
        cmp dword ptr [esi + 8], 1
        jne l4
        mov eax, dword ptr [esi + 0x68]
        test eax, eax
        je l5
        mov ecx, esi
        mov eax, 0x43a820
        call eax
        xor byte ptr [esp + 0xc], al
    l5:
        movzx eax, byte ptr [esp + 0xc]
        cmp eax, 0xff
        jne l6
        or eax, -1
    l6:
        mov dword ptr [ebx], eax
    l4:
        mov eax, esi
        pop esi
        pop ebx
        ret 4
    }
}

// Weighted pick 0x5f7530 (thiscall, ret 8): (u8 weights[count], count) -> index, with probability
// weights[i] / total (weights are signed bytes, those <= 0 count as 0), or -1 when the total is 0.
// Koei's takes the count and returns the index as bytes (N <= 255) and expands the weights into a stack
// buffer; this one returns an int. It draws from the game's random generator 0x472150 like Koei's (one
// draw while the total fits its 16-bit modulus, two otherwise).
typedef uint16_t (__cdecl* Rand16Fn)(int n);
int __fastcall weightedPick(void* self, void*, const int8_t* w, int count) {
    int total = 0;
    for (int i = 0; i < count; i++) if (w[i] > 0) total += w[i];
    if (total <= 0) return -1;
    Rand16Fn rnd = (Rand16Fn)0x472150;
    int r = total < 65536 ? rnd(total) : (int)(((unsigned)rnd(65535) * 65535u + rnd(65535)) % (unsigned)total);
    for (int i = 0; i < count; i++) {
        if (w[i] <= 0) continue;
        if (r < w[i]) return i;
        r -= w[i];
    }
    return -1;
}

// Streams written since phase C (saves) or converted for it (scenarios, convert_scen.py) carry the marker
// 'WIDE' in the unused header dword at file offset 0x2c; worldmod.cpp sets g_idWide when such a stream's
// header is read or written. Their seven i8 id fields are i16 (0x48a9e0); older streams (saves made with
// up to 210 cities) keep the u8 fields (serU8Id), so they still load.
volatile LONG g_idWide = 0;
__declspec(naked) void serId() {
    __asm {
        cmp dword ptr [g_idWide], 0
        je narrow
        mov eax, 0x48a9e0
        jmp eax
    narrow:
        jmp serU8Id
    }
}

bool loadTables(const wchar_t* dir, int C, Bases& b) {
    // bases_tables.bin: "WBTB", u32 C, then 8 x {u32 size, bytes} in the order of the table list below
    wchar_t p[MAX_PATH]; swprintf_s(p, L"%s\\bases_tables.bin", dir);
    FILE* f = nullptr; _wfopen_s(&f, p, L"rb");
    if (!f) return false;
    uint32_t hdr[2] = {};
    bool ok = fread(hdr, 4, 2, f) == 2 && hdr[0] == 'BTBW' && hdr[1] == (uint32_t)C;
    struct { uint8_t* to; size_t size; } t[] = {
        { b.AREAADJ, b.sAREAADJ }, { b.MAT87A, b.sMAT }, { b.MAT87B, b.sMAT }, { b.MATC, b.sMATC },
        { b.AREA2CITY, b.sAREA2CITY }, { b.AREA2BASE, b.sAREA2BASE }, { b.CITYTAB844, b.sCITYTAB844 }, { b.DBGBASE, b.sDBGBASE } };
    for (auto& e : t) {
        uint32_t n = 0;
        if (!ok || fread(&n, 4, 1, f) != 1 || n != e.size || fread(e.to, 1, n, f) != n) { ok = false; break; }
    }
    fclose(f);
    return ok;
}

}  // namespace

bool basesSetup(int C, const wchar_t* dir, Bases& b, TraceLogFn log) {
    g_log = log;
    const int N = C + 45, oldC = 42, oldN = 87;
    if (C < oldC || C > 1000) { if (log) log("bases: invalid city count %d (42..1000)", C); return false; }
    b.C = C; b.N = N;

    b.CITYARR = alloc(C * 0x248);           copyOld(b.CITYARR, 0x7201b30, oldC * 0x248, C * 0x248);
    b.AIBASE = alloc(N * 0x34);             copyOld(b.AIBASE, 0x73f8e14, oldN * 0x34, N * 0x34);
    b.AICITY = alloc(A4(C * 0x21 + 2));     copyOld(b.AICITY, 0x73faf60, A4(oldC * 0x21 + 2), A4(C * 0x21 + 2));
    b.AIUNIT = alloc(0xfa0);                copyOld(b.AIUNIT, 0x99c8a6c, 0xfa0, 0xfa0);
    b.AIBLD16 = alloc(N * 0x10);            copyOld(b.AIBLD16, 0x96a5a30, oldN * 0x10, N * 0x10);
    b.AREAHEX = alloc(4 + N * 0x44);        copyOld(b.AREAHEX, 0x96a9350, 4 + oldN * 0x44, 4 + N * 0x44);
    size_t bits = 4 * (((C + 31) >> 5) > 2 ? ((C + 31) >> 5) : 2);
    b.CITYBITS = alloc(bits);               copyOld(b.CITYBITS, 0x9c43ed0, 8, bits);
    // static screen objects that embed a per-city widget (members after it move when C grows):
    // copy the original image only when the layout is unchanged; they are constructed at run time
    struct { uint8_t** sym; uint32_t addr; size_t size; } scr[] = {
        { &b.UISCR_A, 0x91b6978, 0x341c }, { &b.UISCR_B, 0x9193388, 0x29e4 }, { &b.UISCR_C, 0x91a7bb8, 0x434c },
        { &b.UISCR_D, 0x91abf08, 0x2b84 }, { &b.UISCR_E, 0x91b0ed8, 0x5dc0 }, { &b.UISCR_F, 0x91aea90, 0x2448 } };
    for (auto& s : scr) { *s.sym = alloc(s.size + (C - oldC) * 0xc0); if (C == oldC) copyOld(*s.sym, s.addr, s.size, s.size); }
    b.AIRT = alloc(0x3354 + (N - oldN) * 0x34);
    if (N == oldN) copyOld(b.AIRT, 0x99c78a8, 0x3354, 0x3354);
    size_t colors = (N + 6 > 144 ? N + 6 : 144) * 4;
    b.AREACOL = alloc(colors);
    for (size_t i = 0; i < colors / 4; i++) memcpy(b.AREACOL + i * 4, (void*)(uintptr_t)(0x6fae590 + (i % 144) * 4), 4);

    // tables that were static .rdata data
    b.sAREAADJ = (N + 6) * 56; b.sMAT = N * N; b.sMATC = C * C; b.sAREA2CITY = (N + 6) * 2;   // u16 (phase C)
    b.sAREA2BASE = (N + 6) * 4; b.sCITYTAB844 = C * 4; b.sDBGBASE = N * 16;
    b.AREAADJ = alloc(b.sAREAADJ); b.MAT87A = alloc(b.sMAT); b.MAT87B = alloc(b.sMAT); b.MATC = alloc(b.sMATC);
    b.AREA2CITY = alloc(b.sAREA2CITY); b.AREA2BASE = alloc(b.sAREA2BASE); b.CITYTAB844 = alloc(b.sCITYTAB844);
    b.DBGBASE = alloc(b.sDBGBASE);
    bool fromFile = loadTables(dir, C, b);
    if (!fromFile) {
        if (C != oldC) { if (log) log("bases: bases_tables.bin missing or for another city count; C=%d needs it", C); return false; }
        copyOld(b.AREAADJ, 0x796768, 93 * 56, b.sAREAADJ);
        copyOld(b.MAT87A, 0x797bc0, 87 * 87, b.sMAT);
        copyOld(b.MAT87B, 0x799958, 87 * 87, b.sMAT);
        copyOld(b.MATC, 0x79b830, 42 * 42, b.sMATC);
        for (int i = 0; i < 93; i++) ((uint16_t*)b.AREA2CITY)[i] = *(uint8_t*)(uintptr_t)(0x79c2b0 + i);
        copyOld(b.AREA2BASE, 0x79c358, 93 * 4, b.sAREA2BASE);
        copyOld(b.CITYTAB844, 0x844130, 42 * 4, b.sCITYTAB844);
        copyOld(b.DBGBASE, 0x7e7bd8, 87 * 16, b.sDBGBASE);
    }
    b.BLD_U8 = (void*)bldU8;
    b.WPICK = (void*)weightedPick;
    b.SER_ID = (void*)serId;
    b.IDWIDE = (void*)&g_idWide;
    b.SER_U8ID = (void*)serU8Id;
    bool ok = b.CITYARR && b.AIBASE && b.AICITY && b.AIUNIT && b.AIBLD16 && b.AREAHEX && b.CITYBITS && b.AIRT && b.AREACOL &&
              b.UISCR_A && b.UISCR_B && b.UISCR_C && b.UISCR_D && b.UISCR_E && b.UISCR_F &&
              b.AREAADJ && b.MAT87A && b.MAT87B && b.MATC && b.AREA2CITY && b.AREA2BASE && b.CITYTAB844 && b.DBGBASE;
    if (log) log("bases: C=%d N=%d, arrays %s, tables from %s", C, N, ok ? "allocated" : "FAILED", fromFile ? "bases_tables.bin" : "the original exe");
    return ok;
}
