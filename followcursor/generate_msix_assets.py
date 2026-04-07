"""Generate MSIX visual assets from the FollowCursor app icon.

Produces the PNG files required by AppxManifest.xml:
  - Square44x44Logo.png   (44×44)
  - Square150x150Logo.png (150×150)
  - Square310x310Logo.png (310×310)
  - Wide310x150Logo.png   (310×150)
  - StoreLogo.png          (50×50)
  - SplashScreen.png       (620×300)

Can be run from any working directory; paths are resolved relative to this file.
Output goes to msix/Assets/.

Requires only Pillow (no Qt/PySide6 needed).
"""

import os

from PIL import Image

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "msix", "Assets")
ICO_PATH = os.path.join(os.path.dirname(__file__), "followcursor.ico")
BG_COLOR = (27, 26, 46, 255)  # #1b1a2e fully opaque

SIZES = {
    "Square44x44Logo.png": (44, 44),
    "Square150x150Logo.png": (150, 150),
    "Square310x310Logo.png": (310, 310),
    "Wide310x150Logo.png": (310, 150),
    "StoreLogo.png": (50, 50),
    "SplashScreen.png": (620, 300),
}


def _load_largest_icon() -> Image.Image:
    """Load the highest-resolution frame from the .ico file."""
    with Image.open(ICO_PATH) as ico:
        sizes = ico.info.get("sizes", [(ico.width, ico.height)])
        largest = max(sizes, key=lambda s: s[0] * s[1])
        ico.size = largest  # type: ignore[assignment]
        ico.load()
        return ico.convert("RGBA")


def main() -> None:
    source = _load_largest_icon()
    os.makedirs(ASSETS_DIR, exist_ok=True)

    for filename, (w, h) in SIZES.items():
        tile = Image.new("RGBA", (w, h), BG_COLOR)
        # Centre the icon with 25 % padding on the shorter axis
        icon_size = int(min(w, h) * 0.75)
        resized = source.resize((icon_size, icon_size), Image.LANCZOS)
        x = (w - icon_size) // 2
        y = (h - icon_size) // 2
        tile.paste(resized, (x, y), mask=resized)
        out_path = os.path.join(ASSETS_DIR, filename)
        tile.save(out_path, "PNG")
        print(f"  {filename} ({w}×{h})")

    print(f"Assets written to {ASSETS_DIR}")


if __name__ == "__main__":
    main()
