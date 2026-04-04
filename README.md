# Project 07 — Image Steganography Tool (LSB)

> **Portfolio Project #7** | Cybersecurity Python Projects  
> Author: Don Achema ([@Don-cybertech](https://github.com/Don-cybertech))

Hide secret messages inside PNG/BMP images using **Least Significant Bit (LSB)** substitution — optionally protected with **AES-256 encryption**.

---

## Screenshots

### 1. Inspecting the cover image capacity
![Inspect cover image](screenshots/01_inspect.png)

### 2. Encoding a secret message into the image
![Encode message](screenshots/02_encode.png)

### 3. Decoding the hidden message from the stego image
![Decode message](screenshots/03_decode.png)

---

## How LSB Steganography Works

Each pixel in an image has three colour channels: **Red**, **Green**, **Blue** — each stored as an 8-bit integer (0–255).

The *least significant bit* (the last bit) contributes only ±1 to the colour value. Flipping it is completely invisible to the human eye.

```
Original pixel channel:  10110110  (182)
                                 ^
                          This bit carries 1 unit of colour.
                          We replace it with our secret data.

After embedding bit '1':  10110111  (183)  ← change of just 1/255
After embedding bit '0':  10110110  (182)  ← unchanged
```

For a **1920×1080** image:
- `1920 × 1080 × 3 channels = 6,220,800 usable bits`
- That's **≈ 776 KB** of hidden data in a single photo.

---

## Architecture

```
07_steganography/
├── steganography.py    # CLI entry point (Rich interface)
├── lsb_engine.py       # Core encode/decode logic
├── crypto_utils.py     # AES-256 / Fernet encryption layer
└── requirements.txt
```

### Payload Layout Inside the Image

```
[ 32-bit length header ] [ payload bits ... ] [ unused pixels untouched ]
```

The 4-byte header stores the exact payload length so extraction is deterministic — no delimiter scanning.

---

## Setup

```cmd
cd 07_steganography
pip install -r requirements.txt
```

---

## Usage

### Hide a text message
```cmd
python steganography.py encode -i cover.png -m "Meet me at the bridge" -o stego.png
```

### Hide a text message with encryption
```cmd
python steganography.py encode -i cover.png -m "Top secret" -o stego.png -p mypassword
```

### Hide any file (binary or text)
```cmd
python steganography.py encode -i cover.png -f secret_document.txt -o stego.png
```

### Extract a message
```cmd
python steganography.py decode -i stego.png
```

### Extract an encrypted message
```cmd
python steganography.py decode -i stego.png -p mypassword
```

### Extract and save to file
```cmd
python steganography.py decode -i stego.png -o recovered.txt
```

### Check image capacity
```cmd
python steganography.py inspect -i cover.png
```

---

## Security Design

| Layer | What it does |
|---|---|
| **Steganography** | Hides the *existence* of the message |
| **AES-256 (Fernet)** | Protects the *content* if the image is found |
| **PBKDF2-SHA256** | Derives a strong key from your password (390,000 iterations) |
| **Random salt** | Prevents pre-computation / rainbow table attacks |

> ⚠️ Use PNG or BMP as your cover image. JPEG recompression destroys hidden bits.

---

## Skills Demonstrated

- Binary manipulation (bit-level operations)
- Image processing with Pillow
- AES-256 symmetric encryption
- PBKDF2 key derivation
- Argparse CLI design
- Rich terminal output
- Python `struct` for binary framing
