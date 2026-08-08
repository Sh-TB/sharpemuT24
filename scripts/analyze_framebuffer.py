#!/usr/bin/env python3
"""Analyze framebuffer PNG content - extract dominant colors."""
from collections import Counter
from pathlib import Path
import zlib
import struct

def analyze_bgra(path, width, height):
    with open(path, 'rb') as f:
        data = f.read()
    expected = width * height * 4
    if len(data) < expected:
        return None
    colors = Counter()
    samples = 0
    total_r = total_g = total_b = 0
    min_r = min_g = min_b = 255
    max_r = max_g = max_b = 0
    unique_colors = set()
    for i in range(0, width * height, 100):
        b = data[i*4 + 0]
        g = data[i*4 + 1]
        r = data[i*4 + 2]
        a = data[i*4 + 3]
        qr = r >> 5
        qg = g >> 5
        qb = b >> 5
        unique_colors.add((qr, qg, qb))
        total_r += r
        total_g += g
        total_b += b
        if r < min_r: min_r = r
        if g < min_g: min_g = g
        if b < min_b: min_b = b
        if r > max_r: max_r = r
        if g > max_g: max_g = g
        if b > max_b: max_b = b
        colors[(qr, qg, qb)] += 1
        samples += 1
    avg_r = total_r / samples
    avg_g = total_g / samples
    avg_b = total_b / samples
    print(f"\n=== {Path(path).name} ===")
    print(f"  Size: {width}x{height}")
    print(f"  Avg color: R={avg_r:.0f} G={avg_g:.0f} B={avg_b:.0f}")
    print(f"  Min: R={min_r} G={min_g} B={min_b}")
    print(f"  Max: R={max_r} G={max_g} B={max_b}")
    print(f"  Unique quantized colors: {len(unique_colors)}")
    print(f"  Top 5 dominant colors (R,G,B quantized to 32 levels):")
    for color, count in colors.most_common(5):
        pct = count * 100 / samples
        actual = (color[0] * 32, color[1] * 32, color[2] * 32)
        print(f"    RGB~{actual}: {pct:.1f}%")

if __name__ == '__main__':
    fb_dir = Path('/home/z/my-project/download/framebuffers')
    files = sorted([f for f in fb_dir.iterdir() if f.suffix == '.bgra'])
    indices = [0, 49, 99, 168]
    for i in indices:
        if i >= len(files):
            continue
        f = files[i]
        parts = f.stem.split('-')
        if len(parts) >= 3:
            try:
                w, h = map(int, parts[2].split('x'))
                analyze_bgra(str(f), w, h)
            except:
                pass
