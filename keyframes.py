"""Blender 5.2+ action/F-curve helpers.

Blender 4.4 introduced slotted actions; Blender 5.2 removed ``Action.fcurves``.
These helpers read and edit the F-curves of the slot linked to an object.
"""
from typing import Iterator

import bpy


def _channelbags(obj):
    """Yield the action channelbags linked to *obj*'s current action slot."""
    anim_data = getattr(obj, "animation_data", None)
    if not anim_data or not anim_data.action or not anim_data.action_slot:
        return
    action = anim_data.action
    slot = anim_data.action_slot
    for layer in action.layers:
        for strip in layer.strips:
            if not hasattr(strip, "channelbag"):
                continue
            channelbag = strip.channelbag(slot)
            if channelbag is not None:
                yield channelbag


def iter_action_fcurves(obj) -> Iterator["bpy.types.FCurve"]:
    """Yield every F-curve in the object's current action slot."""
    for channelbag in _channelbags(obj):
        yield from channelbag.fcurves


def location_fcurves(obj) -> list["bpy.types.FCurve"]:
    return [fc for fc in iter_action_fcurves(obj) if fc.data_path == "location"]


def count_location_fcurves(obj) -> int:
    return len(location_fcurves(obj))


def remove_location_fcurves(obj) -> int:
    """Remove only location F-curves, preserving other animation data.

    Returns the number of F-curves removed. Animation data is cleared only when
    the object has no F-curves, NLA tracks, or drivers left.
    """
    anim_data = getattr(obj, "animation_data", None)
    if not anim_data:
        return 0

    removed = 0
    for channelbag in _channelbags(obj):
        for fcurve in list(channelbag.fcurves):
            if fcurve.data_path == "location":
                channelbag.fcurves.remove(fcurve)
                removed += 1

    if removed:
        remaining = list(iter_action_fcurves(obj))
        if (not remaining
                and not anim_data.nla_tracks
                and not len(anim_data.drivers)):
            obj.animation_data_clear()
    return removed


def set_location_interpolation(obj, mode: str = "LINEAR") -> int:
    """Set interpolation for location keys and return the number of keys changed."""
    changed = 0
    for fcurve in location_fcurves(obj):
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = mode
            changed += 1
    return changed
