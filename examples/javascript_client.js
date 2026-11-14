/**
 * Universal AI GIS Studio — JavaScript/TypeScript MCP Client Examples
 * 
 * Requirements:
 *     npm install @modelcontextprotocol/sdk
 * 
 * Usage:
 *     node examples/javascript_client.js
 * 
 * For TypeScript: npx ts-node examples/javascript_client.ts
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { CallToolResultSchema, ListToolsResultSchema } from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "..");

// =============================================================================
// Example 1: Stdio Transport (for local MCP servers)
// =============================================================================

async function exampleStdioTransport() {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 1: Stdio Transport");
    console.log("=".repeat(60));
    
    // Launch MCP server as subprocess
    const serverProcess = spawn("python", [
        "-m", "mcp_server.main",
        "--transport", "stdio"
    ], {
        cwd: PROJECT_ROOT,
        env: {
            ...process.env,
            UAGIS_BRIDGE_URL: "http://127.0.0.1:8765",
            // UAGIS_BRIDGE_TOKEN: "your-token-if-configured",
        },
        stdio: ["pipe", "pipe", "inherit"] // stdin, stdout, stderr
    });
    
    // Create transport connected to server process
    const transport = new StdioClientTransport({
        stdin: serverProcess.stdin,
        stdout: serverProcess.stdout
    });
    
    const client = new Client(
        { name: "uagis-js-example", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        // Connect
        await client.connect(transport);
        console.log("✓ MCP session initialized");
        
        // List tools
        const toolsResult = await client.listTools();
        console.log(`✓ Discovered ${toolsResult.tools.length} tools`);
        
        // Show first 5 tools
        toolsResult.tools.slice(0, 5).forEach(tool => {
            console.log(`  - ${tool.name}: ${tool.description.substring(0, 60)}...`);
        });
        
        // Call qgis.system.inspect
        console.log("\n→ Calling qgis.system.inspect...");
        const result1 = await client.callTool({
            name: "qgis.system.inspect",
            arguments: {}
        });
        printResult(result1);
        
        // Call qgis.system.health
        console.log("\n→ Calling qgis.system.health...");
        const result2 = await client.callTool({
            name: "qgis.system.health",
            arguments: {}
        });
        printResult(result2);
        
    } finally {
        await client.close();
        serverProcess.kill();
    }
}

// =============================================================================
// Example 2: Streamable HTTP Transport (for web/remote clients)
// =============================================================================

async function exampleHttpTransport() {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 2: Streamable HTTP Transport");
    console.log("=".repeat(60));
    
    const transport = new StreamableHTTPClientTransport(
        new URL("http://127.0.0.1:8766/mcp")
    );
    
    const client = new Client(
        { name: "uagis-js-http-example", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        await client.connect(transport);
        console.log("✓ Connected via Streamable HTTP");
        
        // List tools
        const toolsResult = await client.listTools();
        console.log(`✓ Discovered ${toolsResult.tools.length} tools`);
        
        // Call qgis.system.inspect
        console.log("\n→ Calling qgis.system.inspect...");
        const result = await client.callTool({
            name: "qgis.system.inspect",
            arguments: {}
        });
        printResult(result);
        
    } finally {
        await client.close();
    }
}

// =============================================================================
// Example 3: Complete GIS Workflow
// =============================================================================

async function exampleGisWorkflow() {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 3: Complete GIS Workflow");
    console.log("=".repeat(60));
    
    const serverProcess = spawn("python", [
        "-m", "mcp_server.main", "--transport", "stdio"
    ], {
        cwd: PROJECT_ROOT,
        env: { ...process.env, UAGIS_BRIDGE_URL: "http://127.0.0.1:8765" },
        stdio: ["pipe", "pipe", "inherit"]
    });
    
    const transport = new StdioClientTransport({
        stdin: serverProcess.stdin,
        stdout: serverProcess.stdout
    });
    
    const client = new Client(
        { name: "uagis-workflow", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        await client.connect(transport);
        
        // Step 1: System inspection
        console.log("→ Step 1: System inspection");
        let result = await client.callTool({ name: "qgis.system.inspect", arguments: {} });
        printResult(result);
        
        // Step 2: Project inspection
        console.log("\n→ Step 2: Project inspection");
        result = await client.callTool({ name: "qgis.project.inspect", arguments: {} });
        printResult(result);
        
        // Step 3: Load layer (UPDATE PATH TO YOUR DATA)
        console.log("\n→ Step 3: Load layer");
        const layerPath = "D:/data/parcels.gpkg"; // CHANGE THIS
        
        // Check if file exists (Node.js fs)
        const fs = await import("fs");
        if (!fs.existsSync(layerPath)) {
            console.log(`  ⚠ File not found: ${layerPath}`);
            console.log("  Skipping layer load. Update path in example.");
        } else {
            result = await client.callTool({
                name: "qgis.layers.load",
                arguments: { path: layerPath, layer_name: "Parcels JS Example" }
            });
            printResult(result);
            
            // Extract layer ID
            let layerId = null;
            try {
                const content = result.content[0];
                if (content.type === "text") {
                    const data = JSON.parse(content.text);
                    layerId = data.result?.id;
                }
            } catch (e) {
                console.log("  Could not extract layer ID");
            }
            
            // Step 4: Buffer algorithm
            if (layerId) {
                console.log(`\n→ Step 4: Buffer layer ${layerId} by 100m`);
                result = await client.callTool({
                    name: "qgis.algorithms.execute",
                    arguments: {
                        algorithm: "native:buffer",
                        parameters: {
                            INPUT: layerId,
                            DISTANCE: 100,
                            SEGMENTS: 5,
                            END_CAP_STYLE: 0,
                            JOIN_STYLE: 0,
                            MITER_LIMIT: 2,
                            DISSOLVE: false,
                            OUTPUT: "memory:"
                        }
                    }
                });
                printResult(result);
            }
        }
        
        // Step 5: Discover algorithms
        console.log("\n→ Step 5: Discover algorithms");
        result = await client.callTool({ name: "qgis.algorithms.discover", arguments: {} });
        try {
            const content = result.content[0];
            if (content.type === "text") {
                const data = JSON.parse(content.text);
                const algos = data.result?.algorithms || [];
                console.log(`  Found ${algos.length} algorithms`);
                algos.slice(0, 5).forEach(algo => {
                    console.log(`  - ${algo.id}: ${algo.name}`);
                });
            }
        } catch (e) {
            printResult(result);
        }
        
    } finally {
        await client.close();
        serverProcess.kill();
    }
}

// =============================================================================
// Example 4: Error Handling & Verification States
// =============================================================================

async function exampleErrorHandling() {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 4: Error Handling & Verification States");
    console.log("=".repeat(60));
    
    const serverProcess = spawn("python", [
        "-m", "mcp_server.main", "--transport", "stdio"
    ], {
        cwd: PROJECT_ROOT,
        env: { ...process.env, UAGIS_BRIDGE_URL: "http://127.0.0.1:8765" },
        stdio: ["pipe", "pipe", "inherit"]
    });
    
    const transport = new StdioClientTransport({
        stdin: serverProcess.stdin,
        stdout: serverProcess.stdout
    });
    
    const client = new Client(
        { name: "uagis-error-handling", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        await client.connect(transport);
        
        // Test 1: Valid tool call
        console.log("→ Test 1: Valid tool call");
        let result = await client.callTool({ name: "qgis.system.inspect", arguments: {} });
        console.log(`  Verification: ${extractVerification(result)}`);
        
        // Test 2: Invalid tool name
        console.log("\n→ Test 2: Invalid tool name");
        try {
            result = await client.callTool({ name: "qgis.nonexistent.tool", arguments: {} });
            console.log(`  Verification: ${extractVerification(result)}`);
        } catch (e) {
            console.log(`  Exception (expected): ${e.message}`);
        }
        
        // Test 3: Invalid parameters
        console.log("\n→ Test 3: Invalid parameters (nonexistent file)");
        try {
            result = await client.callTool({
                name: "qgis.layers.load",
                arguments: { path: "/nonexistent/path.shp" }
            });
            console.log(`  Verification: ${extractVerification(result)}`);
        } catch (e) {
            console.log(`  Exception: ${e.message}`);
        }
        
    } finally {
        await client.close();
        serverProcess.kill();
    }
}

// =============================================================================
// Example 5: Direct Bridge HTTP Client (bypass MCP)
// =============================================================================

async function exampleDirectBridge() {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 5: Direct Bridge HTTP Client");
    console.log("=".repeat(60));
    
    const bridgeUrl = "http://127.0.0.1:8765";
    const authToken = process.env.UAGIS_BRIDGE_TOKEN;
    
    const headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    };
    if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
    }
    
    // Helper function
    async function dispatch(tool, params) {
        const requestId = `req_${crypto.randomUUID().slice(0, 12)}`;
        const payload = {
            request_id: requestId,
            tool,
            params,
            timeout_seconds: 30
        };
        
        const response = await fetch(`${bridgeUrl}/dispatch`, {
            method: "POST",
            headers,
            body: JSON.stringify(payload)
        });
        
        return response.json();
    }
    
    // Health check
    console.log("→ Health check");
    try {
        const health = await fetch(`${bridgeUrl}/health`, { headers });
        console.log(`  ${health.status}:`, await health.json());
    } catch (e) {
        console.log(`  Failed: ${e.message}`);
    }
    
    // Direct tool dispatch
    console.log("\n→ Direct dispatch: qgis.system.inspect");
    console.log(await dispatch("qgis.system.inspect", {}));
    
    // Load layer
    console.log("\n→ Direct dispatch: qgis.layers.load");
    console.log(await dispatch("qgis.layers.load", { path: "D:/data/parcels.gpkg" })); // CHANGE THIS
}

// =============================================================================
// Utility Functions
// =============================================================================

function extractVerification(result) {
    try {
        const content = result.content[0];
        if (content.type === "text") {
            const data = JSON.parse(content.text);
            return data.verification_state || "UNKNOWN";
        }
    } catch (e) {
        return "PARSE_ERROR";
    }
    return "NO_CONTENT";
}

function printResult(result) {
    try {
        const content = result.content[0];
        if (content.type === "text") {
            const data = JSON.parse(content.text);
            const status = data.status || "unknown";
            const verification = data.verification_state || "unknown";
            
            if (status === "ok") {
                console.log(`  ✓ Status: ${status} | Verification: ${verification}`);
                const resultData = data.result || {};
                Object.entries(resultData).slice(0, 5).forEach(([key, value]) => {
                    console.log(`    ${key}: ${value}`);
                });
            } else {
                const error = data.error || {};
                console.log(`  ✗ Status: ${status} | Verification: ${verification}`);
                console.log(`    Error: ${error.code}: ${error.message}`);
            }
        }
    } catch (e) {
        console.log(`  Parse error: ${e.message}`);
        console.log(`  Raw:`, result);
    }
}

// =============================================================================
// Main
// =============================================================================

async function main() {
    console.log("Universal AI GIS Studio — JavaScript/TypeScript Client Examples");
    console.log("=".repeat(60));
    console.log("Prerequisites:");
    console.log("  1. QGIS 4.2.3 running with Universal AI GIS Studio plugin enabled");
    console.log("  2. Bridge started (Plugins → Universal AI GIS Studio → Start Bridge)");
    console.log("  3. npm install @modelcontextprotocol/sdk");
    console.log("");
    
    // Run examples (comment/uncomment as needed)
    try {
        await exampleStdioTransport();
    } catch (e) {
        console.error("Stdio example failed:", e.message);
        console.log("  Make sure QGIS Bridge is running on port 8765");
    }
    
    // Uncomment for HTTP example (requires MCP server running on HTTP)
    // try {
    //     await exampleHttpTransport();
    // } catch (e) {
    //     console.error("HTTP example failed:", e.message);
    // }
    
    // Uncomment for workflow example (requires data file)
    // try {
    //     await exampleGisWorkflow();
    // } catch (e) {
    //     console.error("Workflow example failed:", e.message);
    // }
    
    try {
        await exampleErrorHandling();
    } catch (e) {
        console.error("Error handling example failed:", e.message);
    }
    
    // Uncomment for direct bridge example
    // try {
    //     await exampleDirectBridge();
    // } catch (e) {
    //     console.error("Direct bridge example failed:", e.message);
    // }
    
    console.log("\n" + "=".repeat(60));
    console.log("Examples complete!");
    console.log("=".repeat(60));
}

main().catch(console.error);