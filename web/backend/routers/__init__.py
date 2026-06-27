"""
Router package initialization.

Router modules are loaded lazily so importing one router does not initialize
unrelated database, streaming, or optional dependency stacks.
"""

from importlib import import_module


_ROUTER_MODULES = {
    'device_router': '.device_router',
    'video_router': '.video_router',
    'streaming_router': '.streaming_router',
    'renderer_router': '.renderer_router',
    'overlay_router': '.overlay_router',
    'projection_router': '.projection_router',
    'mapping_router': '.mapping_router',
    'media_library_router': '.media_library_router',
    'widget_router': '.widget_router',
    'depth_router': '.depth_router',
}


def __getattr__(name):
    module_name = _ROUTER_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    return module.router


__all__ = [name for name in _ROUTER_MODULES if name != 'depth_router']
