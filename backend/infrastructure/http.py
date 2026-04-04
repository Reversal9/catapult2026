from __future__ import annotations

import json
import struct
import zlib
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
USER_AGENT = "catapult2026-infrastructure-pipeline/1.0"


def http_get_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urlopen(request, timeout=20) as response:
        return response.read()


def http_get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    return json.loads(http_get_bytes(url, headers=headers).decode("utf-8"))


def http_post_json(
    url: str,
    payload: dict,
    headers: dict[str, str] | None = None,
) -> bytes:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        return response.read()


def http_post_form(
    url: str,
    fields: dict[str, str],
    headers: dict[str, str] | None = None,
) -> bytes:
    request = Request(
        url,
        data=urlencode(fields).encode("utf-8"),
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            **(headers or {}),
        },
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        return response.read()


def paeth_predictor(a: int, b: int, c: int) -> int:
    prediction = a + b - c
    pa = abs(prediction - a)
    pb = abs(prediction - b)
    pc = abs(prediction - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png_rows(raw: bytes) -> tuple[int, int, list[list[tuple[int, int, int, int]]]]:
    if not raw.startswith(PNG_SIGNATURE):
        raise ValueError("Unsupported image format. Expected PNG.")

    width = 0
    height = 0
    bit_depth = 0
    color_type = 0
    interlace_method = 0
    compressed = bytearray()

    offset = len(PNG_SIGNATURE)
    while offset < len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        offset += 4
        chunk_type = raw[offset : offset + 4]
        offset += 4
        chunk_data = raw[offset : offset + length]
        offset += length + 4

        if chunk_type == b"IHDR":
            (
                width,
                height,
                bit_depth,
                color_type,
                _compression_method,
                _filter_method,
                interlace_method,
            ) = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if bit_depth != 8 or interlace_method != 0 or color_type not in {2, 6}:
        raise ValueError("Only non-interlaced 8-bit RGB/RGBA PNG imagery is supported.")

    bytes_per_pixel = 3 if color_type == 2 else 4
    stride = width * bytes_per_pixel
    payload = zlib.decompress(bytes(compressed))

    rows: list[list[tuple[int, int, int, int]]] = []
    previous = bytearray(stride)
    cursor = 0

    for _ in range(height):
        filter_type = payload[cursor]
        cursor += 1
        row = bytearray(payload[cursor : cursor + stride])
        cursor += stride

        if filter_type == 1:
            for index in range(stride):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                row[index] = (row[index] + left) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                row[index] = (row[index] + previous[index]) & 0xFF
        elif filter_type == 3:
            for index in range(stride):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                up = previous[index]
                row[index] = (row[index] + ((left + up) // 2)) & 0xFF
        elif filter_type == 4:
            for index in range(stride):
                left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                up = previous[index]
                up_left = previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
                row[index] = (row[index] + paeth_predictor(left, up, up_left)) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"Unsupported PNG filter type: {filter_type}")

        pixel_row: list[tuple[int, int, int, int]] = []
        for start in range(0, stride, bytes_per_pixel):
            if bytes_per_pixel == 3:
                red, green, blue = row[start : start + 3]
                alpha = 255
            else:
                red, green, blue, alpha = row[start : start + 4]
            pixel_row.append((red, green, blue, alpha))
        rows.append(pixel_row)
        previous = row

    return width, height, rows
