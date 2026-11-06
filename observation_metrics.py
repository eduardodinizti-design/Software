"""Bounded rolling timings, no frames or files retained."""
from collections import deque, Counter
import math
import statistics

class ObservationMetrics:
    def __init__(self, limit=120):
        self.samples=deque(maxlen=limit)
        self.outcomes=deque(maxlen=limit)
    def add(self, capture, report, cycle_ms):
        values={'capture':capture.get('duration_ms'), **report.get('timings_ms',{}), 'cycle':cycle_ms}
        attempts=report.get('attempts',{})
        for key in ('card_reading','button_reading'):
            if attempts.get(key,0)==0:values.pop(key,None)
        if not any(attempts.values()):values.pop('ocr_setup',None)
        values['cycle_with_ocr' if any(attempts.values()) else 'cycle_without_ocr']=cycle_ms
        self.outcomes.append(dict(status='ANALYZED',card_attempts=attempts.get('card_reading',0),
            rejected=sum(r.get('status')!='COMPLETE_CANDIDATE' for r in report.get('tables',[])),
            reasons=[reason for r in report.get('tables',[]) for reason in r.get('reasons',[])]))
        self.samples.append({k:float(v) for k,v in values.items()
                             if isinstance(v,(int,float)) and math.isfinite(v) and v>=0})
    def failure(self, status):
        self.outcomes.append(dict(status=status,card_attempts=0,rejected=0,reasons=[]))
    def counts(self):
        return dict(window=len(self.outcomes),statuses=dict(Counter(r['status'] for r in self.outcomes)),
                    cycles_with_card_reader=sum(r['card_attempts']>0 for r in self.outcomes),
                    rejected_regions=sum(r['rejected'] for r in self.outcomes),
                    rejection_reasons=dict(Counter(v for r in self.outcomes for v in r['reasons'])))
    def summary(self):
        result={}
        for key in sorted({k for row in self.samples for k in row}):
            values=sorted(row[key] for row in self.samples if key in row)
            result[key]={'n':len(values),'median_ms':round(statistics.median(values),1),
                         'p95_ms':round(values[math.ceil(.95*len(values))-1],1)}
        return result
