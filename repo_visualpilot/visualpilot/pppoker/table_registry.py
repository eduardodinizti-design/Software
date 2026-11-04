"""Session-local table tracks; these keys are not PPPoker table or hand IDs."""
from uuid import uuid4
from collections import Counter


def overlap(a, b):
    x = max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]))
    y = max(0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    intersection = x*y
    return intersection / (a[2]*a[3]+b[2]*b[3]-intersection)


class TableRegistry:
    def __init__(self, lost_cycles=3):
        self.tracks = {}
        self.next_number = 1
        self.lost_cycles = lost_cycles

    def update(self, detections, present_windows=None):
        remaining = set(self.tracks)
        counts = Counter(d.get('window_key') for d in detections)
        previous_counts = Counter(d.get('window_key') for d in self.tracks.values())
        accepted = []
        for detection in detections:
            win = detection.get('window_key')
            # A shared native handle is not evidence that two distinct ROIs
            # are the same table. Only suppress duplicate spatial detections.
            if any(detection['monitor'] == old['monitor']
                   and win == old.get('window_key')
                   and overlap(detection['box'], old['box']) >= .8 for old in accepted):
                continue
            accepted.append(detection)
            matches = [key for key in remaining
                       if win and counts[win] == 1 and previous_counts[win] == 1
                       and self.tracks[key].get('window_key') == win]
            if not matches:
                def spatial_match(old):
                    previous_win = old.get('window_key')
                    if win and previous_win and win != previous_win:
                        return False
                    if win and win == previous_win and detection.get('window_box') and old.get('window_box'):
                        def local(item):
                            x, y, w, h = item['box']
                            a, b, _, _ = item['window_box']
                            return [x-a, y-b, w, h]
                        return overlap(local(old), local(detection)) >= .65
                    return (old['monitor'] == detection['monitor']
                            and overlap(old['box'], detection['box']) >= .65)
                matches = [key for key in remaining
                           if spatial_match(self.tracks[key])]
            if len(matches) == 1:
                key = matches[0]
                remaining.remove(key)
            else:
                key = uuid4().hex
                self.tracks[key] = {'table_key': key, 'number': self.next_number}
                self.next_number += 1
            self.tracks[key].update(detection, window_key=win,
                                    candidate_only=detection.get('candidate_only',False),
                                    window_box=detection.get('window_box'),
                                    missing_cycles=0, visible=True)
        retired = []
        for key in remaining:
            track = self.tracks[key]
            track['missing_cycles'] += 1
            track['visible'] = False
            still_open = (present_windows is not None
                          and track.get('window_key') in present_windows)
            if track['missing_cycles'] >= self.lost_cycles and not still_open:
                retired.append(self.tracks.pop(key))
        return sorted((dict(t) for t in self.tracks.values()), key=lambda t: t['number']), retired
