from PIL import Image as _Image

# Pillow's decompression-bomb guard (~179 Mpx) rejects big maps' own bitmaps;
# see knoxbuild/__init__.py.
_Image.MAX_IMAGE_PIXELS = None
