#!/usr/bin/env python3
"""Split a long source file into overlapping <max_lines>-line chunks.
Creates <src>.chunk<N>.py files beside the original.
Usage:   python chunker.py big_file.py --max-lines 1200 --overlap 150
"""
from pathlib import Path
import argparse

def chunk(path: Path, max_lines: int, overlap: int):
    lines = path.read_text().splitlines()
    start = idx = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        Path(f"{path.stem}.chunk{idx}{path.suffix}").write_text("\n".join(lines[start:end]))
        if end == len(lines):
            break
        start, idx = end - overlap, idx + 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--max-lines", type=int, default=1200)
    ap.add_argument("--overlap", type=int, default=150)
    args = ap.parse_args()
    chunk(args.file, args.max_lines, args.overlap)
