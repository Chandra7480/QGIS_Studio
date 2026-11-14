import json
import urllib.request

url = "http://127.0.0.1:8766/dispatch"

def test_tool(tool_name, params=None):
    payload = json.dumps({
        "request_id": f"test_{tool_name}",
        "tool": tool_name,
        "params": params or {},
        "timeout_seconds": 30
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            status = result.get("status", "unknown")
            verification = result.get("verification_state", "unknown")
            print(f"Tool: {tool_name}")
            print(f"  Status: {status}")
            print(f"  Verification: {verification}")
            if result.get("result"):
                print(f"  Result: {result['result']}")
            if result.get("error"):
                print(f"  Error: {result['error']}")
            print()
    except Exception as e:
        print(f"Tool: {tool_name} - Error: {e}")
        print()

print("Testing Universal AI GIS Studio MCP Bridge")
print("=" * 50)

test_tool("qgis.system.inspect")
test_tool("qgis.system.health")
test_tool("qgis.project.inspect")
test_tool("qgis.layers.inspect")

print("=" * 50)
print("Test complete!")