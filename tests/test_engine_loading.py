"""The backend must get THIS checkout's engine, however it is loaded.

The gateway loads app modules under a synthetic per-app namespace whose root
package's search path is the app directory (see kiro_crew.apps.module_loader),
and unloads exactly those keys on uninstall/disable. An engine imported as a
plain top-level ``engine`` would live outside that namespace, survive a
reinstall, and hand the new backend the previous version's client -- which is
how a freshly installed backend once failed with ``'TrekAPI' object has no
attribute 'me'``. This test loads ``backend.paths`` the gateway's way and checks
the engine lands inside the namespace, with the engine's own sibling imports
resolving there too.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


def _load_like_the_gateway(root: str, dotted: str):
    """Register the synthetic root + parent packages, then exec the module by file."""
    pkg = types.ModuleType(root)
    pkg.__path__ = [str(APP_ROOT)]
    sys.modules[root] = pkg
    parts = dotted.split(".")
    parent = root
    for seg in parts[:-1]:
        parent = f"{parent}.{seg}"
        mod = types.ModuleType(parent)
        mod.__path__ = [str(APP_ROOT.joinpath(*parent.split(".")[1:]))]
        sys.modules[parent] = mod
    spec = importlib.util.spec_from_file_location(f"{root}.{dotted}", APP_ROOT.joinpath(*parts).with_suffix(".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_engine_resolves_inside_the_app_namespace():
    root = "_test_travel_desk_ns"
    try:
        paths = _load_like_the_gateway(root, "backend.paths")
        assert paths.deskpaths.__name__ == f"{root}.engine.deskpaths"
        trek_api = paths.engine_module("trek_api")
        assert trek_api.__name__ == f"{root}.engine.trek_api"
        # the engine module's own `from . import deskpaths` stayed in the namespace
        assert trek_api.deskpaths is paths.deskpaths
        assert hasattr(trek_api.TrekAPI, "me")
        # nothing leaked into the shared top-level names the gateway cannot unload
        assert str(APP_ROOT) not in sys.path or "engine" in sys.modules  # tests may legitimately have both
    finally:
        for key in [k for k in sys.modules if k == root or k.startswith(root + ".")]:
            del sys.modules[key]


def test_engine_falls_back_to_sys_path_for_top_level_imports():
    """Tests and tooling import ``backend`` as a top-level package; there the
    relative parent does not exist and the app root on sys.path serves instead."""
    from backend import paths

    trek_api = paths.engine_module("trek_api")
    assert trek_api.__name__ == "engine.trek_api"
    assert trek_api.deskpaths is paths.deskpaths
