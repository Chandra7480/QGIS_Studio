import json

# Test with the actual content from the zip
import zipfile
zf = zipfile.ZipFile('dist/universal_ai_gis_studio-1.0.0.zip')
content = zf.read('universal_ai_gis_studio/version.json').decode('utf-8')
print("Raw content:")
print(repr(content))
print()
try:
    parsed = json.loads(content)
    print("Parsed successfully:", parsed)
except Exception as e:
    print(f"Error: {e}")