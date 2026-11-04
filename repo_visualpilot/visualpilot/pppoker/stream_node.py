"""Transmissor TCP de recortes RGB; execute com python -m visualpilot.pppoker.stream_node."""
import json
import socket
import struct
import sys
import threading
import uuid
from pathlib import Path
from time import monotonic

import cv2
from visualpilot.pppoker.transport_freshness import VERSION, read_socket_ticket

MAX_PACKET = 8 * 1024 * 1024


def encoding_settings(image_codec='png', jpeg_quality=100):
    if image_codec not in ('png', 'jpeg'):
        raise ValueError('image_codec deve ser png ou jpeg.')
    if type(jpeg_quality) is not int or not 1 <= jpeg_quality <= 100:
        raise ValueError('jpeg_quality deve ser um inteiro entre 1 e 100.')
    return dict(image_codec=image_codec, jpeg_quality=jpeg_quality)


def prepare_capture(rgb):
    """Reduz a janela inteira antes do transporte, preservando sua proporção."""
    if rgb.ndim != 3 or rgb.shape[2] != 3 or not rgb.size:
        raise ValueError('Captura RGB inválida')
    if rgb.shape[1] > 755:
        rgb = cv2.resize(rgb, (755, round(rgb.shape[0] * 755 / rgb.shape[1])),
                         interpolation=cv2.INTER_CUBIC)
    return rgb


def encode_frame(member, session, table, sequence, rgb, *, capture_ticket=None,
                 active_tables=None, membership_generation=None,
                 image_codec='png', jpeg_quality=100):
    encoding_settings(image_codec, jpeg_quality)
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.shape[0] > 1800 or rgb.shape[1] > 1200:
        raise ValueError('Dimensões inválidas')
    if image_codec == 'jpeg':
        # Preserve chroma resolution for small suit symbols; never silently use 4:2:0.
        extension = '.jpg'
        parameters = [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality,
                      cv2.IMWRITE_JPEG_SAMPLING_FACTOR, cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444]
    else:
        extension, parameters = '.png', [cv2.IMWRITE_PNG_COMPRESSION, 1]
    ok, data = cv2.imencode(extension, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), parameters)
    if not ok:
        raise ValueError('Falha ao codificar imagem')
    envelope=dict(member=member,session=session,table=table,sequence=sequence,shape=list(rgb.shape),
                  image_codec=image_codec)
    if capture_ticket is not None:
        envelope.update(protocol=VERSION,capture_ticket=capture_ticket)
    if active_tables is not None:
        envelope.update(active_tables=active_tables, membership_generation=membership_generation)
    header=json.dumps(envelope).encode()
    packet = struct.pack('!I', len(header)) + header + data.tobytes()
    if len(packet) > MAX_PACKET:
        raise ValueError('Frame excede limite')
    return struct.pack('!I', len(packet)) + packet


class FrameSender:
    def __init__(self, host, port, member, *, image_codec='png', jpeg_quality=100):
        self.encoding = encoding_settings(image_codec, jpeg_quality)
        self.address = (host, port)
        self.member = member
        self.session = uuid.uuid4().hex
        self.sequence = {}
        self.socket = None
        self.capture_permit = None
        self.last_error = None
        self.active_tables = None
        self.membership_generation = 0
        self.membership_lock = threading.Lock()
        self.bytes_sent=0
        self.last_transport={}

    def set_tables(self, items):
        active = sorted({item['table_key'] for item in items})
        with self.membership_lock:
            if active != self.active_tables:
                self.active_tables = active
                self.membership_generation += 1

    def membership_snapshot(self):
        with self.membership_lock:
            return (None if self.active_tables is None else list(self.active_tables),
                    self.membership_generation)

    def before_capture(self, item):
        # A previous capture might have been occluded/aborted before send().
        if self.capture_permit is not None:self.close()
        try:
            if self.socket is None:
                self.socket=socket.create_connection(self.address,timeout=1)
                self.socket.settimeout(2)
            token=read_socket_ticket(self.socket)
            self.capture_permit=(item['table_key'],token)
            self.last_error=None
            return True
        except (OSError,ValueError) as exc:
            self.last_error=str(exc);self.close();return False

    def send(self, item, rgb, stamp=None):
        table = item['table_key']
        permit=self.capture_permit
        self.capture_permit=None
        if permit is None or permit[0]!=table or self.socket is None:
            self.last_error='Captura sem autorização temporal anterior; quadro descartado.'
            self.close()
            return False
        sequence = self.sequence.get(table, 0) + 1
        self.sequence[table] = sequence
        try:
            started=monotonic()
            active, generation = self.membership_snapshot()
            packet=encode_frame(self.member,self.session,table,sequence,prepare_capture(rgb),
                                capture_ticket=permit[1], active_tables=active,
                                membership_generation=generation, **self.encoding)
            encoded=monotonic()
            self.socket.sendall(packet)
            self.bytes_sent+=len(packet)
            self.last_transport=dict(last_frame_bytes=len(packet),total_bytes_sent=self.bytes_sent,
                prepare_encode_ms=round((encoded-started)*1000,3),
                socket_send_ms=round((monotonic()-encoded)*1000,3))
            self.last_error=None
            return True
        except (OSError,ValueError) as exc:
            self.last_error=str(exc)
            self.close()  # Nunca reenvia a captura antiga depois de reconectar.
            return False

    def close(self):
        self.capture_permit=None
        if self.socket is not None:
            self.socket.close()
            self.socket = None


def main():
    if sys.argv[1:2]==['--lab-transport-probe']:
        from visualpilot.pppoker.collector_probe import main as probe
        return probe(sys.argv[2:])
    from visualpilot.pppoker.collector_app import main as run_app
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path.cwd()
    try:
        return run_app(root)
    except Exception as exc:
        import traceback
        detail = f'{type(exc).__name__}: {exc}'
        try:
            (root/'collector_startup.log').write_text(traceback.format_exc(), encoding='utf-8')
        except OSError:
            pass
        if sys.platform == 'win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'O Coletor não iniciou.\n' + detail +
                '\nDiagnóstico: ' + str(root/'collector_startup.log'), 'VisualPilot — Coletor', 16)
        elif sys.stderr is not None:
            print(detail, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
