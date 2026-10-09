#pragma once
// Sampling profiler for the game's main thread (see profiler.cpp). Driven by the automation commands
// "prof start" and "prof stop <file>"; tools/profile_report.py turns the file into a function table.
#include <windows.h>
#include "d3dtrace.h"
void profilerInit(TraceLogFn log);          // call on the main thread
bool profilerStart();
int profilerStop(const char* path);         // returns the number of samples written, -1 on error
