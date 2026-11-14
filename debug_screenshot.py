"""Debug script to test capture_canvas directly in QGIS Python Console"""

# Run this in QGIS Python Console (Plugins -> Python Console)
# Paste this entire script and press Enter

from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtCore import QBuffer, QByteArray
import base64

canvas = iface.mapCanvas()
print(f"Canvas: {canvas}")
print(f"Canvas size: {canvas.size()}")

img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
painter = QPainter(img)
canvas.render(painter)
painter.end()

ba = QByteArray()
buf = QBuffer(ba)
buf.open(QBuffer.OpenModeFlag.WriteOnly)
img.save(buf, "PNG")
b64 = base64.b64encode(bytes(ba.data())).decode("ascii")

print(f"Image base64 length: {len(b64)}")
print(f"Width: {img.width()}")
print(f"Height: {img.height()}")
print(f"Format: png")

# Save to file for verification
output_path = r"D:/1 2 3 QGIS/screenshot_direct.png"
img.save(output_path, "PNG")
print(f"Saved to: {output_path}")

# Return the dict that capture_canvas should return
result = {"image_base64": b64, "width": img.width(), "height": img.height(), "format": "png"}
print(f"Result keys: {list(result.keys())}")
print(f"image_base64 length: {len(result['image_base64'])}")