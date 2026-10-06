"""Compile a copy of a built map with N workers and compare it to the original.

    python tools/compile_compare.py output/<map> --workers 6

The original map folder is never written to. It is copied to a temp folder, the
copy's .pzw is pointed at the copy (a .pzw holds absolute paths, so compiling a
plain copy would silently compile the original), its lots and tmx are cleared,
and it is compiled from scratch. Then every file under lots/ is compared byte
for byte against the original's, which has to have been compiled already.

Exit 0 when the two are identical, 1 when they are not.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))


def _hashes(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha1(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project", help="a compiled map folder, e.g. output/mymap")
    ap.add_argument("--workers", type=int, required=True)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--keep", action="store_true", help="keep the temp copy")
    args = ap.parse_args(argv)

    import compile_map

    src = Path(args.project).resolve()
    if not (src / "lots").is_dir() or not any((src / "lots").iterdir()):
        print(f"{src} has no compiled lots to compare against.", file=sys.stderr)
        return 1

    work = Path(tempfile.mkdtemp(prefix="knoxmap-compare-"))
    dst = work / src.name
    try:
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("lots", "tmx", "pictures"))
        pzw = dst / f"{src.name}.pzw"
        text = pzw.read_text(encoding="utf-8")
        old, new = src.as_posix(), dst.as_posix()
        if old not in text:
            print("the .pzw does not mention the map folder; cannot repoint it",
                  file=sys.stderr)
            return 1
        pzw.write_text(text.replace(old, new), encoding="utf-8")

        t0 = time.time()
        compile_map.compile_map(str(dst), batch=args.batch, workers=args.workers)
        print(f"compiled with {args.workers} workers in {time.time() - t0:.0f}s")

        a, b = _hashes(src / "lots"), _hashes(dst / "lots")
        missing = sorted(set(a) - set(b))
        extra = sorted(set(b) - set(a))
        differ = sorted(k for k in set(a) & set(b) if a[k] != b[k])
        print(f"original {len(a)} files, copy {len(b)} files")
        for label, names in (("missing from the copy", missing),
                             ("only in the copy", extra), ("different", differ)):
            if names:
                print(f"{len(names)} {label}: {', '.join(names[:8])}"
                      f"{' ...' if len(names) > 8 else ''}")
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
