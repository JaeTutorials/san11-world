"""Drive a running san11pk_test.exe through worldmod's automation channel.

Usage: python gamectl.py "<cmd>" ["<cmd>" ...]
  Each argument is one command line (see worldmod/src/automation.cpp), e.g.
  python gamectl.py "click 640 400" "wait 500" "shot out/s1.bmp"
Screenshots given as *.bmp are also saved as a half-size PNG next to them.
"""
import sys
import time
from pathlib import Path

def _game_dir():
    import json
    try:
        return Path(json.loads((Path(__file__).resolve().parents[1] / "project.json").read_text(encoding="utf-8"))["game_dir"])
    except (OSError, ValueError, KeyError):
        return Path(r"C:\San11PK")


GAME = _game_dir()   # game_dir from project.json


def run(cmds, timeout=120.0):
    done = GAME / "worldmod_cmd.done"
    if done.exists():
        done.unlink()
    shots = []
    lines = []
    for c in cmds:
        parts = c.split(None, 1)
        if parts and parts[0] == "shot":
            p = Path(parts[1]).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            shots.append(p)
            c = f"shot {p}"
        lines.append(c)
    tmp = GAME / "worldmod_cmd.tmp"
    tmp.write_text("\n".join(lines) + "\n", encoding="mbcs")
    tmp.replace(GAME / "worldmod_cmd.txt")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if done.exists():
            try:
                text = done.read_text(errors="replace")
            except PermissionError:     # the game is still writing it
                time.sleep(0.1)
                continue
            if text.rstrip().endswith("end"):
                break
        time.sleep(0.1)
    else:
        raise SystemExit("timeout waiting for the game (is san11pk_test.exe running with automation=1?)")
    for p in shots:
        if p.exists():
            from PIL import Image
            im = Image.open(p)
            im.resize((im.width // 2, im.height // 2)).save(p.with_suffix(".png"))
    return text


def _click(x, y, after=400):
    return ["activate", f"move {x - 10} {y - 6}", "wait 400", f"move {x} {y}", "wait 400", f"click {x} {y}", f"wait {after}"]


def _skip():
    # a click skips the intro movie when it plays; never Escape, which leaves the menu when it does not
    return ["activate", "click 1700 1000", "wait 2500"]


# Macros for a 1920x1200 window.
_START = _click(524, 1176, 3000) + _click(524, 1176, 3000) + _click(524, 1176, 8000) + ["skip 180000"]
# these start at the scenario list (scenario_list() gets there first); "skip" (worldmod automation) clicks
# through the opening events until the map is idle
MACROS = {
    # scenario 1 (184 黄巾之乱) as 公孫瓚
    "newgame": _click(720, 430, 3000) + _skip() + _click(816, 425, 1500) + _START,
    # the same scenario as 凱撒 (歐洲, tools/forces/europe.json): pick it in the force list ("切換顯示")
    "europe": _click(720, 430, 3000) + _click(540, 856, 1500) + _click(556, 528, 1500) + _START,
    "skip": ["skip 180000"],
}


def pixel(x, y):
    """colour of the next frame at (x, y), or None while nothing is rendered (movies)"""
    import re
    m = re.search(r"= (\d+) (\d+) (\d+)", run([f"pixel {x} {y}"], timeout=30))
    return tuple(map(int, m.groups())) if m else None


def scenario_list(timeout=180):
    """from anywhere before the map (launch movies, title, a sub-menu): get to the scenario list.
    It is recognised by the parchment preview map at (1160,520); the title and the other menus show a dark
    panel or the background there. Each round: 返回 (614,1174; nothing there on the title, and any click
    skips a movie), then 新遊戲 (720,448)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        p = pixel(1160, 520)
        if p and min(p) > 150:
            return True
        run(_click(614, 1174, 2500) + _click(720, 448, 3000))
    return False


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in ("@newgame", "@europe"):
        if not scenario_list():
            raise SystemExit("scenario list not reached")
    cmds = []
    for a in args:
        cmds += MACROS[a[1:]] if a.startswith("@") else [a]
    print(run(cmds, timeout=600), end="")
