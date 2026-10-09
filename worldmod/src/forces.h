#pragma once
// More forces and corps than Koei's 47 (forces.cpp, M8_FORCES.md).
#include <stdint.h>
#include "d3dtrace.h"

struct Forces {
    int R = 42, F = 47;              // regular forces (and regular corps); forces = corps = R + 5
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
