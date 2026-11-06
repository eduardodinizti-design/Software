"""Bounded rolling timings, no frames or files retained."""
from collections import deque
import math
import statistics

class ObservationMetrics:
    def __init__(self, limit=120):
        self.samples=deque(maxlen=limit)
    def add(self, capture, report, cycle_ms):
        values={'capture':capture.get('duration_ms'), **report.get('timings_ms',{}), 'cycle':cycle_ms}
        self.samples.append({k:float(v) for k,v in values.items()
                             if isinstance(v,(int,float)) and math.isfinite(v) and v>=0})
    def summary(self):
        result={}
        for key in sorted({k for row in self.samples for k in row}):
            values=sorted(row[key] for row in self.samples if key in row)
            result[key]={'n':len(values),'median_ms':round(statistics.median(values),1),
                         'p95_ms':round(values[math.ceil(.95*len(values))-1],1)}
        return result
