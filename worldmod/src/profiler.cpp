// Sampling profiler: a background thread suspends the main thread about once per millisecond and records
// EIP plus every exe-code address found on the live part of its stack (ESP .. stack base). Offline,
// tools/profile_report.py keeps only real return addresses (those right after a call instruction) and
// reports self and inclusive time per function.
//
// File: "WPRF" u32 version(1) u32 samples, then per sample: u32 t_ms, u32 eip, u32 n, n x u32 stack words.
#include "profiler.h"
#include <stdio.h>
#include <stdint.h>
#pragma comment(lib, "winmm.lib")

static TraceLogFn g_log = nullptr;
static DWORD g_mainId = 0;
static uint32_t g_stackBase = 0;
static volatile LONG g_on = 0, g_busy = 0;
static uint32_t* g_buf = nullptr;
static size_t g_cap = 0, g_len = 0, g_samples = 0;
static HANDLE g_thread = nullptr;
static DWORD g_t0 = 0;

static const uint32_t CODE_LO = 0x401000, CODE_HI = 0x74f000;
static const size_t BUF_WORDS = 32u << 20;          // 128 MB
static const uint32_t MAX_SCAN = 512u << 10;        // bytes of stack scanned per sample
static const uint32_t MAX_KEEP = 400;               // code words kept per sample

static DWORD WINAPI sampler(void*) {
    HANDLE main = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, g_mainId);
    if (!main) return 0;
    timeBeginPeriod(1);
    while (g_on) {
        Sleep(1);
        if (SuspendThread(main) == (DWORD)-1) break;
        CONTEXT c = {}; c.ContextFlags = CONTEXT_CONTROL;
        if (GetThreadContext(main, &c) && g_len + 3 + MAX_KEEP <= g_cap) {
            uint32_t* rec = g_buf + g_len;
            rec[0] = timeGetTime() - g_t0;
            rec[1] = c.Eip;
            uint32_t n = 0;
            uint32_t sp = c.Esp & ~3u, end = g_stackBase;
            if (end > sp + MAX_SCAN || end <= sp) end = sp + MAX_SCAN;
            __try {
                for (const uint32_t* p = (const uint32_t*)(uintptr_t)sp; (uint32_t)(uintptr_t)p < end && n < MAX_KEEP; p++)
                    if (*p >= CODE_LO && *p < CODE_HI) rec[3 + n++] = *p;
            } __except (EXCEPTION_EXECUTE_HANDLER) {}
            rec[2] = n;
            g_len += 3 + n;
            g_samples++;
        }
        ResumeThread(main);
    }
    timeEndPeriod(1);
    CloseHandle(main);
    return 0;
}

void profilerInit(TraceLogFn log) {
    g_log = log;
    g_mainId = GetCurrentThreadId();
    g_stackBase = (uint32_t)(uintptr_t)((NT_TIB*)NtCurrentTeb())->StackBase;
}

bool profilerStart() {
    if (g_on || !g_mainId) return false;
    if (!g_buf) {
        g_buf = (uint32_t*)VirtualAlloc(nullptr, BUF_WORDS * 4, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (!g_buf) { if (g_log) g_log("profiler: cannot allocate the sample buffer"); return false; }
        g_cap = BUF_WORDS;
    }
    g_len = g_samples = 0;
    g_t0 = timeGetTime();
    g_on = 1;
    g_thread = CreateThread(nullptr, 1 << 16, sampler, nullptr, 0, nullptr);
    SetThreadPriority(g_thread, THREAD_PRIORITY_TIME_CRITICAL);
    if (g_log) g_log("profiler: started (main thread %lu, stack base %08x)", g_mainId, g_stackBase);
    return true;
}

int profilerStop(const char* path) {
    if (!g_on) return -1;
    g_on = 0;
    WaitForSingleObject(g_thread, 5000);
    CloseHandle(g_thread); g_thread = nullptr;
    FILE* f = nullptr; fopen_s(&f, path, "wb");
    if (!f) return -1;
    uint32_t h[3] = { 'FRPW', 1, (uint32_t)g_samples };
    fwrite(h, 4, 3, f);
    fwrite(g_buf, 4, g_len, f);
    fclose(f);
    if (g_log) g_log("profiler: %zu samples over %lu ms -> %s", g_samples, timeGetTime() - g_t0, path);
    return (int)g_samples;
}
