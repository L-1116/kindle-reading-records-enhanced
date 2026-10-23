`stb_image.h` from https://github.com/nothings/stb/blob/f0569113c93ad095470c54bf34a17b36646bbbb5/stb_image.h
(v2.30). Dual public-domain / MIT license is included at the end of the header.
FBInk uses the same stb_image decoding family: https://github.com/NiLuJe/FBInk/blob/master/fbink.c

Only JPEG/PNG and the existing real-cover BMP/GIF formats are compiled. No
external device libraries. The helper runs only in the foreground dashboard,
caps input at 8 MiB / 12 megapixels / 8192 per dimension and Linux execution at
96 MiB address space / 5 CPU seconds. Generated RGB PPM previews fit 240×360 with
white letterboxing and alpha compositing. The v2 content namespace avoids old
lossy PGM previews. Valid generated PGM and PPM files share the 128-entry cache
limit; unrelated files, directories and symbolic links are never pruned.
