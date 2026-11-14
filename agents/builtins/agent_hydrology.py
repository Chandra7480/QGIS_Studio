"""Hydrology Agent — Flow, watershed, stream extraction."""

from agents.base_agent import SpecializedAgent


class HydrologyAgent(SpecializedAgent):
    """Agent for hydrological analysis: flow, watershed, stream network, drainage."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_hydrology",
            name="Hydrology Agent",
            description="Flow, watershed, stream extraction.",
            instructions=(
                "You perform hydrological analysis: flow direction/accumulation, "
                "stream network extraction, watershed delineation, pour point analysis, "
                "and drainage basin characterization. Use SAGA, GRASS, and native algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="hydrology",
            tool_namespace="qgis.algorithms",
        )
        
        self.hydro_algorithms = {
            "fill_sinks": "native:fillsinks",
            "fill_sinks_wang_liu": "saga:fillsinkswangliu",
            "flow_direction": "saga:flowdirection",
            "flow_accumulation": "saga:flowaccumulation",
            "stream_network": "saga:channelnetwork",
            "stream_order": "saga:streamorder",
            "watershed_basins": "saga:upslopearea",
            "watershed_pour_points": "grass7:r.watershed",
            "drainage_basins": "native:catchmentarea",
            "flow_length": "native:flowlength",
            "topographic_wetness": "saga:topographicwetnessindex",
            "stream_power": "saga:streampowerindex",
            "sediment_transport": "saga:sedimenttransportindex",
            "ls_factor": "saga:lsfactor",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "analyze")
        params = task.get("params", {})

        self.add_to_history("user", f"Hydrology: {action}", {"action": action})

        if action == "analyze":
            result = await self._analyze(params)
        elif action == "full_workflow":
            result = await self._full_workflow(params)
        elif action == "fill_sinks":
            result = await self._fill_sinks(params)
        elif action == "flow_direction":
            result = await self._flow_direction(params)
        elif action == "stream_network":
            result = await self._stream_network(params)
        elif action == "watershed":
            result = await self._watershed(params)
        elif action == "pour_points":
            result = await self._pour_points(params)
        elif action == "wetness_index":
            result = await self._wetness_index(params)
        elif action == "list_operations":
            result = {"operations": list(self.hydro_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _analyze(self, params: dict) -> dict:
        """General hydrology router."""
        operation = params.get("operation")
        if operation in self.hydro_algorithms:
            return await self._run_algorithm(self.hydro_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.hydro_algorithms.keys())}

    async def _full_workflow(self, params: dict) -> dict:
        """Complete hydrology workflow: fill -> flow dir -> flow acc -> streams -> watersheds."""
        dem = params.get("dem")
        threshold = params.get("threshold", 1000)  # Stream initiation threshold
        pour_points = params.get("pour_points")  # Optional
        
        if not dem:
            return {"error": "Missing required parameter: dem"}
        
        # Step 1: Fill sinks
        filled = await self._run_algorithm("native:fillsinks", {"INPUT": dem, **params})
        if filled.get("status") != "ok":
            return {"error": "Fill sinks failed", "step": "fill_sinks", "details": filled}
        filled_dem = filled.get("result", {}).get("OUTPUT", dem)
        
        # Step 2: Flow direction
        flow_dir = await self._run_algorithm("saga:flowdirection", {"DEM": filled_dem, **params})
        if flow_dir.get("status") != "ok":
            return {"error": "Flow direction failed", "step": "flow_direction", "details": flow_dir}
        flow_dir_result = flow_dir.get("result", {}).get("DIRECTION", filled_dem)
        
        # Step 3: Flow accumulation
        flow_acc = await self._run_algorithm("saga:flowaccumulation", {"DEM": filled_dem, **params})
        if flow_acc.get("status") != "ok":
            return {"error": "Flow accumulation failed", "step": "flow_accumulation", "details": flow_acc}
        flow_acc_result = flow_acc.get("result", {}).get("FLOW", filled_dem)
        
        # Step 4: Stream network
        streams = await self._run_algorithm("saga:channelnetwork", {
            "DEM": filled_dem, 
            "INIT_GRID": flow_acc_result,
            "THRESHOLD": threshold,
            **params
        })
        stream_result = streams.get("result", {}).get("CHANNELS")
        
        # Step 5: Watersheds (if pour points provided)
        watersheds = None
        if pour_points:
            watersheds = await self._run_algorithm("saga:upslopearea", {
                "DEM": filled_dem,
                "POUR_POINTS": pour_points,
                **params
            })
        
        return {
            "filled_dem": filled,
            "flow_direction": flow_dir,
            "flow_accumulation": flow_acc,
            "streams": streams,
            "watersheds": watersheds,
            "workflow_complete": True,
        }

    async def _fill_sinks(self, params: dict) -> dict:
        """Fill sinks in DEM."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        return await self._run_algorithm("native:fillsinks", {"INPUT": dem, **params})

    async def _flow_direction(self, params: dict) -> dict:
        """Calculate flow direction."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        return await self._run_algorithm("saga:flowdirection", {"DEM": dem, **params})

    async def _stream_network(self, params: dict) -> dict:
        """Extract stream network."""
        dem = params.get("dem")
        flow_acc = params.get("flow_accumulation") or dem
        threshold = params.get("threshold", 1000)
        if not dem:
            return {"error": "Missing required parameter: dem"}
        return await self._run_algorithm("saga:channelnetwork", {
            "DEM": dem, "INIT_GRID": flow_acc, "THRESHOLD": threshold, **params
        })

    async def _watershed(self, params: dict) -> dict:
        """Delineate watershed basins."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        return await self._run_algorithm("saga:upslopearea", {"DEM": dem, **params})

    async def _pour_points(self, params: dict) -> dict:
        """Delineate watersheds from pour points."""
        dem = params.get("dem")
        points = params.get("pour_points")
        if not dem or not points:
            return {"error": "Missing required parameters: dem and pour_points"}
        return await self._run_algorithm("saga:upslopearea", {
            "DEM": dem, "POUR_POINTS": points, **params
        })

    async def _wetness_index(self, params: dict) -> dict:
        """Calculate Topographic Wetness Index (TWI)."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        return await self._run_algorithm("saga:topographicwetnessindex", {"DEM": dem, **params})

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        """Execute a processing algorithm."""
        alg_params = {k: v for k, v in params.items() 
                      if k not in ["operation", "threshold"]}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )