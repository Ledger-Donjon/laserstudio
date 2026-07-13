"""
Workspace package for the new Laser Studio UI.

Re-exports the workspace classes so callers can simply do
``from laserstudio.widgets.workspace import ConfigWorkspace``.
"""
from .workspace import Workspace
from .configworkspace import ConfigWorkspace, InstrumentCard
from .settingsworkspace import SettingsWorkspace
from .photoemissionworkspace import PhotoemissionWorkspace
from .scanworkspace import ScanWorkspace
from .analyzeworkspace import AnalyzeWorkspace

__all__ = [
    "Workspace",
    "ConfigWorkspace",
    "InstrumentCard",
    "SettingsWorkspace",
    "PhotoemissionWorkspace",
    "ScanWorkspace",
    "AnalyzeWorkspace",
]
