"""
steganography.py — Image Steganography CLI Tool
================================================
Portfolio Project #7 | Don Achema (@Don-cybertech)

Hides secret messages inside PNG/BMP images using
Least Significant Bit (LSB) substitution.
Optionally encrypts the message with AES-256 before hiding it.

Commands
--------
  encode  – Embed a message into a cover image
  decode  – Extract a hidden message from a stego image
  inspect – Show steganography capacity of an image

Examples
--------
  python steganography.py encode -i cover.png -m "secret" -o stego.png
  python steganography.py encode -i cover.png -f secret.txt -o stego.png -p mypassword
  python steganography.py decode -i stego.png
  python steganography.py decode -i stego.png -p mypassword
  python steganography.py inspect -i cover.png
"""

import argparse
import sys
import getpass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.text import Text
from rich.rule import Rule

import lsb_engine
import crypto_utils


console = Console()

BANNER = """
[bold cyan]███████╗████████╗███████╗ ██████╗  █████╗ ███╗   ██╗ ██████╗ [/bold cyan]
[bold cyan]██╔════╝╚══██╔══╝██╔════╝██╔════╝ ██╔══██╗████╗  ██║██╔═══██╗[/bold cyan]
[bold cyan]███████╗   ██║   █████╗  ██║  ███╗███████║██╔██╗ ██║██║   ██║[/bold cyan]
[bold cyan]╚════██║   ██║   ██╔══╝  ██║   ██║██╔══██║██║╚██╗██║██║   ██║[/bold cyan]
[bold cyan]███████║   ██║   ███████╗╚██████╔╝██║  ██║██║ ╚████║╚██████╔╝[/bold cyan]
[bold cyan]╚══════╝   ╚═╝   ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ [/bold cyan]
[dim]LSB Image Steganography Tool  |  Portfolio Project #7[/dim]
"""


# ── CLI Setup ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steganography",
        description="Hide secret messages inside PNG/BMP images using LSB steganography.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── encode ──────────────────────────────────────────────────────────────────
    enc = sub.add_parser("encode", help="Hide a message inside a cover image")
    enc.add_argument("-i", "--image",   required=True, help="Path to cover image (PNG/BMP)")
    enc.add_argument("-o", "--output",  required=True, help="Path to save the stego image")
    enc.add_argument("-m", "--message", help="Secret message text (inline)")
    enc.add_argument("-f", "--file",    help="Path to a text/binary file to hide")
    enc.add_argument("-p", "--password",help="Encrypt payload with this password (optional)")
    enc.add_argument("--ask-password",  action="store_true",
                     help="Prompt for password without showing it on screen")

    # ── decode ──────────────────────────────────────────────────────────────────
    dec = sub.add_parser("decode", help="Extract a hidden message from a stego image")
    dec.add_argument("-i", "--image",    required=True, help="Path to stego image")
    dec.add_argument("-o", "--output",   help="Save extracted payload to this file")
    dec.add_argument("-p", "--password", help="Decryption password (if message was encrypted)")
    dec.add_argument("--ask-password",   action="store_true",
                     help="Prompt for password without showing it on screen")

    # ── inspect ─────────────────────────────────────────────────────────────────
    ins = sub.add_parser("inspect", help="Show steganography capacity of an image")
    ins.add_argument("-i", "--image", required=True, help="Path to image")

    return parser


# ── Helpers ────────────────────────────────────────────────────────────────────

def resolve_password(args) -> str | None:
    if args.ask_password:
        return getpass.getpass("Enter password: ")
    return args.password if hasattr(args, "password") else None


def print_banner():
    console.print(BANNER)


def print_stats_table(stats: dict):
    table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    table.add_column("Field",  style="bold dim", min_width=20)
    table.add_column("Value",  style="green")

    table.add_row("Cover image",    stats["cover"])
    table.add_row("Output image",   stats["output"])
    table.add_row("Image size",     stats["image_size"])
    table.add_row("Image capacity", f"{stats['capacity_bytes']:,} bytes")
    table.add_row("Payload size",   f"{stats['payload_bytes']:,} bytes")
    table.add_row("Bits used",      f"{stats['bits_used']:,} / {stats['bits_total']:,}")
    table.add_row("Utilisation",    f"{stats['utilisation_pct']}%")

    console.print(table)


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_encode(args):
    console.print(Rule("[bold cyan]ENCODE[/bold cyan]"))

    # Validate input
    if not args.message and not args.file:
        console.print("[red]✗[/red] Provide a message with [cyan]-m[/cyan] or a file with [cyan]-f[/cyan].")
        sys.exit(1)
    if args.message and args.file:
        console.print("[red]✗[/red] Use either [cyan]-m[/cyan] or [cyan]-f[/cyan], not both.")
        sys.exit(1)

    # Load payload
    if args.message:
        payload = args.message.encode("utf-8")
        console.print(f"[dim]Payload:[/dim] text message ({len(payload)} bytes)")
    else:
        fp = Path(args.file)
        if not fp.exists():
            console.print(f"[red]✗[/red] File not found: {fp}")
            sys.exit(1)
        payload = fp.read_bytes()
        console.print(f"[dim]Payload:[/dim] file [cyan]{fp.name}[/cyan] ({len(payload):,} bytes)")

    # Optional encryption
    password = resolve_password(args)
    if password:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Encrypting payload...[/cyan]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("enc", total=None)
            payload = crypto_utils.encrypt(payload, password)
        console.print("[bold green]✓[/bold green] Payload encrypted (AES-256 / Fernet + PBKDF2)")

    # Encode
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Embedding bits into image...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("embed", total=None)
        try:
            stats = lsb_engine.encode(args.image, payload, args.output)
        except (ValueError, FileNotFoundError) as exc:
            console.print(f"[red]✗ Error:[/red] {exc}")
            sys.exit(1)

    console.print("[bold green]✓[/bold green] Message hidden successfully!\n")
    print_stats_table(stats)

    if password:
        console.print("\n[yellow]⚠[/yellow]  Remember your password — it is required to decode.")
    console.print(f"\n[dim]Stego image saved to:[/dim] [bold]{stats['output']}[/bold]")


def cmd_decode(args):
    console.print(Rule("[bold cyan]DECODE[/bold cyan]"))

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Scanning image for hidden payload...[/cyan]"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("scan", total=None)
        try:
            payload = lsb_engine.decode(args.image)
        except (ValueError, FileNotFoundError) as exc:
            console.print(f"[red]✗ Error:[/red] {exc}")
            sys.exit(1)

    console.print(f"[bold green]✓[/bold green] Hidden payload found: [cyan]{len(payload):,} bytes[/cyan]")

    # Optional decryption
    password = resolve_password(args)
    if password:
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Decrypting...[/cyan]"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("dec", total=None)
            try:
                payload = crypto_utils.decrypt(payload, password)
            except ValueError as exc:
                console.print(f"[red]✗ Decryption failed:[/red] {exc}")
                sys.exit(1)
        console.print("[bold green]✓[/bold green] Decrypted successfully")

    # Output
    if args.output:
        out_path = Path(args.output)
        out_path.write_bytes(payload)
        console.print(f"\n[bold green]✓[/bold green] Payload saved to [bold]{out_path}[/bold]")
    else:
        # Try to display as text
        console.print(Rule("[dim]Extracted Message[/dim]"))
        try:
            text = payload.decode("utf-8")
            console.print(
                Panel(text, title="[bold cyan]Hidden Message[/bold cyan]",
                      border_style="cyan", padding=(1, 2))
            )
        except UnicodeDecodeError:
            console.print(
                "[yellow]⚠[/yellow]  Payload is binary data. "
                "Use [cyan]-o <filename>[/cyan] to save it to a file."
            )
            console.print(f"[dim]Raw bytes (hex preview):[/dim] {payload[:32].hex()} ...")


def cmd_inspect(args):
    console.print(Rule("[bold cyan]INSPECT[/bold cyan]"))

    image_path = Path(args.image)
    if not image_path.exists():
        console.print(f"[red]✗[/red] Image not found: {image_path}")
        sys.exit(1)

    if image_path.suffix.lower() not in lsb_engine.SUPPORTED_FORMATS:
        console.print(
            f"[red]✗[/red] Unsupported format '{image_path.suffix}'. Use PNG or BMP."
        )
        sys.exit(1)

    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    total_pixels = w * h
    total_bits = total_pixels * lsb_engine.CHANNELS_PER_PIXEL
    usable_bytes = (total_bits - lsb_engine.HEADER_BITS) // 8

    table = Table(box=box.ROUNDED, show_header=False, border_style="cyan")
    table.add_column("Field", style="bold dim", min_width=24)
    table.add_column("Value", style="green")

    table.add_row("Image",            str(image_path))
    table.add_row("Dimensions",       f"{w} × {h} pixels")
    table.add_row("Total pixels",     f"{total_pixels:,}")
    table.add_row("Total LSB bits",   f"{total_bits:,}")
    table.add_row("Max payload",      f"{usable_bytes:,} bytes  ({usable_bytes / 1024:.1f} KB)")
    table.add_row("Overhead (header)", f"{lsb_engine.HEADER_BITS} bits (4 bytes)")
    table.add_row("Technique",        "LSB substitution — 1 bit per channel (R, G, B)")

    console.print(table)
    console.print(
        f"\n[dim]Tip:[/dim] A [cyan]1280×720[/cyan] image can hide up to "
        f"[bold]{(1280*720*3 - 32) // 8 // 1024}[/bold] KB of data invisibly."
    )


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    print_banner()
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "encode":
            cmd_encode(args)
        elif args.command == "decode":
            cmd_decode(args)
        elif args.command == "inspect":
            cmd_inspect(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
