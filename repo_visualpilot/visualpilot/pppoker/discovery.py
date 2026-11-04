"""Visual localization for the blue PPPoker skin in the supplied recordings.
Boxes are estimates, not permission to click. Unknown screens stay unknown.
"""
from pathlib import Path
import cv2
import numpy as np
from functools import lru_cache
from time import perf_counter


@lru_cache(maxsize=4)
def _decode_reference(path, modified_ns, size):
    return _read_reference(path)

def load_reference(path=None):
    path = Path(path) if path is not None else Path(__file__).parent/"assets"/"ppp_chat.png"
    try:
        stat=path.stat()
    except OSError:
        return _read_reference(path)
    return _decode_reference(str(path),stat.st_mtime_ns,stat.st_size)

def _read_reference(path=None):
    path = Path(path) if path is not None else Path(__file__).parent/'assets'/'ppp_chat.png'
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ValueError('Não foi possível abrir a referência ppp_chat.png. '
                         'Extraia o ZIP completo em uma nova pasta. Arquivo: ' + str(path)) from exc
    if not data:
        raise ValueError('A referência ppp_chat.png está vazia. Extraia novamente o ZIP completo.')
    try:
        base = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    except cv2.error as exc:
        raise ValueError('A referência ppp_chat.png está corrompida. Extraia novamente o ZIP completo.') from exc
    if base is None or base.shape != (90, 90):
        raise ValueError('A referência ppp_chat.png é inválida; esperado PNG de 90 × 90 pixels. '
                         'Extraia novamente o ZIP completo.')
    return base


def detect_tables(rgb, diagnostics=None):
    if not isinstance(rgb, np.ndarray) or rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 2 or rgb.dtype != np.uint8:
        raise ValueError('A captura do monitor está vazia ou inválida. Confira se o monitor está disponível.')
    base = load_reference()
    factor=min(1.,1600/rgb.shape[1])
    small=cv2.resize(rgb,None,fx=factor,fy=factor)
    gray=cv2.cvtColor(small,cv2.COLOR_RGB2GRAY)
    hits=[]
    if diagnostics is not None:
        diagnostics.update(best_match=0.0, candidates_before_filter=0)
    # Reference layout: table at (280,0), 1080x1920; chat crop at (1250,1640).
    for scale in np.geomspace(.12,1.65,42):
        size=round(90*scale*factor)
        if size<9 or size>=min(gray.shape): continue
        template=cv2.resize(base,(size,size))
        scores=cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED)
        if diagnostics is not None:
            diagnostics["best_match"] = max(diagnostics["best_match"], round(float(scores.max()), 4))
        for _ in range(16):
            _,score,_,point=cv2.minMaxLoc(scores)
            if score<.85: break
            if diagnostics is not None:
                diagnostics["candidates_before_filter"] += 1
            x,y=point
            scores[max(0,y-size):y+size,max(0,x-size):x+size]=-1
            actual=size/90/factor
            left=round(x/factor-970*actual)
            top=round(y/factor-1640*actual)
            width=round(1080*actual);height=round(1920*actual)
            if left < -width*.04 or top < -height*.04: continue
            right,bottom=left+width,top+height
            if right>rgb.shape[1]+width*.04 or bottom>rgb.shape[0]+height*.04: continue
            left,top=max(0,left),max(0,top)
            right,bottom=min(rgb.shape[1],right),min(rgb.shape[0],bottom)
            area=rgb[top:bottom,left:right]
            hsv=cv2.cvtColor(area,cv2.COLOR_RGB2HSV)
            blue=(hsv[:,:,0]>=95)&(hsv[:,:,0]<=130)&(hsv[:,:,1]>70)&(hsv[:,:,2]>55)
            if blue.mean()<.50: continue
            hits.append(dict(box=[left,top,right-left,bottom-top],score=round(score,4),blue_fraction=round(float(blue.mean()),4)))
    accepted=[]
    for item in sorted(hits,key=lambda h:-h['score']):
        x,y,w,h=item['box']
        if any(abs(x-a['box'][0])<w*.35 and abs(y-a['box'][1])<h*.35 for a in accepted): continue
        # A small false match inside an already validated table is not a second table.
        if any(x >= a['box'][0] and y >= a['box'][1] and
               x+w <= a['box'][0]+a['box'][2] and y+h <= a['box'][1]+a['box'][3]
               for a in accepted): continue
        accepted.append(item)
    return sorted(accepted,key=lambda a:a['box'][0])


def table_anchor_visible(rgb):
    """Cheap per-frame guard for visual-only capture, using the known chat anchor."""
    if rgb is None or rgb.ndim != 3 or min(rgb.shape[:2]) < 80:
        return False
    height, width = rgb.shape[:2]
    size = round(width * 90 / 1080)
    area = rgb[round(height*.75):, round(width*.75):]
    if size < 9 or min(area.shape[:2]) < size:
        return False
    gray = cv2.cvtColor(area, cv2.COLOR_RGB2GRAY)
    template = cv2.resize(load_reference(), (size, size))
    score = float(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED).max())
    if score < .85:
        return False
    small = cv2.resize(rgb, (108, 192))
    hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV)
    return bool(((hsv[:, :, 0] >= 95) & (hsv[:, :, 0] <= 130)
                 & (hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 55)).mean() >= .5)


def scan_monitors(capture, stop, detector=detect_tables, excluded=()):
    """Visit every current display; one failed display never skips the next."""
    reports=[]
    detections=[]
    for index,monitor in enumerate(capture.monitors(),1):
        if stop.is_set(): break
        report=dict(monitor=index,region=monitor.to_dict(),state='capturing',tables=0)
        try:
            began=perf_counter()
            rgb=capture.grab(monitor)
            captured=perf_counter()
            report.update(capture_ms=round((captured-began)*1000,1),frame_mib=round(rgb.nbytes/1048576,2))
            if stop.is_set(): break
            # Work on the owned capture buffer, never on an application's preview.
            for ex, ey, ew, eh in excluded:
                x1, y1 = max(0, ex-monitor.left), max(0, ey-monitor.top)
                x2 = min(rgb.shape[1], ex+ew-monitor.left)
                y2 = min(rgb.shape[0], ey+eh-monitor.top)
                if x2 > x1 and y2 > y1:
                    rgb[y1:y2, x1:x2] = 0
            details={}
            found=detector(rgb,diagnostics=details)
            report.update(state='captured',tables=len(found),analysis_ms=round((perf_counter()-captured)*1000,1),**details)
            for item in found:
                x,y,w,h=item['box']
                detections.append(dict(monitor=index,box=[x+monitor.left,y+monitor.top,w,h],score=item['score']))
        except Exception as exc:
            report.update(state='error',error=str(exc))
        reports.append(report)
    return reports,detections
