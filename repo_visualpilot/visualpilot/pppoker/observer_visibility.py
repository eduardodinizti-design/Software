"""Conservative desktop occlusion handling for observer-only candidate previews."""
from .window_visibility_guardian import rect_intersection_area


def candidate_visibility(desktop_box, blockers):
    # One-pixel margin rejects contours truncated by a masked obstacle.
    x, y, w, h = desktop_box
    expanded = (x-1, y-1, w+2, h+2)
    return "OCCLUDED" if any(rect_intersection_area(expanded, b["box"]) > 0 for b in blockers) else "CLEAR"


def prepare_observer_frame(frame, client_box, blockers):
    """Mask foreign windows before detection; never change the source capture."""
    result = frame.copy()
    ox, oy, _, _ = client_box
    height, width = frame.shape[:2]
    for blocker in blockers:
        x, y, w, h = blocker["box"]
        left, top = max(0, x-ox), max(0, y-oy)
        right, bottom = min(width, x-ox+w), min(height, y-oy+h)
        if left < right and top < bottom:
            result[top:bottom, left:right] = 0
    return result
