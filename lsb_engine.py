"""
lsb_engine.py — Core LSB Steganography Engine
================================================
Hides/extracts arbitrary byte payloads inside PNG/BMP images
by overwriting the Least Significant Bit of each RGB channel.

Payload layout inside the image:
  [32-bit length header] [payload bits] ... [padding]

The 32-bit header stores the exact byte-length of the payload so
extraction knows precisely how many bits to read — no delimiter
scanning needed (faster and more robust).
"""

from PIL import Image
from pathlib import Path
from typing import Union
import struct


# ── Constants ──────────────────────────────────────────────────────────────────

SUPPORTED_FORMATS = {".png", ".bmp"}
HEADER_BITS = 32          # 4-byte unsigned int → max payload ~536 MB
CHANNELS_PER_PIXEL = 3    # R, G, B  (alpha ignored to stay format-safe)


# ── Bit utilities ──────────────────────────────────────────────────────────────

def _bytes_to_bits(data: bytes) -> list[int]:
    """Convert bytes → flat list of bits (MSB first)."""
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits


def _bits_to_bytes(bits: list[int]) -> bytes:
    """Convert flat list of bits (MSB first) → bytes."""
    result = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i : i + 8]
        if len(chunk) < 8:
            break
        byte = 0
        for b in chunk:
            byte = (byte << 1) | b
        result.append(byte)
    return bytes(result)


# ── Capacity helpers ───────────────────────────────────────────────────────────

def max_payload_bytes(image_path: Union[str, Path]) -> int:
    """Return the maximum number of payload bytes an image can carry."""
    img = Image.open(image_path).convert("RGB")
    total_bits = img.width * img.height * CHANNELS_PER_PIXEL
    usable_bits = total_bits - HEADER_BITS
    return usable_bits // 8


# ── Encode ─────────────────────────────────────────────────────────────────────

def encode(
    cover_path: Union[str, Path],
    payload: bytes,
    output_path: Union[str, Path],
) -> dict:
    """
    Embed *payload* bytes into *cover_path* and save to *output_path*.

    Returns a dict with encoding statistics.

    Raises:
        ValueError  – unsupported format or payload too large
        FileNotFoundError – cover image not found
    """
    cover_path = Path(cover_path)
    output_path = Path(output_path)

    if cover_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format '{cover_path.suffix}'. Use PNG or BMP."
        )
    if not cover_path.exists():
        raise FileNotFoundError(f"Cover image not found: {cover_path}")

    img = Image.open(cover_path).convert("RGB")
    pixels = img.load()
    width, height = img.size

    capacity_bits = width * height * CHANNELS_PER_PIXEL
    payload_bits = len(payload) * 8
    required_bits = HEADER_BITS + payload_bits

    if required_bits > capacity_bits:
        raise ValueError(
            f"Payload too large: need {required_bits} bits, "
            f"image holds {capacity_bits} bits "
            f"({capacity_bits // 8 - 4} usable bytes)."
        )

    # Build the full bit-stream: 32-bit length + payload bits
    header = struct.pack(">I", len(payload))   # big-endian unsigned int
    bitstream = _bytes_to_bits(header) + _bytes_to_bits(payload)

    # Embed bits LSB-first into pixels
    bit_idx = 0
    total_bits = len(bitstream)

    for y in range(height):
        for x in range(width):
            if bit_idx >= total_bits:
                break
            r, g, b = pixels[x, y]
            channels = [r, g, b]
            for c in range(CHANNELS_PER_PIXEL):
                if bit_idx < total_bits:
                    channels[c] = (channels[c] & 0xFE) | bitstream[bit_idx]
                    bit_idx += 1
            pixels[x, y] = (channels[0], channels[1], channels[2])
        if bit_idx >= total_bits:
            break

    img.save(output_path, "PNG")   # always save as PNG to avoid lossy re-encoding

    return {
        "cover": str(cover_path),
        "output": str(output_path),
        "image_size": f"{width}x{height}",
        "capacity_bytes": (capacity_bits - HEADER_BITS) // 8,
        "payload_bytes": len(payload),
        "bits_used": required_bits,
        "bits_total": capacity_bits,
        "utilisation_pct": round(required_bits / capacity_bits * 100, 2),
    }


# ── Decode ─────────────────────────────────────────────────────────────────────

def decode(stego_path: Union[str, Path]) -> bytes:
    """
    Extract the hidden payload from *stego_path*.

    Returns the raw payload bytes.

    Raises:
        ValueError  – no valid payload found
        FileNotFoundError – stego image not found
    """
    stego_path = Path(stego_path)
    if not stego_path.exists():
        raise FileNotFoundError(f"Stego image not found: {stego_path}")

    img = Image.open(stego_path).convert("RGB")
    pixels = img.load()
    width, height = img.size

    # Harvest all LSBs
    all_bits: list[int] = []
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            all_bits.extend([r & 1, g & 1, b & 1])

    # Read 32-bit header
    if len(all_bits) < HEADER_BITS:
        raise ValueError("Image too small to contain a valid payload.")

    length_bytes = _bits_to_bytes(all_bits[:HEADER_BITS])
    payload_length = struct.unpack(">I", length_bytes)[0]

    max_possible = (len(all_bits) - HEADER_BITS) // 8
    if payload_length == 0 or payload_length > max_possible:
        raise ValueError(
            "No hidden message detected, or image has not been encoded with this tool."
        )

    # Extract payload
    payload_bits = all_bits[HEADER_BITS : HEADER_BITS + payload_length * 8]
    return _bits_to_bytes(payload_bits)
