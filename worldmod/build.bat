@echo off
rem Builds worldmod as a 32-bit d3d9.dll proxy.
rem Do not link d3d9.lib: this DLL is itself named d3d9.dll and loads the system one at runtime.
rem Uses an x86 compiler environment that is already set up (e.g. on GitHub Actions); otherwise finds
rem Visual Studio 2022 or its Build Tools (any edition, with the C++ desktop workload) through vswhere.
if /i "%VSCMD_ARG_TGT_ARCH%"=="x86" goto build
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto novs
set "VSDIR="
for /f "usebackq delims=" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSDIR=%%i"
if not defined VSDIR goto novs
set "PATH=%PATH%;%ProgramFiles(x86)%\Microsoft Visual Studio\Installer"
call "%VSDIR%\VC\Auxiliary\Build\vcvars32.bat" >nul

:build
cd /d "%~dp0"
if not exist build mkdir build
cl /nologo /utf-8 /O2 /MT /W3 /EHsc /std:c++17 /LD src\worldmod.cpp src\d3dtrace.cpp src\automation.cpp src\terrainworld.cpp src\bases.cpp src\profiler.cpp src\pathfind.cpp src\radar.cpp src\midmap.cpp src\forces.cpp src\units.cpp /Fobuild\ /Febuild\d3d9.dll /link /DEF:src\d3d9.def user32.lib kernel32.lib shell32.lib gdi32.lib
if errorlevel 1 exit /b 1
exit /b 0

:novs
echo Visual Studio 2022 C++ tools not found. Install "Build Tools for Visual Studio 2022" with "Desktop development with C++".
exit /b 1
