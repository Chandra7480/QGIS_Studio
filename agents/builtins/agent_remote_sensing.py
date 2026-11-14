"""Remote Sensing Agent — Satellite imagery, band combinations, indices."""

from agents.base_agent import SpecializedAgent


class RemoteSensingAgent(SpecializedAgent):
    """Agent for remote sensing: satellite imagery, band math, indices, atmospheric correction."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_remote_sensing",
            name="Remote Sensing Agent",
            description="Satellite imagery, band combinations, indices.",
            instructions=(
                "You process remote sensing data: satellite image download, band combinations, "
                "spectral indices (NDVI, EVI, SAVI, NDBI, etc.), atmospheric correction, "
                "pan-sharpening, and time series analysis. Use qgis.algorithms.execute and web GIS tools."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="remote_sensing",
            tool_namespace="qgis.algorithms",
        )
        
        self.rs_algorithms = {
            "band_combination": "qgis:rastercalculator",
            "ndvi": "custom:ndvi",
            "evi": "custom:evi",
            "savi": "custom:savi",
            "msavi": "custom:msavi",
            "ndbi": "custom:ndbi",
            "ndwi": "custom:ndwi",
            "mndwi": "custom:mndwi",
            "nbr": "custom:nbr",
            "pan_sharpen": "gdal:pansharpen",
            "atmospheric_correction": "custom:atmospheric_correction",
            "cloud_mask": "custom:cloud_mask",
            "mosaic": "gdal:merge",
            "clip": "gdal:cliprasterbymasklayer",
            "resample": "gdal:warpreproject",
            "reproject": "gdal:warpreproject",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "process")
        params = task.get("params", {})

        self.add_to_history("user", f"Remote Sensing: {action}", {"action": action})

        if action == "process":
            result = await self._process(params)
        elif action == "indices":
            result = await self._indices(params)
        elif action == "band_math":
            result = await self._band_math(params)
        elif action == "pan_sharpen":
            result = await self._pan_sharpen(params)
        elif action == "cloud_mask":
            result = await self._cloud_mask(params)
        elif action == "download":
            result = await self._download(params)
        elif action == "time_series":
            result = await self._time_series(params)
        elif action == "list_operations":
            result = {"operations": list(self.rs_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _process(self, params: dict) -> dict:
        operation = params.get("operation")
        if operation in self.rs_algorithms:
            return await self._run_algorithm(self.rs_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.rs_algorithms.keys())}

    async def _indices(self, params: dict) -> dict:
        """Calculate spectral indices."""
        index = params.get("index", "ndvi").lower()
        bands = params.get("bands", {})
        
        expressions = {
            "ndvi": f"({bands.get('nir', 'B8')} - {bands.get('red', 'B4')}) / ({bands.get('nir', 'B8')} + {bands.get('red', 'B4')})",
            "evi": f"2.5 * ({bands.get('nir', 'B8')} - {bands.get('red', 'B4')}) / ({bands.get('nir', 'B8')} + 6 * {bands.get('red', 'B4')} - 7.5 * {bands.get('blue', 'B2')} + 1)",
            "savi": f"1.5 * ({bands.get('nir', 'B8')} - {bands.get('red', 'B4')}) / ({bands.get('nir', 'B8')} + {bands.get('red', 'B4')} + 0.5)",
            "msavi": f"(2 * {bands.get('nir', 'B8')} + 1 - sqrt((2 * {bands.get('nir', 'B8')} + 1)^2 - 8 * ({bands.get('nir', 'B8')} - {bands.get('red', 'B4')}))) / 2",
            "ndbi": f"({bands.get('swir', 'B11')} - {bands.get('nir', 'B8')}) / ({bands.get('swir', 'B11')} + {bands.get('nir', 'B8')})",
            "ndwi": f"({bands.get('green', 'B3')} - {bands.get('nir', 'B8')}) / ({bands.get('green', 'B3')} + {bands.get('nir', 'B8')})",
            "mndwi": f"({bands.get('green', 'B3')} - {bands.get('swir', 'B11')}) / ({bands.get('green', 'B3')} + {bands.get('swir', 'B11')})",
            "nbr": f"({bands.get('nir', 'B8')} - {bands.get('swir', 'B12')}) / ({bands.get('nir', 'B8')} + {bands.get('swir', 'B12')})",
        }
        
        expr = expressions.get(index)
        if not expr:
            return {"error": f"Unknown index: {index}", "available": list(expressions.keys())}
        
        return await self._run_algorithm("qgis:rastercalculator", {
            "expression": expr,
            "layers": list(bands.values()),
            "output": params.get("output", "memory:")
        })

    async def _band_math(self, params: dict) -> dict:
        """Custom band math expression."""
        expression = params.get("expression")
        layers = params.get("layers", [])
        if not expression or not layers:
            return {"error": "Missing expression or layers"}
        return await self._run_algorithm("qgis:rastercalculator", {
            "expression": expression,
            "layers": layers,
            "output": params.get("output", "memory:")
        })

    async def _pan_sharpen(self, params: dict) -> dict:
        """Pan-sharpen multispectral with panchromatic."""
        required = ["panchromatic", "multispectral"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("gdal:pansharpen", params)

    async def _cloud_mask(self, params: dict) -> dict:
        """Generate cloud mask (simplified - requires specific algorithm)."""
        return {"note": "Cloud masking requires Sentinel-2/Landsat specific algorithms. Use QGIS plugins or external tools."}

    async def _download(self, params: dict) -> dict:
        """Download satellite imagery (requires web GIS agent)."""
        return {"note": "Use agent_web_gis for downloading from WMS/WCS/STAC APIs"}

    async def _time_series(self, params: dict) -> dict:
        """Time series analysis."""
        return {"note": "Time series analysis requires multiple dates. Use agent_temporal_gis for temporal operations."}

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        alg_params = {k: v for k, v in params.items() if k not in ["operation", "index"]}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )