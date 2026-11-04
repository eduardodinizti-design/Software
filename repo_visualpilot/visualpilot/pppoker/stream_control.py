"""Bounded status exchanges on a separate socket; never capture freshness."""
import json
import socket
import struct
from time import monotonic

from visualpilot.pppoker.transport_freshness import VERSION, parse_ticket

CONTROL_VERSION = 1
CONTROL_LIMIT = 4096
HEARTBEAT_INTERVAL = 2.0
HEARTBEAT_TIMEOUT = 6.0


def encode_status(member, session, sequence, token, active_tables, generation, discovery_state='ready'):
    header=json.dumps(dict(kind='collector_status',protocol=VERSION,control_version=CONTROL_VERSION,
        member=member,session=session,control_sequence=sequence,capture_ticket=token,
        active_tables=active_tables,membership_generation=generation,discovery_state=discovery_state)).encode()
    if len(header)>CONTROL_LIMIT:raise ValueError('Estado do Coletor excede o limite')
    packet=struct.pack('!I',len(header))+header
    return struct.pack('!I',len(packet))+packet


def read_message(sock,deadline):
    def exact(size):
        chunks=[]
        while size:
            remaining=deadline-monotonic()
            if remaining<=0:raise TimeoutError('Prazo de controle excedido')
            sock.settimeout(min(2,remaining))
            chunk=sock.recv(size)
            if not chunk:raise OSError('Central encerrou o controle; verifique a versão dos dois programas.')
            chunks.append(chunk);size-=len(chunk)
        return b''.join(chunks)
    size=struct.unpack('!I',exact(4))[0]
    if not 0<size<=CONTROL_LIMIT:raise ValueError('Confirmação de controle acima do limite')
    return exact(size)


def read_ack(sock,deadline):
    ack=json.loads(read_message(sock,deadline))
    if not isinstance(ack,dict):raise ValueError('Confirmação de controle inválida')
    return ack


class ControlSender:
    def __init__(self,address,member,session):
        self.address,self.member,self.session=address,member,session
        self.sequence=0

    def exchange(self,active_tables,generation,discovery_state='ready'):
        self.sequence+=1
        started=monotonic()
        # Each exchange has its own socket, bounded reads and explicit ACK.
        # Capture cannot steal this reply or interleave bytes with the control.
        with socket.create_connection(self.address,timeout=1) as sock:
            sock.settimeout(2)
            token=parse_ticket(read_message(sock,started+4))
            packet=encode_status(self.member,self.session,self.sequence,token,active_tables,generation,discovery_state)
            sock.sendall(packet)
            ack=read_ack(sock,started+4)
        if (ack.get('kind')!='collector_ack' or ack.get('control_version')!=CONTROL_VERSION
                or ack.get('session')!=self.session or ack.get('control_sequence')!=self.sequence):
            raise ValueError('Confirmação de controle não corresponde ao pedido')
        return dict(control_roundtrip_ms=round((monotonic()-started)*1000,3),
                    control_sequence=self.sequence,control_bytes=len(packet))


class AdaptiveFpsThrottler:
    """Throttler de FPS adaptativo para otimização de CPU/GPU em multi-mesas (6+)."""
    def __init__(self, idle_fps: int = 10, active_fps: int = 30):
        self.idle_fps = idle_fps
        self.active_fps = active_fps
        self.last_capture_times: Dict[str, float] = {}

    def should_capture(self, table_id: str, is_hero_turn: bool) -> bool:
        """Determina se o frame da mesa deve ser capturado com base no FPS alvo."""
        target_fps = self.active_fps if is_hero_turn else self.idle_fps
        interval = 1.0 / target_fps
        now = monotonic()
        
        last = self.last_capture_times.get(table_id, 0.0)
        if (now - last) >= interval:
            self.last_capture_times[table_id] = now
            return True
        return False
