#!/usr/bin/env python3
"""Analyze Dreaming Sarah PPM frame capture from EXP-138 run.
Reports: nonZero pixels, color count, SHA256, converts to PNG."""
import hashlib
import os
import sys
from collections import Counter

def analyze_ppm(path):
    with open(path, 'rb') as f:
        data = f.read()
    # Parse PPM P6 header
    # P6\n#comment\nW H\n255\n<pixel data>
    idx = 0
    # magic
    assert data[:2] == b'P6', f"Not a PPM P6 file: {data[:10]}"
    idx = 2
    # skip whitespace
    while data[idx] in b' \t\n\r': idx += 1
    # skip comment line
    if data[idx] == ord('#'):
        while data[idx] != ord('\n'): idx += 1
        idx += 1
    # width
    w_start = idx
    while data[idx] not in b' \t\n\r': idx += 1
    width = int(data[w_start:idx])
    while data[idx] in b' \t\n\r': idx += 1
    # height
    h_start = idx
    while data[idx] not in b' \t\n\r': idx += 1
    height = int(data[h_start:idx])
    while data[idx] in b' \t\n\r': idx += 1
    # maxval
    m_start = idx
    while data[idx] not in b' \t\n\r': idx += 1
    maxval = int(data[m_start:idx])
    # single whitespace
    idx += 1
    pixel_data = data[idx:]
    print(f"PPM header: {width}x{height} maxval={maxval}")
    print(f"Pixel data size: {len(pixel_data)} bytes (expected {width*height*3} for RGB or {width*height*4} for RGBA)")
    # The headless presenter writes RGBA (4 bytes/pixel) even though PPM P6 is RGB (3 bytes/pixel)
    # Let's check both interpretations
    expected_rgb = width * height * 3
    expected_rgba = width * height * 4
    print(f"Expected RGB: {expected_rgb}, RGBA: {expected_rgba}")
    # Count non-zero bytes
    non_zero_bytes = sum(1 for b in pixel_data if b != 0)
    print(f"Non-zero bytes: {non_zero_bytes} / {len(pixel_data)} ({100*non_zero_bytes/len(pixel_data):.2f}%)")
    # Treat as RGBA, count non-zero pixels (any channel non-zero)
    if len(pixel_data) >= expected_rgba:
        non_zero_pixels = 0
        colors = Counter()
        for i in range(0, expected_rgba, 4):
            r, g, b, a = pixel_data[i], pixel_data[i+1], pixel_data[i+2], pixel_data[i+3]
            if r != 0 or g != 0 or b != 0 or a != 0:
                non_zero_pixels += 1
                colors[(r, g, b, a)] += 1
        print(f"Non-zero pixels (RGBA): {non_zero_pixels} / {width*height} ({100*non_zero_pixels/(width*height):.2f}%)")
        print(f"Distinct colors (RGBA): {len(colors)}")
        if colors:
            print(f"Top 5 colors: {colors.most_common(5)}")
    # SHA256 of pixel data
    sha = hashlib.sha256(pixel_data).hexdigest()
    print(f"SHA256 (pixel data): {sha}")
    # SHA256 of whole file
    sha_file = hashlib.sha256(data).hexdigest()
    print(f"SHA256 (whole file): {sha_file}")
    return width, height, non_zero_bytes, sha

def convert_to_png(ppm_path, png_path):
    """Convert PPM to PNG using PIL if available, else skip."""
    try:
        from PIL import Image
        # Read PPM manually because PIL may not handle RGBA-as-PPM correctly
        with open(ppm_path, 'rb') as f:
            data = f.read()
        # Parse header (same as above)
        idx = 2
        while data[idx] in b' \t\n\r': idx += 1
        if data[idx] == ord('#'):
            while data[idx] != ord('\n'): idx += 1
            idx += 1
        w_start = idx
        while data[idx] not in b' \t\n\r': idx += 1
        width = int(data[w_start:idx])
        while data[idx] in b' \t\n\r': idx += 1
        h_start = idx
        while data[idx] not in b' \t\n\r': idx += 1
        height = int(data[h_start:idx])
        while data[idx] in b' \t\n\r': idx += 1
        m_start = idx
        while data[idx] not in b' \t\n\r': idx += 1
        idx += 1
        pixel_data = data[idx:]
        # Create RGBA image
        img = Image.frombytes('RGBA', (width, height), pixel_data[:width*height*4])
        img.save(png_path)
        print(f"PNG saved: {png_path} ({os.path.getsize(png_path)} bytes)")
        return True
    except ImportError:
        print("PIL not available, skipping PNG conversion")
        return False
    except Exception as e:
        print(f"PNG conversion failed: {e}")
        return False

if __name__ == '__main__':
    frame_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/ds-frames-exp138/frame000001.ppm'
    png_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp/ds-frames-exp138/frame000001.png'
    print(f"=== Analyzing {frame_path} ===")
    print()
    analyze_ppm(frame_path)
    print()
    convert_to_png(frame_path, png_path)
