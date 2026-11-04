"""Receptor asyncio: valida envelopes e entrega à Mailbox do runtime."""
import asyncio
import json
import struct
from time import monotonic

import cv2
import numpy as np

from .stream_node import MAX_PACKET
from .transport_freshness import CaptureTicket, FreshnessError, VERSION
from .stream_control import CONTROL_VERSION


class StreamReceiver:
    def __init__(self, runtime, host='0.0.0.0', port=48735, *, allow_legacy=False):
        self.runtime = runtime
        self.allow_legacy=allow_legacy
        self.last_warning=None
        self.metrics=dict(accepted_verified=0,accepted_legacy=0,rejected={},image_codecs={})
        if hasattr(runtime,'metrics'):runtime.metrics['transport']=self.metrics
        self.host, self.port = host, port
        self.sequences = {}
        self.clients = set()
        self.server = None
        self.members = {}
        self.retired_sessions = set()
        self.last_seen = {}
        self.identities = {}
        self.numbers = {}
        self.memberships = {}
        self.control_sequences = {}
        self.transport_revision = 0

    def publish_tables(self):
        """Retirement reaches queues, previews and panel before delayed OCR."""
        from .multitable import latest
        self.transport_revision += 1
        active=set(self.sequences)
        epochs=self.runtime.frames.set_remote_active(active)
        status=dict(tables=[dict(table_key=k,number=self.numbers[k],state='capturando')
                            for k in self.sequences],transport_revision=self.transport_revision,
                    remote_epochs=epochs)
        captures=getattr(self.runtime,'captures',None)
        if captures is not None:latest(captures,status)
        output=getattr(self.runtime,'output',None)
        if output is not None:latest(output,dict(kind='tables',value=status))
        monitor=getattr(self.runtime,'monitor',None)
        if monitor:monitor.retain(active)

    def accept_status(self,header,ticket):
        if header.get('control_version')!=CONTROL_VERSION:raise ValueError('Versão de controle incompatível')
        discovery_state=header.get('discovery_state','ready')
        if discovery_state not in ('ready','pending','error'):raise ValueError('Estado de descoberta inválido')
        if header.get('protocol')!=VERSION or ticket is None:raise FreshnessError('missing_capture_ticket')
        ticket.verify(header.get('capture_ticket'))
        member,session=header.get('member'),header.get('session')
        if any(not isinstance(p,str) or not 0<len(p)<=128 for p in (member,session)):
            raise ValueError('Identidade de controle inválida')
        if (member,session) in self.retired_sessions:raise ValueError('Sessão de controle já retirada')
        previous=self.members.get(member)
        replacing=previous is not None and previous!=session
        now=monotonic()
        if replacing and now-self.last_seen[member]<=5:raise ValueError('Outro Coletor ainda está ativo')
        if previous is None and len(self.members)>=6:raise ValueError('Limite de membros de controle atingido')
        sequence=header.get('control_sequence')
        if type(sequence) is not int or sequence<=self.control_sequences.get((member,session),0):
            raise ValueError('Sequência de controle inválida ou repetida')
        active=header.get('active_tables')
        generation=header.get('membership_generation')
        previous_membership=self.memberships.get((member,session))
        membership=previous_membership
        if active is None:
            if type(generation) is not int or generation!=0:
                raise ValueError('Geração de descoberta indefinida inválida')
        else:
            if (type(generation) is not int or generation<1 or not isinstance(active,list)
                    or len(active)>6 or any(not isinstance(t,str) or not 0<len(t)<=128 for t in active)
                    or len(set(active))!=len(active)):
                raise ValueError('Lista de controle inválida')
            candidate=(generation,frozenset(active))
            if previous_membership and generation==previous_membership[0] and candidate!=previous_membership:
                raise ValueError('Lista conflitante para a mesma descoberta')
            # A new image may have delivered a newer discovery before this
            # heartbeat arrived. Acknowledge connection, never roll back the list.
            if discovery_state=='ready' and (previous_membership is None or generation>=previous_membership[0]):
                membership=candidate
        retired=[k for k,identity in self.identities.items() if
                 (replacing and identity[0]==member) or
                 (identity[:2]==(member,session) and membership is not None and identity[2] not in membership[1])]
        ticket.consume(header.get('capture_ticket'))
        if replacing:
            self.retired_sessions.add((member,previous))
            self.memberships.pop((member,previous),None)
            self.control_sequences.pop((member,previous),None)
        if membership is not None:self.memberships[member,session]=membership
        for key in retired:
            for mapping in (self.sequences,self.identities,self.numbers):mapping.pop(key,None)
        self.members[member]=session
        self.last_seen[member]=now
        self.control_sequences[member,session]=sequence
        if retired or membership!=previous_membership:self.publish_tables()
        self.metrics['accepted_controls']=self.metrics.get('accepted_controls',0)+1
        output=getattr(self.runtime,'output',None)
        if output is not None:
            from .multitable import latest
            latest(output,dict(kind='collector_status',member=member,session=session,
                control_sequence=sequence,observed=now,discovery_state=discovery_state,
                visible_tables=None if membership is None else len(membership[1])))
        return dict(kind='collector_ack',control_version=CONTROL_VERSION,
                    session=session,control_sequence=sequence)

    async def start(self):
        self.server = await asyncio.start_server(self.handle, self.host, self.port)
        return self.server.sockets[0].getsockname()

    async def close(self):
        if self.server:
            self.server.close()
        for writer in tuple(self.clients):
            writer.close()
            # A collector can still be sending when the user stops the Central.
            # Abort the transport so shutdown cannot wait for that peer to drain.
            writer.transport.abort()
            try:await asyncio.wait_for(writer.wait_closed(), 1)
            except (OSError, TimeoutError):pass
        if self.server:
            await self.server.wait_closed()

    def warn(self,reason):
        if reason==self.last_warning:return
        self.last_warning=reason
        messages={
            'legacy_frame_without_freshness_proof':'Coletor incompatível com a validação temporal. Atualize a Central e o Coletor juntos.',
            'expired_capture_ticket':'Imagem descartada por atraso. Aguardando uma captura nova.'}
        output=getattr(self.runtime,'output',None)
        if output is not None:
            from .multitable import latest
            latest(output,dict(kind='transport_status',reason=reason,
                warning=messages.get(reason,'Quadro recusado; aguardando nova captura.') if reason else None))

    def new_ticket(self):
        return CaptureTicket(clock=lambda:monotonic())

    def accept_packet(self, packet, ticket=None):
        try:
            return self._accept_packet(packet,ticket)
        except (ValueError,KeyError,TypeError) as exc:
            reason=getattr(exc,'reason','invalid_packet')
            counts=self.metrics['rejected'];counts[reason]=counts.get(reason,0)+1
            control=bool(getattr(exc,'control_message',False))
            self.metrics['last_error']=dict(type=type(exc).__name__,message=str(exc)[:500],
                                            channel='control' if control else 'frame')
            if not control:self.warn(reason)
            raise

    def _accept_packet(self, packet, ticket):
        if not isinstance(packet, (bytes, bytearray)) or not 4 < len(packet) <= MAX_PACKET:
            raise ValueError('Pacote incompleto ou acima do limite')
        length = struct.unpack('!I', packet[:4])[0]
        if not 0 < length <= 4096 or length + 4 > len(packet):
            raise ValueError('Cabeçalho inválido')
        header = json.loads(packet[4:4 + length])
        if not isinstance(header,dict):raise ValueError('Cabeçalho deve ser um objeto')
        if header.get('kind')=='collector_status':
            try:
                if length+4!=len(packet):raise ValueError('Controle não pode conter imagem')
                return self.accept_status(header,ticket)
            except (ValueError,KeyError,TypeError) as exc:
                exc.control_message=True
                raise
        verified=header.get('protocol')==VERSION
        if verified:
            if ticket is None:raise FreshnessError('missing_capture_ticket')
            ticket.verify(header.get('capture_ticket'))
        elif not self.allow_legacy:raise FreshnessError('legacy_frame_without_freshness_proof')
        parts = [header[k] for k in ('member', 'session', 'table')]
        if any(not isinstance(p, str) or not 0 < len(p) <= 128 for p in parts):
            raise ValueError('Identidade inválida')
        key = json.dumps(parts, separators=(',', ':'))
        member, session, table = parts
        now = monotonic()
        if (member, session) in self.retired_sessions:
            return False
        previous = self.members.get(member)
        replacing = previous is not None and previous != session
        if replacing and now - self.last_seen[member] <= 5:
            return False  # Two running collectors must not fight for ownership.
        retired = [k for k, identity in self.identities.items()
                   if replacing and identity[0] == member]
        membership = None
        active = header.get('active_tables')
        previous_membership = self.memberships.get((member, session))
        if active is not None:
            generation = header.get('membership_generation')
            if (not verified or type(generation) is not int or generation < 1
                    or not isinstance(active, list) or not 1 <= len(active) <= 6
                    or any(not isinstance(t, str) or not 0 < len(t) <= 128 for t in active)
                    or len(set(active)) != len(active) or table not in active):
                raise ValueError('Lista de mesas inválida')
            membership = (generation, frozenset(active))
            if previous_membership:
                if generation < previous_membership[0]:
                    raise ValueError('Lista de mesas de uma descoberta anterior')
                if generation == previous_membership[0] and membership != previous_membership:
                    raise ValueError('Lista de mesas conflitante para a mesma descoberta')
            retired += [k for k, identity in self.identities.items()
                        if identity[:2] == (member, session) and identity[2] not in active]
        elif previous_membership is not None:
            raise ValueError('Quadro sem a lista de mesas da sessão')
        seq = header['sequence']
        if type(seq) is not int or seq <= 0:
            raise ValueError('Sequência inválida')
        if seq <= self.sequences.get(key, 0):
            return False
        if key not in self.sequences and len(self.sequences) - len(retired) >= 6:
            raise ValueError('Limite de seis mesas atingido')
        shape = header['shape']
        if len(shape) != 3 or not (0 < shape[0] <= 1800 and 0 < shape[1] <= 1200 and shape[2] == 3):
            raise ValueError('Dimensões inválidas')
        # Old senders omit the codec and send PNG. An explicit codec must match
        # the payload; malformed data must not consume a ticket or retire tables.
        codec = header.get('image_codec', 'png')
        payload = packet[4 + length:]
        signatures = {'png': b'\x89PNG\r\n\x1a\n', 'jpeg': b'\xff\xd8\xff'}
        if not isinstance(codec, str) or codec not in signatures or not payload.startswith(signatures[codec]):
            raise ValueError('Formato de imagem inválido ou diferente do cabeçalho')
        if codec == 'jpeg' and not payload.endswith(b'\xff\xd9'):
            raise ValueError('JPEG incompleto')
        try:
            bgr = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error as exc:
            raise ValueError('Imagem inválida') from exc
        if bgr is None or list(bgr.shape) != shape:
            raise ValueError('Imagem inválida')
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        proof=(ticket.consume(header.get('capture_ticket')) if verified else
               dict(protocol=1,verified=False,reason='legacy_transport'))
        self.metrics['accepted_verified' if verified else 'accepted_legacy']+=1
        codecs=self.metrics['image_codecs']
        codecs[codec]=codecs.get(codec,0)+1
        if verified:self.warn(None)
        membership_changed = key not in self.sequences or bool(retired)
        if replacing:
            self.retired_sessions.add((member, previous))
            self.memberships.pop((member, previous), None)
            self.control_sequences.pop((member, previous), None)
        if membership is not None:
            self.memberships[member, session] = membership
        for old in retired:
            for mapping in (self.sequences, self.identities, self.numbers):
                mapping.pop(old, None)
        self.members[member] = session
        self.last_seen[member] = now
        self.identities[key] = (member, session, table)
        if key not in self.numbers:
            self.numbers[key] = next(n for n in range(1, 7) if n not in self.numbers.values())
        self.sequences[key] = seq
        if membership_changed:
            self.publish_tables()
        monitor = getattr(self.runtime, 'monitor', None)
        if monitor:
            monitor.retain(set(self.sequences))
            monitor.frame(key, self.numbers[key], rgb)
        self.runtime.frames.put(dict(table_key=key, number=self.numbers[key],
                                     sequence=seq,collector_session=session,transport=proof,
                                     image_codec=codec,remote_epoch=self.runtime.frames.remote_epochs[key]), rgb)
        return True

    async def handle(self, reader, writer):
        self.clients.add(writer)
        try:
            ticket=self.new_ticket()
            writer.write(ticket.wire());await writer.drain()
            while True:
                prefix = await asyncio.wait_for(reader.readexactly(4), 5)
                size = struct.unpack('!I', prefix)[0]
                if not 4 < size <= MAX_PACKET:
                    raise ValueError('Pacote inválido')
                packet = await asyncio.wait_for(reader.readexactly(size), 5)
                # Uma chamada por vez evita inversão de sequência e mantém a fila limitada.
                result=self.accept_packet(packet,ticket)
                if isinstance(result,dict):
                    ack=json.dumps(result).encode()
                    writer.write(struct.pack('!I',len(ack))+ack);await writer.drain()
                    break  # One bounded control exchange per independent socket.
                if ticket.used:
                    ticket=self.new_ticket()
                    writer.write(ticket.wire());await writer.drain()
        except (asyncio.IncompleteReadError, TimeoutError, ValueError, KeyError, TypeError, OSError):
            pass
        finally:
            self.clients.discard(writer)
            writer.close()
            try:await writer.wait_closed()
            except OSError:pass


async def run_remote_session(runtime, config_path='stream_config.ini'):
    """Inicia receptor e runtime juntos; runtime.stop encerra ambos."""
    import configparser
    config = configparser.ConfigParser()
    if not config.read(config_path):
        raise FileNotFoundError(config_path)
    receiver = StreamReceiver(runtime,
        config.get('central', 'listen_host', fallback='0.0.0.0'),
        config.getint('central', 'port'),
        allow_legacy=config.getboolean('central','allow_legacy_frames',fallback=False))
    await receiver.start()
    try:
        await asyncio.to_thread(runtime.run, capture=False)
    finally:
        runtime.stop.set()
        await receiver.close()
