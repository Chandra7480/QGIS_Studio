"""Universal AI GIS Studio — Cartography & Layout Prompts.

Prompt templates for map composition and cartographic output.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_cartography_prompts(registry) -> None:
    """Register all cartography prompts."""

    # 1. Create Print Layout
    registry.register(PromptSpec(
        name="create_layout",
        description="Create a new print layout with map, legend, scalebar, and title.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Name for the new layout", required=True),
            PromptArgument("page_size", "Page size", default="A4", required=False, enum=["A4", "A3", "Letter", "Legal", "Custom"]),
            PromptArgument("orientation", "Page orientation", default="Landscape", required=False, enum=["Portrait", "Landscape"]),
            PromptArgument("map_layers", "Comma-separated layers to include in map", default="", required=False),
            PromptArgument("title", "Map title text", default="", required=False),
        ],
        template="""Create a print layout in QGIS:

**Layout Name:** {layout_name}
**Page Size:** {page_size}
**Orientation:** {orientation}
**Map Layers:** {map_layers}
**Title:** {title}

**Steps:**
1. Project → New Print Layout → Name: {layout_name}
2. Layout → Page Setup → Size: {page_size}, Orientation: {orientation}
3. Add Map: Drag rectangle on page → Item Properties → Set layers: {map_layers}
4. Add Title: Add Label → Text: {title} → Font: Bold, 18pt
5. Add Legend: Add Legend → Link to map → Customize items
6. Add Scalebar: Add Scalebar → Link to map → Units: Map Units
7. Add North Arrow: Add Image → Search "north arrow" → Link to map
8. Export: Layout → Export as PDF/Image

**Manual Process** (no single algorithm - uses Layout Designer)
**Use Case:** Report maps, publication figures, atlas pages""",
        tags=["layout", "print layout", "map composition", "cartography"],
    ))

    # 2. Add Legend
    registry.register(PromptSpec(
        name="add_legend",
        description="Add and configure a legend in a print layout.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Target layout name"),
            PromptArgument("map_item_id", "Map item ID in layout (default: auto-detect)", default="", required=False),
            PromptArgument("title", "Legend title", default="Legend", required=False),
            PromptArgument("columns", "Number of columns", default=1, required=False),
            PromptArgument("symbol_size", "Symbol size (mm)", default=5, required=False),
        ],
        template="""Add legend to print layout in QGIS:

**Layout:** {layout_name}
**Map Item:** {map_item_id} (auto-detect if empty)
**Legend Title:** {title}
**Columns:** {columns}
**Symbol Size:** {symbol_size} mm

**Steps:**
1. Open layout: {layout_name}
2. Add Item → Add Legend → Click on page
3. Item Properties → Main Properties → Linked Map: {map_item_id}
4. Legend Items → Uncheck "Auto update" → Customize layer order/names
5. Fonts → Title: Bold 12pt, Items: 10pt
6. Symbol → Symbol width: {symbol_size} mm, Symbol height: {symbol_size} mm
7. Columns → Count: {columns}
8. Position/size as needed

**Use Case:** Every thematic map needs a legend""",
        tags=["legend", "layout", "cartography", "symbology"],
    ))

    # 3. Add Scalebar
    registry.register(PromptSpec(
        name="add_scalebar",
        description="Add a scale bar to a print layout.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Target layout name"),
            PromptArgument("map_item_id", "Map item ID in layout", default="", required=False),
            PromptArgument("style", "Scalebar style", default="Single Box", required=False, enum=["Single Box", "Double Box", "Line Ticks Up", "Line Ticks Down", "Line Ticks Middle", "Numeric"]),
            PromptArgument("units", "Display units", default="Map Units", required=False, enum=["Map Units", "Meters", "Kilometers", "Feet", "Miles", "Nautical Miles"]),
            PromptArgument("segments", "Number of segments", default=4, required=False),
            PromptArgument("segment_size", "Segment size (in display units)", default=1000, required=False),
        ],
        template="""Add scalebar to print layout in QGIS:

**Layout:** {layout_name}
**Map Item:** {map_item_id}
**Style:** {style}
**Units:** {units}
**Segments:** {segments}
**Segment Size:** {segment_size}

**Steps:**
1. Open layout: {layout_name}
2. Add Item → Add Scalebar → Click on page (typically bottom)
3. Item Properties → Main Properties → Linked Map: {map_item_id}
4. Style → {style}
5. Units → {units}
6. Segments → Left: 0, Right: {segments}, Segment size: {segment_size}
7. Font → 9pt, Color: Dark gray
8. Position bottom-left or bottom-right

**Use Case:** All reference maps need scale indication""",
        tags=["scalebar", "scale", "layout", "cartography"],
    ))

    # 4. Add North Arrow
    registry.register(PromptSpec(
        name="add_north_arrow",
        description="Add a north arrow to a print layout.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Target layout name"),
            PromptArgument("map_item_id", "Map item ID in layout", default="", required=False),
            PromptArgument("style", "North arrow style", default="ESRI", required=False, enum=["ESRI", "Simple", "Fancy", "Custom SVG"]),
            PromptArgument("size", "Size (mm)", default=20, required=False),
        ],
        template="""Add north arrow to print layout in QGIS:

**Layout:** {layout_name}
**Map Item:** {map_item_id}
**Style:** {style}
**Size:** {size} mm

**Steps:**
1. Open layout: {layout_name}
2. Add Item → Add Image → Click on page (typically top-right)
3. Item Properties → Search directories → Type "north" → Select {style} arrow
4. Main Properties → Linked Map: {map_item_id} (auto-rotates with map)
5. Image Size → Width: {size} mm, Height: {size} mm
6. Position top-right corner with margin

**Use Case:** Orient map readers, required for non-north-up projections""",
        tags=["north arrow", "orientation", "layout", "cartography"],
    ))

    # 5. Export Layout
    registry.register(PromptSpec(
        name="export_layout",
        description="Export a print layout to PDF, image, or SVG.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Layout to export"),
            PromptArgument("output_path", "Full output file path"),
            PromptArgument("format", "Export format", default="PDF", required=False, enum=["PDF", "PNG", "JPG", "SVG", "TIFF"]),
            PromptArgument("dpi", "Resolution (DPI)", default=300, required=False),
            PromptArgument("georef", "Include georeference (PDF/TIFF only)", default=False, required=False),
        ],
        template="""Export print layout in QGIS:

**Layout:** {layout_name}
**Output Path:** {output_path}
**Format:** {format}
**DPI:** {dpi}
**Georeference:** {georef}

**Steps:**
1. Open layout: {layout_name}
2. Layout → Export as {format} → {output_path}
3. Export Settings:
   - Resolution: {dpi} DPI
   - Georeference: {georef} (PDF: GeoPDF, TIFF: GeoTIFF)
   - Simplify geometries: Checked (for PDF/SVG)
   - Text as outlines: Unchecked (keeps text selectable in PDF)
4. Click Save

**Use Case:** Final map delivery, printing, web publishing, archival""",
        tags=["export", "pdf", "image", "svg", "layout", "cartography"],
    ))

    # 6. Atlas Generation
    registry.register(PromptSpec(
        name="generate_atlas",
        description="Generate an atlas (map series) from a layout and coverage layer.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Layout with atlas configured"),
            PromptArgument("coverage_layer", "Vector layer defining atlas pages"),
            PromptArgument("page_name_field", "Field for page names/filenames"),
            PromptArgument("output_dir", "Output directory for atlas pages"),
            PromptArgument("format", "Output format", default="PDF", required=False, enum=["PDF", "PNG", "JPG", "SVG"]),
            PromptArgument("dpi", "Resolution (DPI)", default=300, required=False),
            PromptArgument("single_file", "Export as single multi-page file", default=True, required=False),
        ],
        template="""Generate Atlas (Map Series) in QGIS:

**Layout:** {layout_name}
**Coverage Layer:** {coverage_layer}
**Page Name Field:** {page_name_field}
**Output Directory:** {output_dir}
**Format:** {format}
**DPI:** {dpi}
**Single File:** {single_file}

**Steps:**
1. Open layout: {layout_name}
2. Atlas Settings → Generate atlas → Checked
3. Coverage Layer: {coverage_layer}
4. Page Name: {page_name_field}
5. Filter/Optional: Sort by {page_name_field}
6. Layout → Atlas Preview → Verify pages
7. Atlas → Export Atlas as {format}:
   - Directory: {output_dir}
   - Single file: {single_file}
   - Resolution: {dpi} DPI
   - Filename expression: {page_name_field}

**Use Case:** Map books, parcel maps, utility atlases, taxonomic series""",
        tags=["atlas", "map series", "batch export", "layout", "cartography"],
    ))

    # 7. Add Grid/Graticule
    registry.register(PromptSpec(
        name="add_grid",
        description="Add coordinate grid or graticule to map in layout.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Target layout name"),
            PromptArgument("map_item_id", "Map item ID in layout", default="", required=False),
            PromptArgument("grid_type", "Grid type", default="Cross", required=False, enum=["Cross", "Frame", "Full", "Frame Annotations", "Cross Annotations"]),
            PromptArgument("crs", "Grid CRS (empty = map CRS)", default="", required=False),
            PromptArgument("interval_x", "X interval (grid units)", default=10000, required=False),
            PromptArgument("interval_y", "Y interval (grid units)", default=10000, required=False),
        ],
        template="""Add coordinate grid/graticule in QGIS:

**Layout:** {layout_name}
**Map Item:** {map_item_id}
**Grid Type:** {grid_type}
**Grid CRS:** {crs} (empty = map CRS)
**X Interval:** {interval_x}
**Y Interval:** {interval_y}

**Steps:**
1. Open layout: {layout_name}
2. Select Map Item → Item Properties → Grids → Add Grid
3. Grid Type: {grid_type}
4. CRS: {crs} (for lat/lon graticule use EPSG:4326)
5. Interval X: {interval_x}, Interval Y: {interval_y}
6. Frame Style → Choose style (Zebra, Interior Ticks, etc.)
7. Annotations → Draw coordinates: Checked
   - Format: Degrees/Decimal/DMS
   - Font: 8pt
   - Position: Outside frame

**Use Case:** Reference maps, navigation, coordinate lookup""",
        tags=["grid", "graticule", "coordinates", "layout", "cartography"],
    ))

    # 8. Create Overview Map (Inset)
    registry.register(PromptSpec(
        name="add_inset_map",
        description="Add an overview/inset map showing context.",
        category=PromptCategory.CARTOGRAPHY,
        arguments=[
            PromptArgument("layout_name", "Target layout name"),
            PromptArgument("main_map_id", "Main map item ID"),
            PromptArgument("inset_layers", "Layers for inset map (typically basemap)", default="", required=False),
            PromptArgument("position", "Inset position", default="Bottom Right", required=False, enum=["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Custom"]),
            PromptArgument("size_mm", "Inset size (width mm)", default=60, required=False),
        ],
        template="""Add inset/overview map in QGIS:

**Layout:** {layout_name}
**Main Map:** {main_map_id}
**Inset Layers:** {inset_layers}
**Position:** {position}
**Size:** {size_mm} mm

**Steps:**
1. Open layout: {layout_name}
2. Add Item → Add Map → Draw small rectangle at {position}
3. Item Properties → Main Properties:
   - Layers: {inset_layers} (typically: basemap, admin boundaries)
   - Lock layers: Checked
   - Lock styles: Checked
4. Overviews → Add Overview → Select {main_map_id}
   - Frame Style: Solid, Color: Red, Width: 0.5mm
   - Blend mode: Multiply
5. Resize inset to {size_mm} mm wide
6. Position with margin from edge

**Use Case:** Context locator, regional overview, multi-scale maps""",
        tags=["inset", "overview", "locator", "layout", "cartography"],
    ))