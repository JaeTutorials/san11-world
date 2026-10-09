#pragma once
// Optional Direct3D 9 call tracer (see d3dtrace.cpp).
typedef void (*TraceLogFn)(const char* fmt, ...);
void traceInit(const wchar_t* dir, const wchar_t* section, TraceLogFn log, bool recordCalls);
void* traceWrapDirect3D9(void* d3d);
