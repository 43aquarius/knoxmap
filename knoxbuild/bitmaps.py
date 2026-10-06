"""Read the map's bitmaps without holding three copies of them.

``np.array(Image.open(p).convert("RGB"))`` decodes the file into a PIL image,
converts it into a second one and copies that into an array: about three times
the bitmap at once. A 285 Mpx map is 855 MB as an array, so that was 2.5 GB
before the building step had done anything.

The renderer writes plain 24-bit (landscape, vegetation) and 8-bit (road
hierarchy) BMPs. For those the pixels are read straight off the disk a strip of
rows at a time into one preallocated array, so the peak is the array and a
strip. Any other BMP, or a file this cannot make sense of, goes through Pillow
as before.
"""
from __future__ import annotations

import os
import struct

import numpy as np
from PIL import Image

STRIP_ROWS = 256


def _bmp_header(path: str):
    """(width, height, bottom_up, bits, data_offset) of a plain BMP, else None."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(54)
    except OSError:
        return None
    if len(head) < 54 or head[:2] != b"BM":
        return None
    offset, = struct.unpack_from("<I", head, 10)
    size, width, height, planes, bits, compression = struct.unpack_from(
        "<IiiHHI", head, 14)
    if size < 40 or compression != 0 or planes != 1 or width <= 0 or height == 0:
        return None
    return width, abs(height), height > 0, bits, offset


def _fast(path: str, bits_wanted: int, crop):
    hdr = _bmp_header(path)
    if hdr is None or hdr[3] != bits_wanted:
        return None
    width, height, bottom_up, bits, offset = hdr
    bpp = bits // 8
    stride = (width * bpp + 3) // 4 * 4
    if os.path.getsize(path) < offset + stride * height:
        return None
    out_h, out_w = height, width
    if crop is not None:
        out_h, out_w = min(crop[0], height), min(crop[1], width)
    shape = (out_h, out_w, 3) if bpp == 3 else (out_h, out_w)
    out = np.empty(shape, dtype=np.uint8)
    raw = np.memmap(path, dtype=np.uint8, mode="r", offset=offset,
                    shape=(height, stride))
    try:
        for top in range(0, out_h, STRIP_ROWS):
            bottom = min(top + STRIP_ROWS, out_h)
            if bottom_up:
                # File row 0 is the bottom of the picture.
                src = raw[height - bottom:height - top][::-1]
            else:
                src = raw[top:bottom]
            if bpp == 3:
                px = src[:, :out_w * 3].reshape(bottom - top, out_w, 3)
                out[top:bottom] = px[:, :, ::-1]          # BGR -> RGB
            else:
                out[top:bottom] = src[:, :out_w]
    finally:
        del raw
    return out


def read_rgb(path: str, crop: tuple[int, int] | None = None) -> np.ndarray:
    """The picture as a (height, width, 3) uint8 array. `crop` is (rows, cols)."""
    arr = _fast(path, 24, crop)
    if arr is not None:
        return arr
    with Image.open(path) as img:
        arr = np.array(img.convert("RGB"))
    return arr[:crop[0], :crop[1]] if crop else arr


def read_gray(path: str, crop: tuple[int, int] | None = None) -> np.ndarray:
    """The picture as a (height, width) uint8 array of grey levels."""
    arr = _fast(path, 8, crop)
    if arr is not None:
        # An 8-bit BMP is palette indices; the renderer writes a grey ramp, so
        # they are the grey levels. Check, rather than trust it.
        with Image.open(path) as img:
            pal = img.getpalette()
        if pal is None or all(pal[i * 3] == i for i in range(256)
                              if i * 3 < len(pal)):
            return arr
    with Image.open(path) as img:
        arr = np.array(img.convert("L"))
    return arr[:crop[0], :crop[1]] if crop else arr


def same_colour(rgb: np.ndarray, colour) -> np.ndarray:
    """Boolean mask of the pixels equal to `colour`, without the (h, w, 3)
    boolean that ``np.all(rgb == colour, axis=2)`` builds."""
    r, g, b = colour[:3]
    mask = rgb[:, :, 0] == r
    mask &= rgb[:, :, 1] == g
    mask &= rgb[:, :, 2] == b
    return mask
