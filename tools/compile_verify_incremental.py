"""Check that recompiling only what changed gives the same lots as compiling it all.

    python tools/compile_verify_incremental.py output/<map>

The map is never written to. It is copied, and the copy is first compiled in full,
so that what the incremental compile keeps is what this program compiled: lots
made by an older compile can differ from a fresh one in places (WorldEd's output
is not the same from one run configuration to another), which would hide what is
being tested. Pass --reuse-lots to start from the lots the map already has
instead, and skip that first compile. Three changes are made to a temporary copy - one building's .tbx, a
patch of ground, a patch of the zombie spawn map, in cells far from each other
- and the copy is then compiled twice: once the way the window does after an
edit (only what changed), and once from nothing. Every lot file of the two is
compared. Takes as long as a full compile of the map.

Exit 0 when they are identical, 1 when they are not.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))


def _hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha1(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _copy(src: Path, dst: Path, with_lots: bool) -> None:
    ignore = shutil.ignore_patterns("pictures", "compile_state.json*",
                                    *([] if with_lots else ["lots"]))
    shutil.copytree(src, dst, ignore=ignore)
    pzw = dst / f"{dst.name}.pzw"
    text = pzw.read_text(encoding="utf-8")
    pzw.write_text(text.replace(src.as_posix(), dst.as_posix()), encoding="utf-8")


def _edit(project: Path) -> list[str]:
    """Change one building, a patch of ground and a patch of spawn map."""
    import numpy as np
    from PIL import Image

    said = []
    pzw = project / f"{project.name}.pzw"
    text = pzw.read_text(encoding="utf-8")
    base = re.search(r'<bmp path="([^"]+)"', text).group(1)
    stem = Path(base).stem
    world = re.search(r'<world version="[^"]*" width="(\d+)" height="(\d+)"', text)
    w, h = int(world.group(1)), int(world.group(2))

    # A building in the lower part of the map.
    cells = re.findall(r'<cell x="(\d+)" y="(\d+)" map="[^"]*">(.*?)</cell>', text, re.S)
    for cx, cy, body in cells:
        if int(cy) >= h // 2 and '<lot ' in body:
            rel = re.search(r'<lot [^>]*map="([^"]+)"', body).group(1)
            path = project / rel
            tbx = path.read_text(encoding="utf-8")
            tile = re.search(r'tile="(floors_interior_[a-z_]+_01_\d+)"', tbx)
            if tile:
                other = re.sub(r'_\d+$', '_3', tile.group(1))
                if other == tile.group(1):
                    other = re.sub(r'_\d+$', '_4', tile.group(1))
                path.write_text(tbx.replace(tile.group(1), other, 1), encoding="utf-8")
                said.append(f"building {rel} in cell {cx},{cy}")
                break

    # A patch of ground in the upper right.
    gx, gy = max(0, w - 6) * 300 + 100, min(3, h - 1) * 300 + 100
    ground = project / f"{stem}.bmp"
    with Image.open(ground) as im:
        arr = np.array(im.convert("RGB"))
    arr[gy:gy + 40, gx:gx + 40] = (60, 60, 60)
    Image.fromarray(arr).save(ground, format="BMP")
    said.append(f"ground at tile {gx},{gy} (cell {gx // 300},{gy // 300})")

    # A patch of the zombie spawn map in the lower middle.
    spawn = project / f"{stem}_ZombieSpawnMap.bmp"
    if spawn.exists():
        with Image.open(spawn) as im:
            sp = np.array(im.convert("RGB"))
        sx, sy = (w // 2) * 30 + 5, max(0, h - 3) * 30 + 5
        sp[sy:sy + 10, sx:sx + 10] = np.minimum(255, sp[sy:sy + 10, sx:sx + 10] + 6)
        Image.fromarray(sp).save(spawn, format="BMP")
        said.append(f"spawn map at cell {sx // 30},{sy // 30}")
    return said


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--reuse-lots", action="store_true",
                    help="start from the map's own lots rather than compiling first")
    args = ap.parse_args(argv)

    import compile_map
    import compile_state

    src = Path(args.project).resolve()
    if args.reuse_lots and not any((src / "lots").glob("*.lotheader")):
        print(f"{src} has not been compiled; compile it first, or leave out "
              f"--reuse-lots.", file=sys.stderr)
        return 1

    work = Path(tempfile.mkdtemp(prefix="knoxmap-incr-"))
    try:
        # The modified inputs, once, so both compiles start from the same ones.
        inc, full = work / "inc" / src.name, work / "full" / src.name
        (work / "inc").mkdir()
        (work / "full").mkdir()
        _copy(src, inc, with_lots=args.reuse_lots)
        if args.reuse_lots:
            # The record the window would have from the compile that made these lots.
            compile_state.save(inc, compile_state.fingerprints(inc))
        else:
            t0 = time.time()
            compile_state.wipe(inc)
            compile_map.compile_map(str(inc), workers=args.workers)
            print(f"baseline compile:    {time.time() - t0:.0f}s")
            if compile_state.load(inc) is None:
                print("the baseline compile left no record; cannot go on", file=sys.stderr)
                return 1
        print("changes:")
        for line in _edit(inc):
            print("  " + line)
        _copy(inc, full, with_lots=False)       # same edits, nothing compiled
        for f in (full / "tmx").glob("*"):
            f.unlink()
        compile_state.wipe(full)

        # Which lot cells the incremental compile will write again, worked out the
        # way compile_map does, so a difference can be put down to a cell that
        # was rewritten or to one that was kept from the earlier compile.
        now = compile_state.fingerprints(inc)
        plan = compile_state.plan(compile_state.load(inc), now, True)
        origin, (w, h) = tuple(now["origin"]), now["size"]
        discarded = compile_state.lot_files_of(plan["lots"], origin)
        batches = [(x, y, min(x + 3, w - 1), min(y + 3, h - 1))
                   for y in range(0, h, 4) for x in range(0, w, 4)]
        rerun = [b for b in batches
                 if any(c in discarded for c in compile_state.lot_files_of(
                     {(cx, cy) for cx in range(b[0], b[2] + 1) for cy in range(b[1], b[3] + 1)},
                     origin))]
        rewritten = compile_state.lot_files_of(
            {(cx, cy) for b in rerun for cx in range(b[0], b[2] + 1)
             for cy in range(b[1], b[3] + 1)}, origin)

        seen: list = []
        t0 = time.time()
        compile_map.compile_map(str(inc), workers=args.workers,
                                on_detail=lambda d: seen.append(d.get("incremental"))
                                if d.get("incremental") else None)
        t_inc = time.time() - t0
        print(f"incremental compile: {t_inc:.0f}s", seen[:1] or "(no incremental plan)")

        t0 = time.time()
        compile_map.compile_map(str(full), workers=args.workers, incremental=False)
        t_full = time.time() - t0
        print(f"full compile:        {t_full:.0f}s")

        a, b = _hashes(inc / "lots"), _hashes(full / "lots")
        missing = sorted(set(b) - set(a))
        extra = sorted(set(a) - set(b))
        differ = sorted(k for k in set(a) & set(b) if a[k] != b[k])
        print(f"incremental {len(a)} files, full {len(b)} files")
        for label, names in (("missing from the incremental", missing),
                             ("only in the incremental", extra), ("different", differ)):
            if names:
                print(f"  {len(names)} {label}: {', '.join(names[:8])}"
                      f"{' ...' if len(names) > 8 else ''}")
        cells = sorted({tuple(int(v) for v in re.findall(r"\d+", k)[:2]) for k in differ})
        rew = [c for c in cells if c in rewritten]
        kept = [c for c in cells if c not in rewritten]
        print(f"differing lot cells: {len(cells)}; in cells the incremental compile wrote "
              f"again: {len(rew)}; in cells it kept: {len(kept)}")
        print(f"  rewritten: {rew}")
        print(f"  kept:      {kept}")
        print(f"  discarded {len(discarded)} lot cells, reran batches {rerun}")
        same = not (missing or extra or differ)
        print("IDENTICAL" if same else "NOT IDENTICAL")
        return 0 if same else 1
    finally:
        if args.keep:
            print(f"kept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
