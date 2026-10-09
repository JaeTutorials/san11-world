#pragma once
// More forces and corps than Koei's 47 (forces.cpp, M8_FORCES.md).
#include <stdint.h>
#include "d3dtrace.h"

struct Forces {
    int R = 42, F = 47;              // regular forces (and regular corps); forces = corps = R + 5
    // relocated arrays and side tables (patch-expression symbols of the same name)
    uint8_t *FORCEARR = nullptr, *CORPSARR = nullptr, *FREL = nullptr, *FA64 = nullptr;
    // replacement functions (thiscall)
    void *GET_REL = nullptr, *SET_REL = nullptr, *GET_A64 = nullptr, *SET_A64 = nullptr;
    void *SER_FREL = nullptr, *SER_FA64 = nullptr;
};

bool forcesSetup(int R, Forces& f, TraceLogFn log);
void forceClearRows(uint8_t* force);     // after Koei's force reset 0x481020
