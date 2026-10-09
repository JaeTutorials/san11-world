#pragma once
// World terrain store and terrain-window filling (see terrainwin.cpp).
#include <stdint.h>
#include "d3dtrace.h"
bool terrainOpen(const wchar_t* dir, int chinaLo, int chinaHi, TraceLogFn log);
void terrainCaptureChina(const uint8_t* stage);
void terrainFill(uint8_t* stage, int originZ, int originX);
