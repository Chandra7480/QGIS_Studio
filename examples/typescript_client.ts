/**
 * Universal AI GIS Studio — TypeScript MCP Client Examples
 * 
 * Requirements:
 *     npm install @modelcontextprotocol/sdk
 *     npm install -D typescript ts-node @types/node
 * 
 * Usage:
 *     npx ts-node examples/typescript_client.ts
 * 
 * Or compile first:
 *     npx tsc examples/typescript_client.ts --esModuleInterop --moduleResolution node --target ES2022 --module ESNext
 *     node examples/typescript_client.js
 */

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { CallToolResult, ListToolsResult } from "@modelcontextprotocol/sdk/types.js";
import { spawn, ChildProcess } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "..");

// =============================================================================
// Type Definitions
// =============================================================================

interface UAGISToolResult {
    request_id: string;
    tool: string;
    status: "ok" | "error";
    verification_state: "SUCCESS" | "PARTIAL_SUCCESS" | "FAILED" | "NEEDS_REVIEW" | "CANCELLED";
    result: Record<string, unknown>;
    error?: {
        code: string;
        message: string;
        context?: Record<string, unknown>;
    };
    job_id?: string;
    timestamp: string;
}

interface BridgeHealthResponse {
    status: string;
    qgis_connected?: boolean;
    project_open?: boolean;
    layer_count?: number;
    main_thread?: boolean;
    error?: string;
}

interface BridgeDispatchRequest {
    request_id: string;
    tool: string;
    params: Record<string, unknown>;
    timeout_seconds: number;
    require_approval?: boolean;
    metadata?: Record<string, unknown>;
}

interface BridgeDispatchResponse {
    request_id: string;
    status: "ok" | "error";
    result: Record<string, unknown>;
    error?: {
        code: string;
        message: string;
        context?: Record<string, unknown>;
    };
    verification_state: string;
    job_id?: string;
    timestamp: string;
}

// =============================================================================
// Example 1: Stdio Transport
// =============================================================================

async function exampleStdioTransport(): Promise<void> {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 1: Stdio Transport (TypeScript)");
    console.log("=".repeat(60));
    
    const serverProcess: ChildProcess = spawn("python", [
        "-m", "mcp_server.main",
        "--transport", "stdio"
    ], {
        cwd: PROJECT_ROOT,
        env: {
            ...process.env,
            UAGIS_BRIDGE_URL: "http://127.0.0.1:8765",
        },
        stdio: ["pipe", "pipe", "inherit"]
    });
    
    const transport = new StdioClientTransport({
        stdin: serverProcess.stdin,
        stdout: serverProcess.stdout
    });
    
    const client = new Client(
        { name: "uagis-ts-example", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        await client.connect(transport);
        console.log("✓ MCP session initialized");
        
        // List tools
        const toolsResult: ListToolsResult = await client.listTools();
        console.log(`✓ Discovered ${toolsResult.tools.length} tools`);
        
        toolsResult.tools.slice(0, 5).forEach(tool => {
            console.log(`  - ${tool.name}: ${tool.description.substring(0, 60)}...`);
        });
        
        // Call qgis.system.inspect
        console.log("\n→ Calling qgis.system.inspect...");
        const result1: CallToolResult = await client.callTool({
            name: "qgis.system.inspect",
            arguments: {}
        });
        printResult(result1);
        
        // Call qgis.system.health
        console.log("\n→ Calling qgis.system.health...");
        const result2: CallToolResult = await client.callTool({
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
// Example 2: Streamable HTTP Transport
// =============================================================================

async function exampleHttpTransport(): Promise<void> {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 2: Streamable HTTP Transport (TypeScript)");
    console.log("=".repeat(60));
    
    const transport = new StreamableHTTPClientTransport(
        new URL("http://127.0.0.1:8766/mcp")
    );
    
    const client = new Client(
        { name: "uagis-ts-http-example", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        await client.connect(transport);
        console.log("✓ Connected via Streamable HTTP");
        
        const toolsResult: ListToolsResult = await client.listTools();
        console.log(`✓ Discovered ${toolsResult.tools.length} tools`);
        
        console.log("\n→ Calling qgis.system.inspect...");
        const result: CallToolResult = await client.callTool({
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

async function exampleGisWorkflow(): Promise<void> {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 3: Complete GIS Workflow (TypeScript)");
    console.log("=".repeat(60));
    
    const serverProcess: ChildProcess = spawn("python", [
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
        { name: "uagis-ts-workflow", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        await client.connect(transport);
        
        // Step 1: System inspection
        console.log("→ Step 1: System inspection");
        let result: CallToolResult = await client.callTool({ 
            name: "qgis.system.inspect", 
            arguments: {} 
        });
        printResult(result);
        
        // Step 2: Project inspection
        console.log("\n→ Step 2: Project inspection");
        result = await client.callTool({ 
            name: "qgis.project.inspect", 
            arguments: {} 
        });
        printResult(result);
        
        // Step 3: Load layer (UPDATE PATH TO YOUR DATA)
        console.log("\n→ Step 3: Load layer");
        const layerPath = "D:/data/parcels.gpkg"; // CHANGE THIS
        
        const fs = await import("fs");
        if (!fs.existsSync(layerPath)) {
            console.log(`  ⚠ File not found: ${layerPath}`);
            console.log("  Skipping layer load. Update path in example.");
        } else {
            result = await client.callTool({
                name: "qgis.layers.load",
                arguments: { path: layerPath, layer_name: "Parcels TS Example" }
            });
            printResult(result);
            
            // Extract layer ID
            let layerId: string | null = null;
            try {
                const content = result.content[0];
                if (content.type === "text") {
                    const data: UAGISToolResult = JSON.parse(content.text);
                    layerId = data.result?.id as string ?? null;
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
        result = await client.callTool({ 
            name: "qgis.algorithms.discover", 
            arguments: {} 
        });
        try {
            const content = result.content[0];
            if (content.type === "text") {
                const data: UAGISToolResult = JSON.parse(content.text);
                const algos = data.result?.algorithms as Array<{id: string; name: string}> ?? [];
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

async function exampleErrorHandling(): Promise<void> {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 4: Error Handling & Verification States (TypeScript)");
    console.log("=".repeat(60));
    
    const serverProcess: ChildProcess = spawn("python", [
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
        { name: "uagis-ts-error-handling", version: "1.0.0" },
        { capabilities: {} }
    );
    
    try {
        await client.connect(transport);
        
        // Test 1: Valid tool call
        console.log("→ Test 1: Valid tool call");
        let result: CallToolResult = await client.callTool({ 
            name: "qgis.system.inspect", 
            arguments: {} 
        });
        console.log(`  Verification: ${extractVerification(result)}`);
        
        // Test 2: Invalid tool name
        console.log("\n→ Test 2: Invalid tool name");
        try {
            result = await client.callTool({ 
                name: "qgis.nonexistent.tool", 
                arguments: {} 
            });
            console.log(`  Verification: ${extractVerification(result)}`);
        } catch (e) {
            console.log(`  Exception (expected): ${(e as Error).message}`);
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
            console.log(`  Exception: ${(e as Error).message}`);
        }
        
    } finally {
        await client.close();
        serverProcess.kill();
    }
}

// =============================================================================
// Example 5: Direct Bridge HTTP Client (bypass MCP)
// =============================================================================

async function exampleDirectBridge(): Promise<void> {
    console.log("\n" + "=".repeat(60));
    console.log("EXAMPLE 5: Direct Bridge HTTP Client (TypeScript)");
    console.log("=".repeat(60));
    
    const bridgeUrl = "http://127.0.0.1:8765";
    const authToken = process.env.UAGIS_BRIDGE_TOKEN;
    
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    };
    if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
    }
    
    // Helper function
    async function dispatch(tool: string, params: Record<string, unknown>): Promise<BridgeDispatchResponse> {
        const requestId = `req_${crypto.randomUUID().slice(0, 12)}`;
        const payload: BridgeDispatchRequest = {
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
        
        return response.json() as Promise<BridgeDispatchResponse>;
    }
    
    // Health check
    console.log("→ Health check");
    try {
        const healthResponse = await fetch(`${bridgeUrl}/health`, { headers });
        const health: BridgeHealthResponse = await healthResponse.json();
        console.log(`  ${healthResponse.status}:`, health);
    } catch (e) {
        console.log(`  Failed: ${(e as Error).message}`);
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

function extractVerification(result: CallToolResult): string {
    try {
        const content = result.content[0];
        if (content.type === "text") {
            const data: UAGISToolResult = JSON.parse(content.text);
            return data.verification_state ?? "UNKNOWN";
        }
    } catch (e) {
        return "PARSE_ERROR";
    }
    return "NO_CONTENT";
}

function printResult(result: CallToolResult): void {
    try {
        const content = result.content[0];
        if (content.type === "text") {
            const data: UAGISToolResult = JSON.parse(content.text);
            const status = data.status ?? "unknown";
            const verification = data.verification_state ?? "unknown";
            
            if (status === "ok") {
                console.log(`  ✓ Status: ${status} | Verification: ${verification}`);
                const resultData = data.result ?? {};
                Object.entries(resultData).slice(0, 5).forEach(([key, value]) => {
                    console.log(`    ${key}: ${value}`);
                });
            } else {
                const error = data.error ?? {};
                console.log(`  ✗ Status: ${status} | Verification: ${verification}`);
                console.log(`    Error: ${error.code}: ${error.message}`);
            }
        }
    } catch (e) {
        console.log(`  Parse error: ${(e as Error).message}`);
        console.log(`  Raw:`, result);
    }
}

// =============================================================================
// Main
// =============================================================================

async function main(): Promise<void> {
    console.log("Universal AI GIS Studio — TypeScript Client Examples");
    console.log("=".repeat(60));
    console.log("Prerequisites:");
    console.log("  1. QGIS 4.2.3 running with Universal AI GIS Studio plugin enabled");
    console.log("  2. Bridge started (Plugins → Universal AI GIS Studio → Start Bridge)");
    console.log("  3. npm install @modelcontextprotocol/sdk");
    console.log("  4. npm install -D typescript ts-node @types/node");
    console.log("");
    
    // Run examples (comment/uncomment as needed)
    try {
        await exampleStdioTransport();
    } catch (e) {
        console.error("Stdio example failed:", (e as Error).message);
        console.log("  Make sure QGIS Bridge is running on port 8765");
    }
    
    // Uncomment for HTTP example (requires MCP server running on HTTP)
    // try {
    //     await exampleHttpTransport();
    // } catch (e) {
    //     console.error("HTTP example failed:", (e as Error).message);
    // }
    
    // Uncomment for workflow example (requires data file)
    // try {
    //     await exampleGisWorkflow();
    // } catch (e) {
    //     console.error("Workflow example failed:", (e as Error).message);
    // }
    
    try {
        await exampleErrorHandling();
    } catch (e) {
        console.error("Error handling example failed:", (e as Error).message);
    }
    
    // Uncomment for direct bridge example
    // try {
    //     await exampleDirectBridge();
    // } catch (e) {
    //     console.error("Direct bridge example failed:", (e as Error).message);
    // }
    
    console.log("\n" + "=".repeat(60));
    console.log("Examples complete!");
    console.log("=".repeat(60));
}

main().catch(console.error);