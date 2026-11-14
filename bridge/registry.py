"""Universal AI GIS Studio — Command Registry.

Central registry for all socket server commands with signature validation.
"""

import os
from .wire import BATCH_BLOCKED_COMMANDS, UNRECORDED_COMMANDS

# Command registry: cmd_type -> handler method name
COMMANDS = {}

# Compound mode: 27 grouped commands
COMPOUND_COMMANDS = {
    "system": [
        ("ping", "ping"),
        ("diagnose", "diagnose"),
        ("get_qgis_info", "get_qgis_info"),
        ("get_message_log", "get_message_log"),
    ],
    "project": [
        ("load_project", "load_project"),
        ("create_new_project", "create_new_project"),
        ("save_project", "save_project"),
        ("get_project_info", "get_project_info"),
        ("set_project_crs", "set_project_crs"),
    ],
    "layer": [
        ("get_layers", "get_layers"),
        ("add_vector_layer", "add_vector_layer"),
        ("add_raster_layer", "add_raster_layer"),
        ("remove_layer", "remove_layer"),
        ("find_layer", "find_layer"),
        ("create_memory_layer", "create_memory_layer"),
        ("set_layer_visibility", "set_layer_visibility"),
        ("zoom_to_layer", "zoom_to_layer"),
        ("get_layer_extent", "get_layer_extent"),
        ("set_layer_property", "set_layer_property"),
        ("get_layer_crs", "get_layer_crs"),
        ("set_layer_crs", "set_layer_crs"),
        ("get_active_layer", "get_active_layer"),
        ("set_active_layer", "set_active_layer"),
        ("add_table_join", "add_table_join"),
        ("export_layer", "export_layer"),
    ],
    "features": [
        ("get_layer_features", "get_layer_features"),
        ("add_features", "add_features"),
        ("update_features", "update_features"),
        ("update_feature_geometry", "update_feature_geometry"),
        ("delete_features", "delete_features"),
        ("select_features", "select_features"),
        ("get_selection", "get_selection"),
        ("clear_selection", "clear_selection"),
        ("get_field_statistics", "get_field_statistics"),
        ("get_unique_values", "get_unique_values"),
    ],
    "selection": [
        ("select_features", "select_features"),
        ("get_selection", "get_selection"),
        ("clear_selection", "clear_selection"),
    ],
    "style": [
        ("set_layer_style", "set_layer_style"),
        ("set_raster_style", "set_raster_style"),
        ("apply_style_qml", "apply_style_qml"),
        ("save_style_qml", "save_style_qml"),
        ("get_layer_labeling", "get_layer_labeling"),
        ("set_layer_labeling", "set_layer_labeling"),
    ],
    "canvas": [
        ("get_canvas_screenshot", "get_canvas_screenshot"),
        ("get_canvas_extent", "get_canvas_extent"),
        ("set_canvas_extent", "set_canvas_extent"),
        ("get_canvas_scale", "get_canvas_scale"),
        ("set_canvas_scale", "set_canvas_scale"),
    ],
    "render": [
        ("render_map", "render_map"),
        ("get_3d_screenshot", "get_3d_screenshot"),
    ],
    "processing": [
        ("execute_processing", "execute_processing"),
        ("execute_processing_batch", "execute_processing_batch"),
        ("list_processing_algorithms", "list_processing_algorithms"),
        ("get_algorithm_help", "get_algorithm_help"),
        ("get_processing_providers", "get_processing_providers"),
        ("create_processing_model", "create_processing_model"),
        ("list_processing_models", "list_processing_models"),
        ("run_model", "run_model"),
        ("start_processing_job", "start_processing_job"),
        ("get_processing_job", "get_processing_job"),
        ("cancel_processing_job", "cancel_processing_job"),
    ],
    "code": [
        ("execute_code", "execute_code"),
        ("batch_commands", "batch"),
        ("validate_expression", "validate_expression"),
    ],
    "batch": [
        ("batch_commands", "batch"),
    ],
    "layer_tree": [
        ("get_layer_tree", "get_layer_tree"),
        ("create_layer_group", "create_layer_group"),
        ("move_layer_to_group", "move_layer_to_group"),
        ("duplicate_layer", "duplicate_layer"),
        ("set_layer_order", "set_layer_order"),
    ],
    "plugins": [
        ("list_plugins", "list_plugins"),
        ("get_plugin_info", "get_plugin_info"),
        ("reload_plugin", "reload_plugin"),
    ],
    "variables": [
        ("get_project_variables", "get_project_variables"),
        ("set_project_variable", "set_project_variable"),
    ],
    "settings": [
        ("get_setting", "get_setting"),
        ("set_setting", "set_setting"),
    ],
    "expression": [
        ("evaluate_expression", "evaluate_expression"),
    ],
    "query": [
        ("execute_sql", "execute_sql"),
        ("identify_features", "identify_features"),
    ],
    "transform": [
        ("transform_coordinates", "transform_coordinates"),
    ],
}

# Build reverse mapping: original_cmd -> (group, action)
_COMPOUND_REVERSE_MAP = {}
for group, actions in COMPOUND_COMMANDS.items():
    for action, cmd in actions:
        _COMPOUND_REVERSE_MAP[cmd] = (group, action)


def command(func):
    """Decorator to register a command handler."""
    COMMANDS[func.__name__] = func
    return func


def command_batch_blocked(func):
    """Decorator for commands that are blocked in batch mode."""
    BATCH_BLOCKED_COMMANDS.add(func.__name__)
    return command(func)


def get_compound_groups():
    """Get the compound command groups for the current tool mode."""
    tool_mode = os.environ.get("QGIS_MCP_TOOL_MODE", "granular").lower()
    if tool_mode != "compound":
        return None
    return {
        group: [action for action, _ in actions]
        for group, actions in COMPOUND_COMMANDS.items()
    }