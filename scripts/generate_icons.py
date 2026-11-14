#!/usr/bin/env python3
"""Generate GIS-themed icons for Universal AI GIS Studio plugin.

Creates professional PNG icons at 24x24, 48x48, and 128x128 sizes
with a blue/green color scheme featuring map pin, layers, and globe symbols.
"""

from PIL import Image, ImageDraw
import os


# Color palette - GIS professional blue/green theme
COLORS = {
    "bg_primary": (0x1E, 0x3A, 0x5F),      # Dark navy blue
    "bg_secondary": (0x2C, 0x5F, 0x8A),    # Medium blue
    "accent_blue": (0x00, 0x96, 0xD6),     # Bright blue
    "accent_green": (0x2E, 0xCC, 0x71),    # Emerald green
    "accent_teal": (0x00, 0xB4, 0xD8),     # Teal
    "white": (0xFF, 0xFF, 0xFF),
    "white_transparent": (0xFF, 0xFF, 0xFF, 0),
    "pin_red": (0xE7, 0x4C, 0x3C),         # Map pin red
    "pin_dark": (0xC0, 0x39, 0x2B),        # Darker pin red
    "layer_blue": (0x34, 0x98, 0xDB),      # Layer blue
    "layer_green": (0x27, 0xAE, 0x60),     # Layer green
    "globe_blue": (0x29, 0x80, 0xB9),      # Globe blue
    "globe_light": (0x85, 0xC1, 0xE9),     # Light globe blue
}


def create_icon_base(size: int) -> Image.Image:
    """Create base icon with rounded background."""
    img = Image.new("RGBA", (size, size), COLORS["white_transparent"])
    draw = ImageDraw.Draw(img)
    
    # Rounded square background
    radius = max(2, size // 8)
    margin = max(1, size // 32)
    
    # Draw gradient-like background using layered rounded rectangles
    for i in range(3):
        alpha = 255 - i * 30
        color = (*COLORS["bg_primary"][:3], alpha) if i == 0 else (*COLORS["bg_secondary"][:3], alpha)
        offset = i * (size // 20)
        draw.rounded_rectangle(
            [margin + offset, margin + offset, size - margin - offset, size - margin - offset],
            radius=radius - i,
            fill=color
        )
    
    return img


def draw_map_pin(draw: ImageDraw.Draw, size: int, cx: float, cy: float, scale: float = 1.0):
    """Draw a map pin marker."""
    pin_size = size * 0.35 * scale
    pin_width = pin_size * 0.6
    pin_height = pin_size * 1.2
    
    # Pin stem (circle at bottom)
    stem_radius = pin_width * 0.45
    stem_cx = cx
    stem_cy = cy + pin_height * 0.35
    
    # Pin head (teardrop shape)
    head_points = [
        (cx, cy - pin_height * 0.5),  # Top point
        (cx + pin_width * 0.5, cy),   # Right
        (cx, cy + pin_height * 0.2),  # Bottom center
        (cx - pin_width * 0.5, cy),   # Left
    ]
    
    # Draw pin head
    draw.polygon(head_points, fill=COLORS["pin_red"])
    # Draw pin head border
    draw.polygon(head_points, outline=COLORS["pin_dark"], width=max(1, int(size * 0.015)))
    
    # Draw stem circle
    draw.ellipse(
        [
            stem_cx - stem_radius, stem_cy - stem_radius,
            stem_cx + stem_radius, stem_cy + stem_radius
        ],
        fill=COLORS["pin_red"],
        outline=COLORS["pin_dark"],
        width=max(1, int(size * 0.015))
    )
    
    # Inner white dot on pin head
    inner_radius = stem_radius * 0.4
    draw.ellipse(
        [
            cx - inner_radius, cy - pin_height * 0.3 - inner_radius,
            cx + inner_radius, cy - pin_height * 0.3 + inner_radius
        ],
        fill=COLORS["white"]
    )


def draw_layers(draw: ImageDraw.Draw, size: int, cx: float, cy: float, scale: float = 1.0):
    """Draw stacked map layers."""
    layer_count = 3
    layer_height = size * 0.12 * scale
    layer_width = size * 0.55 * scale
    spacing = size * 0.04 * scale
    
    colors = [COLORS["layer_blue"], COLORS["accent_teal"], COLORS["layer_green"]]
    
    for i in range(layer_count):
        y = cy - (layer_count - 1) * (layer_height + spacing) / 2 + i * (layer_height + spacing)
        x = cx - layer_width / 2
        
        # Layer rectangle with rounded corners
        radius = max(1, int(size * 0.02))
        draw.rounded_rectangle(
            [x, y, x + layer_width, y + layer_height],
            radius=radius,
            fill=(*colors[i][:3], 200),
            outline=colors[i],
            width=max(1, int(size * 0.015))
        )
        
        # Layer detail lines
        if size >= 48:
            line_count = 3
            for j in range(line_count):
                lx = x + layer_width * 0.15 + j * layer_width * 0.3
                draw.line(
                    [(lx, y + layer_height * 0.2), (lx, y + layer_height * 0.8)],
                    fill=(*colors[i][:3], 150),
                    width=max(1, int(size * 0.01))
                )


def draw_globe(draw: ImageDraw.Draw, size: int, cx: float, cy: float, scale: float = 1.0):
    """Draw a globe with meridians and parallels."""
    radius = size * 0.28 * scale
    
    # Globe circle
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=(*COLORS["globe_blue"][:3], 180),
        outline=COLORS["globe_blue"],
        width=max(2, int(size * 0.02))
    )
    
    # Meridians (vertical curves)
    for angle in [-60, -30, 0, 30, 60]:
        # Simulate curve with ellipse arc
        draw.arc(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            start=angle - 90, end=angle + 90,
            fill=(*COLORS["globe_light"][:3], 200),
            width=max(1, int(size * 0.015))
        )
    
    # Equator (horizontal line)
    draw.line(
        [(cx - radius, cy), (cx + radius, cy)],
        fill=(*COLORS["globe_light"][:3], 200),
        width=max(1, int(size * 0.015))
    )
    
    # Latitude lines
    for lat_offset in [-radius * 0.5, radius * 0.5]:
        y = cy + lat_offset
        # Draw as ellipse arc (flattened)
        draw.arc(
            [cx - radius, y - radius * 0.3, cx + radius, y + radius * 0.3],
            start=0, end=180,
            fill=(*COLORS["globe_light"][:3], 150),
            width=max(1, int(size * 0.01))
        )


def draw_ai_spark(draw: ImageDraw.Draw, size: int, cx: float, cy: float, scale: float = 1.0):
    """Draw AI spark/star accent in corner."""
    spark_size = size * 0.08 * scale
    # 4-pointed star
    points = [
        (cx, cy - spark_size),      # Top
        (cx + spark_size * 0.3, cy - spark_size * 0.3),  # Top-right inner
        (cx + spark_size, cy),      # Right
        (cx + spark_size * 0.3, cy + spark_size * 0.3),  # Bottom-right inner
        (cx, cy + spark_size),      # Bottom
        (cx - spark_size * 0.3, cy + spark_size * 0.3),  # Bottom-left inner
        (cx - spark_size, cy),      # Left
        (cx - spark_size * 0.3, cy - spark_size * 0.3),  # Top-left inner
    ]
    draw.polygon(points, fill=COLORS["accent_green"], outline=COLORS["white"], width=max(1, int(size * 0.01)))


def generate_icon(size: int) -> Image.Image:
    """Generate a complete GIS-themed icon at the given size."""
    img = create_icon_base(size)
    draw = ImageDraw.Draw(img)
    
    cx = size / 2
    cy = size / 2
    
    if size >= 128:
        # Large icon: Globe with layers and pin
        draw_globe(draw, size, cx, cy - size * 0.05, scale=1.0)
        draw_layers(draw, size, cx, cy + size * 0.22, scale=0.7)
        draw_map_pin(draw, size, cx + size * 0.25, cy - size * 0.2, scale=0.6)
        draw_ai_spark(draw, size, cx + size * 0.38, cy - size * 0.38, scale=1.0)
    elif size >= 48:
        # Medium icon: Globe with pin
        draw_globe(draw, size, cx, cy, scale=0.9)
        draw_map_pin(draw, size, cx + size * 0.22, cy - size * 0.18, scale=0.7)
        draw_ai_spark(draw, size, cx + size * 0.35, cy - size * 0.35, scale=1.0)
    else:
        # Small icon (24x24): Simple pin with globe hint
        draw_map_pin(draw, size, cx, cy, scale=1.1)
        # Tiny globe hint at pin base
        draw_ai_spark(draw, size, cx + size * 0.3, cy + size * 0.25, scale=1.0)
    
    return img


def save_icons(output_dir: str, prefix: str = ""):
    """Generate and save icons at all required sizes."""
    os.makedirs(output_dir, exist_ok=True)
    
    sizes = [24, 48, 128]
    
    for size in sizes:
        icon = generate_icon(size)
        filename = f"{prefix}icon_{size}x{size}.png" if prefix else f"icon_{size}x{size}.png"
        filepath = os.path.join(output_dir, filename)
        icon.save(filepath, "PNG", optimize=True)
        print(f"Created: {filepath} ({size}x{size})")
    
    # Also create a default icon.png (using 128x128 as default)
    default_icon = generate_icon(128)
    default_path = os.path.join(output_dir, f"{prefix}icon.png" if prefix else "icon.png")
    default_icon.save(default_path, "PNG", optimize=True)
    print(f"Created default: {default_path}")


def create_ico_file(output_dir: str, prefix: str = ""):
    """Create a multi-resolution .ico file for Windows."""
    try:
        icons = [generate_icon(size) for size in [16, 24, 32, 48, 64, 128, 256]]
        ico_path = os.path.join(output_dir, f"{prefix}icon.ico" if prefix else "icon.ico")
        icons[0].save(ico_path, format="ICO", sizes=[(i.width, i.height) for i in icons])
        print(f"Created ICO: {ico_path}")
    except Exception as e:
        print(f"ICO creation failed (non-critical): {e}")


if __name__ == "__main__":
    # Generate for plugin resources
    plugin_resources = "Universal-AI-GIS-Studio/plugin/universal_ai_gis/resources"
    print(f"Generating icons for plugin: {plugin_resources}")
    save_icons(plugin_resources)
    create_ico_file(plugin_resources)
    
    # Generate for root resources
    root_resources = "Universal-AI-GIS-Studio/resources"
    print(f"\nGenerating icons for root: {root_resources}")
    save_icons(root_resources)
    create_ico_file(root_resources)
    
    print("\n✅ All icons generated successfully!")