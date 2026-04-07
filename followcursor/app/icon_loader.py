"""Icon loader for Fluent UI System Icons with theme-aware coloring."""

import logging
from typing import Dict, Optional
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, QRectF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer

logger = logging.getLogger(__name__)

# Icon cache to avoid reloading the same icon multiple times
_ICON_CACHE: Dict[str, QIcon] = {}

# Path to the icons directory
_ICONS_DIR = Path(__file__).parent / "icons"


def load_icon(
    name: str,
    size: int = 20,
    variant: str = "regular",
    color: Optional[str] = None,
) -> QIcon:
    """Load a Fluent UI System Icon with optional color replacement.

    Args:
        name: Icon name (e.g., "record", "play", "save")
        size: Icon size in pixels (default: 20)
        variant: Icon variant - "regular" or "filled" (default: "regular")
        color: Optional color to apply (hex string or rgba). If None, uses default SVG color.

    Returns:
        QIcon object ready to use in Qt widgets

    Example:
        >>> from . import tokens as T
        >>> icon = load_icon("record", size=20, variant="filled", color=T.BRAND)
        >>> button.setIcon(icon)
    """
    # Build cache key
    cache_key = f"{name}_{size}_{variant}_{color or 'default'}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    # Build file path
    svg_file = _ICONS_DIR / f"{name}_{size}_{variant}.svg"
    if not svg_file.exists():
        logger.warning(f"Icon file not found: {svg_file}")
        return QIcon()  # Return empty icon as fallback

    try:
        # Read SVG content
        svg_content = svg_file.read_text(encoding="utf-8")

        # Apply color if specified
        if color:
            # Replace the fill color in the SVG
            # Fluent icons typically use fill="#212121" or similar
            svg_content = _apply_color(svg_content, color)

        # Render SVG to QPixmap
        svg_bytes = QByteArray(svg_content.encode("utf-8"))
        renderer = QSvgRenderer(svg_bytes)
        
        if not renderer.isValid():
            logger.warning(f"Invalid SVG content in: {svg_file}")
            return QIcon()

        # Create pixmap with the requested size
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
        
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()

        # Create icon from pixmap
        icon = QIcon(pixmap)
        
        # Cache it
        _ICON_CACHE[cache_key] = icon
        
        return icon

    except Exception:
        logger.exception(f"Failed to load icon {name}")
        return QIcon()


def _apply_color(svg_content: str, color: str) -> str:
    """Replace fill color in SVG content with the specified color.

    Args:
        svg_content: Original SVG content as string
        color: Color to apply (hex string like "#8b5cf6" or rgba string like "rgba(139, 92, 246, 1)")

    Returns:
        Modified SVG content with color applied
    """
    # Convert rgba() to hex if needed
    if color.startswith("rgba("):
        color = _rgba_to_hex(color)

    # Replace fill attributes
    # Fluent icons use fill="#212121" or fill='#212121'
    import re
    
    # Replace fill="#..." with our color
    svg_content = re.sub(r'fill="#[0-9a-fA-F]{6}"', f'fill="{color}"', svg_content)
    svg_content = re.sub(r"fill='#[0-9a-fA-F]{6}'", f"fill='{color}'", svg_content)
    
    # Also handle style attributes like style="fill:#..."
    svg_content = re.sub(r'fill:#[0-9a-fA-F]{6}', f'fill:{color}', svg_content)

    return svg_content


def _rgba_to_hex(rgba_str: str) -> str:
    """Convert rgba(r, g, b, a) string to #RRGGBB hex.

    Args:
        rgba_str: String like "rgba(139, 92, 246, 1)"

    Returns:
        Hex color string like "#8b5cf6"
    """
    import re
    match = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)", rgba_str)
    if match:
        r, g, b = map(int, match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    return "#212121"  # Fallback to default dark gray


def clear_cache() -> None:
    """Clear the icon cache. Useful when theme changes."""
    global _ICON_CACHE
    _ICON_CACHE.clear()
    logger.debug("Icon cache cleared")
