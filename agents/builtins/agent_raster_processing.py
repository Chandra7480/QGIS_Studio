"""Raster Processing Agent — Raster calculation, reclassify, mosaic."""

from agents.base_agent import SpecializedAgent


class RasterProcessingAgent(SpecializedAgent):
    """Agent for raster processing: calculator, reclassify, mosaic, resample, etc."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_raster_processing",
            name="Raster Processing Agent",
            description="Raster calculation, reclassify, mosaic.",
            instructions=(
                "You process raster data: raster calculator, reclassify, mosaic, clip, "
                "resample, slope/aspect, hillshade, and index calculations (NDVI, etc.). "
                "Use qgis.algorithms.execute with GDAL and native raster algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="raster_processing",
            tool_namespace="qgis.algorithms",
        )
        
        self.raster_algorithms = {
            "calculator": "qgis:rastercalculator",
            "reclassify": "native:reclassifybytable",
            "clip": "gdal:cliprasterbymasklayer",
            "clip_extent": "gdal:cliprasterbyextent",
            "merge": "gdal:merge",
            "resample": "gdal:warpreproject",
            "slope": "native:slope",
            "aspect": "native:aspect",
            "hillshade": "native:hillshade",
            "contour": "gdal:contour",
            "ndvi": "custom:ndvi",  # Calculated via raster calculator
            "indices": "custom:indices",  # Various spectral indices
            "translate": "gdal:translate",
            "warp": "gdal:warpreproject",
            "proximity": "gdal:proximity",
            "polygonize": "gdal:polygonize",
            "rasterize": "gdal:rasterize",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "process_raster")
        params = task.get("params", {})

        self.add_to_history("user", f"Raster Processing: {action}", {"action": action})

        if action == "process_raster":
            result = await self._process_raster(params)
        elif action == "calculator":
            result = await self._calculator(params)
        elif action == "reclassify":
            result = await self._reclassify(params)
        elif action == "mosaic":
            result = await self._mosaic(params)
        elif action == "clip":
            result = await self._clip_raster(params)
        elif action == "terrain":
            result = await self._terrain(params)
        elif action == "indices":
            result = await self._indices(params)
        elif action == "convert":
            result = await self._convert(params)
        elif action == "list_operations":
            result = {"operations": list(self.raster_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _process_raster(self, params: dict) -> dict:
        """General raster processing router."""
        operation = params.get("operation")
        if operation in self.raster_algorithms:
            return await self._run_algorithm(self.raster_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.raster_algorithms.keys())}

    async def _calculator(self, params: dict) -> dict:
        """Raster calculator."""
        required = ["expression", "layers"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("qgis:rastercalculator", params)

    async def _reclassify(self, params: dict) -> dict:
        """Reclassify raster values."""
        required = ["input", "table"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:reclassifybytable", params)

    async def _mosaic(self, params: dict) -> dict:
        """Merge multiple rasters."""
        if "inputs" not in params:
            return {"error": "Missing required parameter: inputs (list)"}
        return await self._run_algorithm("gdal:merge", params)

    async def _clip_raster(self, params: dict) -> dict:
        """Clip raster by mask or extent."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        mask = params.get("mask")
        extent = params.get("extent")
        algo = "gdal:cliprasterbymasklayer" if mask else "gdal:cliprasterbyextent"
        return await self._run_algorithm(algo, params)

    async def _terrain(self, params: dict) -> dict:
        """Terrain derivatives: slope, aspect, hillshade."""
        terrain_type = params.get("terrain_type", "slope")  # slope, aspect, hillshade
        algo_map = {
            "slope": "native:slope",
            "aspect": "native:aspect",
            "hillshade": "native:hillshade",
        }
        algo = algo_map.get(terrain_type, "native:slope")
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm(algo, params)

    async def _indices(self, params: dict) -> dict:
        """Calculate spectral indices (NDVI, EVI, etc.)."""
        index = params.get("index", "ndvi").lower()
        red = params.get("red_band")
        nir = params.get("nir_band")
        
        if not red or not nir:
            return {"error": "Missing red_band and/or nir_band parameters"}
        
        expressions = {
            "ndvi": f"({nir} - {red}) / ({nir} + {red})",
            "evi": f"2.5 * ({nir} - {red}) / ({nir} + 6 * {red} - 7.5 * {params.get('blue_band', '0')} + 1)",
            "savi": f"1.5 * ({nir} - {red}) / ({nir} + {red} + 0.5)",
            "msavi": f"(2 * {nir} + 1 - sqrt((2 * {nir} + 1)^2 - 8 * ({nir} - {red}))) / 2",
        }
        
        expr = expressions.get(index)
        if not expr:
            return {"error": f"Unknown index: {index}", "available": list(expressions.keys())}
        
        return await self._run_algorithm("qgis:rastercalculator", {
            "expression": expr,
            "layers": [red, nir] + ([params.get("blue_band")] if params.get("blue_band") else []),
            "output": params.get("output", "memory:")
        })

    async def _convert(self, params: dict) -> dict:
        """Convert raster format/project."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("gdal:translate", params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        """Execute a processing algorithm."""
        alg_params = {k: v for k, v in params.items() 
                      if k not in ["operation", "terrain_type", "index"]}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )