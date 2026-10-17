`stb_image.h` from https://github.com/nothings/stb/blob/f0569113c93ad095470c54bf34a17b36646bbbb5/stb_image.h
(v2.30). Dual public-domain / MIT license is included at the end of the header.
FBInk uses the same stb_image decoding family: https://github.com/NiLuJe/FBInk/blob/master/fbink.c

Only JPEG/PNG and the existing real-cover BMP/GIF formats are compiled. No
external device libraries. The helper runs only in the foreground dashboard,
caps input at 8 MiB / 12 megapixels / 8192 per dimension and Linux execution at
96 MiB address space / 5 CPU seconds. Generated PGM previews fit 240×360 with
white letterboxing; the cache is bounded to 128 content-addressed entries.
