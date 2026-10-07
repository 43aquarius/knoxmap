"""Does compiling the same thing twice give the same files?

    python tools/compile_repeatable.py output/<map> [--workers N]

Compiles the same four batches of a copy of the map twice, into two separate
copies, and compares every lot file. If they differ, WorldEd itself is not
repeatable, and no comparison between two compiles (see
compile_verify_incremental.py) can be exact; the differences found are what
that costs. The map is never written to.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))


def _hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha1(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)

    import compile_map
    import compile_state

    src = Path(args.project).resolve()
    work = Path(tempfile.mkdtemp(prefix="knoxmap-repeat-"))
    cells = [[0, 0, 3, 3], [4, 0, 7, 3], [8, 0, 11, 3], [12, 0, 15, 3]]
    try:
        out = []
        for name in ("one", "two"):
            dst = work / name / src.name
            (work / name).mkdir()
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("pictures", "lots", "compile_state.json*"))
            pzw = dst / f"{dst.name}.pzw"
            pzw.write_text(pzw.read_text(encoding="utf-8").replace(src.as_posix(), dst.as_posix()),
                           encoding="utf-8")
            compile_state.wipe(dst)
            compile_map.compile_map(str(dst), only_cells=cells, workers=args.workers)
            out.append(_hashes(dst / "lots"))
        a, b = out
        differ = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        print(f"{len(a)} files and {len(b)} files; {len(differ)} differ")
        if differ:
            print("  " + ", ".join(differ[:12]) + (" ..." if len(differ) > 12 else ""))
        print("REPEATABLE" if not differ else "NOT REPEATABLE")
        return 0 if not differ else 1
    finally:
        if args.keep:
            print(f"kept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
