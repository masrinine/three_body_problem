"""
Three Body Problem - Blender Addon
Calculate three-body-problem in Blender.
"""

bl_info = {
    "name": "Three Body Problem",
    "author": "masrinine",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Three Body",
    "description": "Calculate three-body-problem in Blender",
    "category": "Physics",
}


from . import properties
from . import panels

def register():
    """Register addon classes and properties."""
    properties.register()
    panels.register()


def unregister():
    """Unregister addon classes and properties."""
    panels.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
