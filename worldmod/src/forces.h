#pragma once
// More forces and corps than Koei's 47 (forces.cpp, M8_FORCES.md).
#include <stdint.h>
#include "d3dtrace.h"

struct Forces {
    int R = 42, F = 47;              // regular forces (and regular corps); forces = corps = R + 5
    int W = 2;                       // dwords per force bit set row: (F+31)/32
    uint32_t *FMASK = nullptr, *AIM0 = nullptr, *AIM1 = nullptr, *FBITS = nullptr;   // force bit sets (forces.cpp)
    // relocated arrays and side tables (patch-expression symbols of the same name)
    uint8_t *FORCEARR = nullptr, *CORPSARR = nullptr, *FREL = nullptr, *FA64 = nullptr;
    uint8_t *TURNORD = nullptr, *AIFREG = nullptr, *AICORPS = nullptr;
    uint8_t *FLAG104 = nullptr, *FLAG84A = nullptr, *FLAG84B = nullptr, *FLAG1004 = nullptr;
    uint8_t *SFRC1 = nullptr, *SFRC2 = nullptr, *SFRC3 = nullptr, *SFRC4 = nullptr;
    uint8_t *STKARR = nullptr;          // slots for the stack-local per-force arrays (0x2000 bytes each)
    uint8_t *DLGREC = nullptr;          // new-game setup dialog: per-force records (0x184 each)
    // replacement functions (thiscall)
    void *GET_REL = nullptr, *SET_REL = nullptr, *GET_A64 = nullptr, *SET_A64 = nullptr;
    void *SER_FREL = nullptr, *SER_FA64 = nullptr;
};

bool forcesSetup(int R, Forces& f, TraceLogFn log);
void forceClearRows(uint8_t* force);     // after Koei's force reset 0x481020
bool forcesInstallTraps();               // the four stack-array stores that are emulated (int3)

// replacement functions for the force bit sets (installed by worldmod.cpp)
uint32_t* __cdecl forceMaskRow(uint8_t* force);
int __fastcall forceTestMask(uint8_t* self, int, int other);
void __stdcall forceSetMaskPair(int a, int b, int value);
void* __fastcall forceSerMask(uint8_t* stream, int, uint8_t* member);
void __cdecl forceSerAIMasks(uint8_t* stream, int k);
void __stdcall aiReset(int f);
void __stdcall aiClear0(int f);
void __stdcall aiClear1(int f);
void __stdcall aiSet0(int f, int bit, int val);
void __stdcall aiSet1(int f, int bit, int val);
int __stdcall aiTest0(int f, int bit);
int __stdcall aiTest1(int f, int bit);
