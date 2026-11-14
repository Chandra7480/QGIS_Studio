"""Universal AI GIS Studio — Automation Prompts.

Prompt templates for batch processing, models, and workflow automation.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_automation_prompts(registry) -> None:
    """Register all automation prompts."""

    # 1. Batch Process Algorithm
    registry.register(PromptSpec(
        name="batch_process",
        description="Run a processing algorithm on multiple input layers (batch processing).",
        category=PromptCategory.AUTOMATION,
        arguments=[
            PromptArgument("algorithm", "Algorithm ID (e.g., native:buffer, native:reprojectlayer)"),
            PromptArgument("input_layers", "Comma-separated input layer names/paths"),
            PromptArgument("parameters", "JSON string of fixed parameters for all runs"),
            PromptArgument("output_pattern", "Output naming pattern (use {INPUT} for input name)", default="{INPUT}_output", required=False),
            PromptArgument("output_folder", "Folder for outputs", required=True),
        ],
        template="""Batch Processing in QGIS:

**Algorithm:** {algorithm}
**Input Layers:** {input_layers}
**Fixed Parameters:** {parameters}
**Output Pattern:** {output_pattern}
**Output Folder:** {output_folder}

**Steps:**
1. Processing → Toolbox → Find {algorithm}
2. Right-click → "Execute as Batch Process"
3. Input Layer: Add rows for each layer in {input_layers}
4. Parameters: Fill {parameters} for each row (or use "Fill Down")
5. Output: Set pattern {output_pattern} in {output_folder}
6. Run → Check log for progress

**Automation via Python:**
```python
import processing
params = {parameters}
for layer in {input_layers}.split(','):
    params['INPUT'] = layer
    params['OUTPUT'] = f'{output_folder}/{output_pattern.format(INPUT=layer)}'
    processing.run({algorithm}, params)
```

**Use Case:** Reproject 50 layers, buffer 100 polygons, clip 20 rasters""",
        tags=["batch", "automation", "multiple", "processing", "model"],
    ))

    # 2. Create Processing Model (Graphical Modeler)
    registry.register(PromptSpec(
        name="create_model",
        description="Build a reusable Processing Model (Graphical Modeler) for complex workflows.",
        category=PromptCategory.AUTOMATION,
        arguments=[
            PromptArgument("model_name", "Name for the model"),
            PromptArgument("group", "Model group in toolbox", default="Custom Models", required=False),
            PromptArgument("inputs", "Model inputs: comma-separated 'name:type' (e.g., 'InputLayer:vector, BufferDist:number')"),
            PromptArgument("steps", "Model steps: semicolon-separated 'algorithm:param1=value,param2=@InputLayer'"),
            PromptArgument("outputs", "Model outputs: comma-separated 'name:algorithm_output'"),
        ],
        template="""Create Processing Model in QGIS Graphical Modeler:

**Model Name:** {model_name}
**Group:** {group}
**Inputs:** {inputs}
**Steps:** {steps}
**Outputs:** {outputs}

**Steps to Build:**
1. Processing → Graphical Modeler → New Model
2. Model Properties → Name: {model_name}, Group: {group}
3. **Inputs Panel:** Add each input from {inputs}
   - Types: vector, raster, number, string, extent, crs, field, enum, boolean, file, folder
4. **Model Canvas:** Drag algorithms from left panel
   - For each step in {steps}:
     - Search algorithm, drag to canvas
     - Set parameters: use @InputName for model inputs
     - Connect outputs to next algorithm inputs
5. **Outputs Panel:** Add each output from {outputs}
6. Save: {group}/{model_name}.model3

**Example Workflow:**
Inputs: "AOI:vector, BufferDist:number"
Steps: "native:buffer:INPUT=@AOI,DISTANCE=@BufferDist,OUTPUT=@Buffered; native:clip:INPUT=@RasterLayer,OVERLAY=@Buffered,OUTPUT=@Clipped"
Outputs: "Buffered:@Buffered, Clipped:@Clipped"

**Use Case:** Reusable workflows, team sharing, batch execution, documentation""",
        tags=["model", "graphical modeler", "workflow", "automation", "reusable"],
    ))

    # 3. Iterate Features (Run Algorithm per Feature)
    registry.register(PromptSpec(
        name="iterate_features",
        description="Run an algorithm once per feature in a layer (e.g., clip raster per polygon).",
        category=PromptCategory.AUTOMATION,
        arguments=[
            PromptArgument("algorithm", "Algorithm to run per feature (must support feature iteration)"),
            PromptArgument("feature_layer", "Layer with features to iterate over"),
            PromptArgument("algorithm_params", "Base parameters (use @FEATURE_ for feature-specific)"),
            PromptArgument("output_folder", "Output folder"),
            PromptArgument("output_pattern", "Output pattern with feature attributes", default="output_{ID}", required=False),
        ],
        template="""Iterate Features (Per-Feature Processing) in QGIS:

**Algorithm:** {algorithm}
**Feature Layer:** {feature_layer}
**Base Parameters:** {algorithm_params}
**Output Folder:** {output_folder}
**Output Pattern:** {output_pattern}

**Methods:**

**Method 1: Processing → Iterate Features (QGIS 3.22+)**
1. Right-click algorithm → "Iterate over Features"
2. Input Layer: {feature_layer}
3. Set parameters, use @attribute_name for feature fields
4. Output: {output_folder}/{output_pattern}

**Method 2: Python Script (Full Control)**
```python
layer = QgsProject.instance().mapLayersByName('{feature_layer}')[0]
for feat in layer.getFeatures():
    attrs = feat.attributes()
    fid = feat.id()
    params = {algorithm_params}
    # Substitute @FIELD_NAME with feat['FIELD_NAME']
    params['OUTPUT'] = f'{output_folder}/{output_pattern.format(**dict(zip(layer.fields().names(), attrs)))}'
    processing.run('{algorithm}', params)
```

**Method 3: Model with "Iterate Features" Algorithm**
1. Graphical Modeler → Add "native:iteratefeatures" algorithm
2. Connect to target algorithm
3. Outputs collected automatically

**Compatible Algorithms:** native:clip, native:extractbyextent, gdal:cliprasterbymasklayer, native:zonalstatisticsfb
**Use Case:** Clip raster per polygon, stats per zone, export per feature""",
        tags=["iterate", "per feature", "loop", "automation", "batch"],
    ))

    # 4. Create Atlas from Template
    registry.register(PromptSpec(
        name="batch_export_atlas",
        description="Automated atlas generation from layout template.",
        category=PromptCategory.AUTOMATION,
        arguments=[
            PromptArgument("layout_name", "Layout with atlas configured"),
            PromptArgument("coverage_layer", "Coverage layer for atlas pages"),
            PromptArgument("output_folder", "Output directory"),
            PromptArgument("format", "Output format", default="PDF", required=False, enum=["PDF", "PNG", "JPG", "SVG"]),
            PromptArgument("dpi", "Resolution", default=300, required=False),
            PromptArgument("filename_field", "Field for output filenames", required=True),
        ],
        template="""Batch Atlas Export in QGIS:

**Layout:** {layout_name}
**Coverage Layer:** {coverage_layer}
**Output Folder:** {output_folder}
**Format:** {format}
**DPI:** {dpi}
**Filename Field:** {filename_field}

**Steps:**
1. Layout {layout_name}: Atlas → Generate Atlas ✓
2. Coverage Layer: {coverage_layer}
3. Page Name: {filename_field}
4. Atlas → Export Atlas:
   - Format: {format}
   - Directory: {output_folder}
   - Single file: No (one file per feature)
   - Filename: [{filename_field}]
   - DPI: {dpi}

**Automation via Python:**
```python
layout = QgsProject.instance().layoutManager().layoutByName('{layout_name}')
atlas = layout.atlas()
atlas.setCoverageLayer(QgsProject.instance().mapLayersByName('{coverage_layer}')[0])
atlas.setFilenameExpression('"{filename_field}"')
atlas.beginRender()
for i in range(atlas.pageCount()):
    atlas.prepareForPage(i)
    exporter = QgsLayoutExporter(layout)
    exporter.exportToPdf(f'{output_folder}/{atlas.pageName()}.pdf', QgsLayoutExporter.PdfExportSettings())
atlas.endRender()
```

**Use Case:** Parcel maps, utility sheets, species distribution maps, reporting""",
        tags=["atlas", "batch export", "map series", "automation", "layout"],
    ))

    # 5. Scheduled/Recurring Processing
    registry.register(PromptSpec(
        name="scheduled_processing",
        description="Set up recurring processing tasks (via OS scheduler + QGIS CLI).",
        category=PromptCategory.AUTOMATION,
        arguments=[
            PromptArgument("script_path", "Python script path (.py) with processing logic"),
            PromptArgument("schedule", "Cron expression or frequency", default="daily", required=False),
            PromptArgument("qgis_path", "QGIS Python executable path", default="qgis_process", required=False),
            PromptArgument("params", "Parameters to pass to script", default="", required=False),
        ],
        template="""Scheduled/Recurring Processing with QGIS:

**Script:** {script_path}
**Schedule:** {schedule}
**QGIS CLI:** {qgis_path}
**Parameters:** {params}

**Approach 1: qgis_process (Headless, QGIS 3.14+)**
```bash
# Single algorithm
qgis_process run native:buffer -- INPUT=layer.gpkg DISTANCE=100 OUTPUT=buffer.gpkg

# Model
qgis_process run model:my_model -- INPUT=layer.gpkg OUTPUT=result.gpkg

# Python script
qgis_process run python:my_script.py -- param1=value1
```

**Approach 2: Python + QGIS API (Full Control)**
```python
# script.py
import sys
sys.path.append('/path/to/qgis/python')
from qgis.core import QgsApplication, processing

QgsApplication.setPrefixPath('/usr', True)
qgs = QgsApplication([], False)
qgs.initQgis()

# Your processing code here
processing.run("native:buffer", {...})

qgs.exitQgis()
```

**Scheduling:**
- Linux/macOS: cron (`crontab -e`)
  - Daily: `0 2 * * * /usr/bin/python3 /path/script.py`
  - Hourly: `0 * * * * ...`
- Windows: Task Scheduler
  - Trigger: Daily/Weekly/Monthly
  - Action: `python.exe C:\\path\\script.py`

**Use Case:** Daily data updates, automated reporting, scheduled backups, ETL pipelines""",
        tags=["scheduled", "cron", "automation", "headless", "qgis_process", "recurring"],
    ))

    # 6. Parallel Processing
    registry.register(PromptSpec(
        name="parallel_processing",
        description="Run multiple independent processing tasks in parallel.",
        category=PromptCategory.AUTOMATION,
        arguments=[
            PromptArgument("tasks", "List of independent tasks (algorithm:params)"),
            PromptArgument("max_workers", "Maximum parallel workers", default=4, required=False),
            PromptArgument("output_folder", "Base output folder"),
        ],
        template="""Parallel Processing in QGIS:

**Tasks:** {tasks} (list of algorithm:params)
**Max Workers:** {max_workers}
**Output Folder:** {output_folder}

**Python Implementation:**
```python
import concurrent.futures
import processing
from qgis.core import QgsApplication

def run_task(task):
    algo, params = task.split(':', 1)
    import json
    params = json.loads(params)
    return processing.run(algo, params)

tasks = {tasks}
with concurrent.futures.ProcessPoolExecutor(max_workers={max_workers}) as executor:
    futures = [executor.submit(run_task, t) for t in tasks]
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
        print(f'Completed: {result}')
```

**QGIS Process Pool (Native):**
```python
from qgis.core import QgsTaskManager, QgsTask
# Create QgsTask subclasses for each algorithm
task_manager = QgsTaskManager.instance()
for task in tasks:
    task_manager.addTask(MyProcessingTask(task))
```

**Considerations:**
- GDAL/OGR: Thread-safe for reading, not for writing same file
- Memory: Each worker needs RAM for data
- CRS/Transform: Initialize in each worker
- Output: Use unique filenames per worker

**Use Case:** Large batch jobs, tile processing, multi-core utilization""",
        tags=["parallel", "multiprocessing", "concurrent", "performance", "automation"],
    ))