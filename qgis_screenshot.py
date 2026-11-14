"""QGIS Screenshot Script - Run this in QGIS Python Console"""

from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice
import base64
import os

canvas = iface.mapCanvas()
img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
painter = QPainter(img)
canvas.render(painter)
painter.end()

# Save to file
output_path = r"D:/1 2 3 QGIS/screenshot.png"
img.save(output_path, "PNG")
print(f"Screenshot saved to: {output_path}")
print(f"Canvas size: {img.size().width()} x {img.size().height()}")

# Convert to base64
ba = QByteArray()
buf = QBuffer(ba)
buf.open(QIODevice.OpenModeFlag.WriteOnly)
img.save(buf, "PNG")
b64 = base64.b64encode(bytes(ba.data())).decode("ascii")
print(f"Base64 length: {len(b64)}")
print("BASE64_START")
print(b64)
print("BASE64_END")