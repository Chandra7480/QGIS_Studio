"""Engines package — Low-level execution engines."""

import importlib
from core.capability_registry import CapabilityRegistry

# Engine submodules
ENGINE_MODULES = {
    "screen_capture": "engines.screen_capture",
    "visual_automation": "engines.visual_automation",
    "mouse_keyboard": "engines.mouse_keyboard",
    "cursor_controller": "engines.cursor_controller",
    "verification": "engines.verification",
    "computer_vision": "engines.computer_vision",
    "georeferencing": "engines.georeferencing",
}


def register_engines_capabilities(capability_registry: CapabilityRegistry) -> None:
    """Register all engine capabilities with the CapabilityRegistry."""
    engine_capabilities = {
        "screen_capture": ["capture_screen", "capture_region", "periodic_capture"],
        "visual_automation": ["detect_window", "record_macro", "play_macro"],
        "mouse_keyboard": ["move_mouse", "click", "type_text", "hotkey", "scroll"],
        "cursor_controller": ["move_cursor", "click_cursor", "drag_cursor", "highlight"],
        "verification": ["verify_layer", "verify_algorithm", "verify_georeferencing", "verify_screen_capture"],
        "computer_vision": ["feature_detection", "template_matching", "homography", "image_quality"],
        "georeferencing": ["inspect_image", "detect_landmarks", "generate_gcps", "validate_gcps", "transform"],
    }

    for engine_name, capabilities in engine_capabilities.items():
        for cap_name in capabilities:
            capability_registry.register(
                category="engine",
                name=f"{engine_name}:{cap_name}",
                version="1.0.0",
                available=True,
                details={"engine": engine_name, "capability": cap_name}
            )


def get_engine(engine_name: str):
    """Get engine instance by name."""
    if engine_name not in ENGINE_MODULES:
        raise ValueError(f"Unknown engine: {engine_name}")
    mod_name = ENGINE_MODULES[engine_name]
    mod = importlib.import_module(mod_name)
    # Assume each engine has a get_engine() or main class
    if hasattr(mod, 'get_engine'):
        return mod.get_engine()
    elif hasattr(mod, f'{engine_name}_engine'):
        return getattr(mod, f'{engine_name}_engine')
    return mod