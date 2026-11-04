"""Single-use capture tickets; causal age bound, not client authentication.

The cooperating collector obtains a ticket BEFORE grabbing pixels. The central
monotonic time at issue is therefore a conservative lower bound on capture time.
No client wall-clock timestamp is trusted. Stale pixels from a faulty capture API
are a separate freeze-detection concern.
"""
import json
import secrets
import struct
from time import monotonic
from .observer.freshness import MAX_SOURCE_AGE

VERSION = 2
MAX_CONTROL_BYTES = 1024


class FreshnessError(ValueError):
    def __init__(self, reason):
        self.reason=reason
        super().__init__(reason)


class CaptureTicket:
    def __init__(self, clock=monotonic, max_age=MAX_SOURCE_AGE):
        self.clock=clock
        self.max_age=max_age
        self.issued_at=clock()
        self.token=secrets.token_hex(24)
        self.used=False

    def wire(self):
        data=json.dumps(dict(kind='capture_ticket',protocol=VERSION,
                             token=self.token,max_age_seconds=self.max_age)).encode('utf-8')
        return struct.pack('!I',len(data))+data

    def verify(self, token):
        if self.used:raise FreshnessError('ticket_already_used')
        if not isinstance(token,str) or not secrets.compare_digest(token,self.token):
            raise FreshnessError('wrong_capture_ticket')
        elapsed=self.clock()-self.issued_at
        if not 0<=elapsed<=self.max_age:raise FreshnessError('expired_capture_ticket')
        return dict(protocol=VERSION,verified=True,not_before_monotonic=self.issued_at,
                    age_upper_bound_at_receive=elapsed,age_budget_seconds=self.max_age)

    def consume(self, token):
        proof=self.verify(token)
        self.used=True
        return proof


def parse_ticket(data):
    if not 0<len(data)<=MAX_CONTROL_BYTES:raise FreshnessError('invalid_ticket_size')
    value=json.loads(data)
    if (not isinstance(value,dict) or value.get('kind')!='capture_ticket' or
            value.get('protocol')!=VERSION or not isinstance(value.get('token'),str)
            or len(value['token'])!=48):
        raise FreshnessError('invalid_ticket')
    return value['token']


async def read_capture_ticket(reader):
    """Async peer helper for replay/loopback clients; capture must follow this call."""
    import asyncio
    header=await asyncio.wait_for(reader.readexactly(4),2)
    size=struct.unpack('!I',header)[0]
    if not 0<size<=MAX_CONTROL_BYTES:raise FreshnessError('invalid_ticket_size')
    return parse_ticket(await asyncio.wait_for(reader.readexactly(size),2))


def read_socket_ticket(sock):
    def exact(size):
        chunks=[]
        while size:
            chunk=sock.recv(size)
            if not chunk:raise OSError('A Central encerrou a conexão.')
            chunks.append(chunk);size-=len(chunk)
        return b''.join(chunks)
    size=struct.unpack('!I',exact(4))[0]
    if not 0<size<=MAX_CONTROL_BYTES:raise FreshnessError('invalid_ticket_size')
    return parse_ticket(exact(size))
