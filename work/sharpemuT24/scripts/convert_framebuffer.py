#!/usr/bin/env python3
"""Convert SharpEmu BGRA framebuffer dumps at specific indices to PNG."""
import struct
import zlib
import sys
from pathlib import Path

def bgra_to_png(bgra_path, png_path, width, height):
    with open(bgra_path, 'rb') as f:
        data = f.read()
    expected = width * height * 4
    if len(data) < expected:
        print(f"ERROR: file too small: {len(data)} < {expected}")
        return False
    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        b = data[i*4 + 0]
        g = data[i*4 + 1]
        r = data[i*4 + 2]
        a = data[i*4 + 3]
        rgba[i*4 + 0] = r
        rgba[i*4 + 1] = g
        rgba[i*4 + 2] = b
        rgba[i*4 + 3] = a

    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        crc = zlib.crc32(chunk) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', crc)

    png = b'\x89PNG\r\n\x1a\n'
    png += make_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y*width*4:(y+1)*width*4])
    compressed = zlib.compress(bytes(raw), 9)
    png += make_chunk(b'IDAT', compressed)
    png += make_chunk(b'IEND', b'')
    with open(png_path, 'wb') as f:
        f.write(png)
    print(f"  Converted {bgra_path.name} -> {png_path.name} ({width}x{height}, {len(png)} bytes)")
    return True

if __name__ == '__main__':
    fb_dir = Path('/home/z/my-project/download/framebuffers')
    out_dir = Path('/home/z/my-project/download')
    files = sorted([f for f in fb_dir.iterdir() if f.suffix == '.bgra'])
    print(f"Total framebuffer files: {len(files)}")
    # Indices requested: 001, 050, 100, 169 (1-indexed)
    # Convert to 0-indexed: 0, 49, 99, 168
    target_indices = [0, 49, 99, min(168, len(files)-1)]
    print(f"Converting indices: {target_indices}")
    for i in target_indices:
        if i >= len(files):
            continue
        f = files[i]
        parts = f.stem.split('-')
        if len(parts) >= 3:
            try:
                w, h = map(int, parts[2].split('x'))
                # Name as framebuffer_001, framebuffer_050, etc (1-indexed)
                png_name = f"framebuffer_{i+1:03d}_{w}x{h}.png"
                png_path = out_dir / png_name
                bgra_to_png(str(f), str(png_path), w, h)
            except Exception as e:
                print(f"  ERROR for {f.name}: {e}")
