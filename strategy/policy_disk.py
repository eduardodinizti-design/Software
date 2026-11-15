"""Immutable, bounded-memory policy files. Full trees stay on disk, not in RAM."""
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import array
import sys
import zlib

from strategy.action_tree import Action, BetMenu, apply_action, is_legal
from strategy.range_catalog import ComboRange, DECK, combo_key, joint_deals
from strategy.state_contract import BettingState, GameContext, StrategyError, digest, reveal, validate_game


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def stored_node(state,actions,rows,native_probabilities=None):
    if native_probabilities is None:
        return encoded(dict(state=state.to_dict(),actions=[a.to_dict() for a in actions],combos=rows))
    normalized=all(isinstance(row,dict) for row in rows.values())
    ids=[a.id for a in actions]
    values=([rows[k]['frequencies'][a] for k in sorted(rows) for a in ids] if normalized
            else [p for k in sorted(rows) for p in native_probabilities[k]])
    use_float32=array.array('f',values).tolist()==values
    matrix=array.array('f' if use_float32 else 'd',values)
    if sys.byteorder!='little':matrix.byteswap()
    metadata=dict(state=state.to_dict(),actions=[a.to_dict() for a in actions],normalized=normalized,
                  encoding='native_float32' if use_float32 else 'native_float64')
    if normalized:
        annotations={k:{f:v for f,v in row.items() if f!='frequencies' and v is not None} for k,row in rows.items()}
        if any(annotations.values()):metadata['annotations']=annotations
    header=encoded(metadata)
    return b'VPB1'+len(header).to_bytes(4,'little')+header+matrix.tobytes()


def decoded_node(raw,ranges,*,include_rows=True):
    if not raw.startswith(b'VPB1'):return json.loads(raw)
    size=int.from_bytes(raw[4:8],'little');node=json.loads(raw[8:8+size])
    if not include_rows:return node
    state=BettingState.from_dict(node['state']);n=len(node['actions'])
    matrix=array.array('f' if node.pop('encoding')=='native_float32' else 'd')
    matrix.frombytes(raw[8+size:])
    if sys.byteorder!='little':matrix.byteswap()
    combos=sorted(k for k,_ in ranges[state.actor].weights if not set((k[:2],k[2:])).intersection(state.board))
    if len(matrix)!=len(combos)*n:raise StrategyError('DISK_POLICY_MATRIX_LENGTH_CHANGED')
    ids=[Action(**a).id for a in node['actions']];rows={}
    normalized=node.pop('normalized',False);annotations=node.pop('annotations',{})
    for i,key in enumerate(combos):
        values=matrix[i*n:(i+1)*n];total=sum(values)
        if total<=0:raise StrategyError('DISK_POLICY_ZERO_DISTRIBUTION')
        rows[key]=dict(frequencies={a:p if normalized else p/total for a,p in zip(ids,values)},visits=None,action_ev_bb=None)
        rows[key].update(annotations.get(key,{}))
    node['combos']=rows
    return node


class PolicyWriter:
    def __init__(self,path,context,root,ranges,menu):
        self.path=Path(path)
        if self.path.exists():raise StrategyError('POLICY_OUTPUT_ALREADY_EXISTS')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.context,self.root,self.ranges,self.menu=context,root,tuple(ranges),menu
        self.db=sqlite3.connect(self.path)
        self.db.executescript('''
          PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;
          CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE nodes(key TEXT PRIMARY KEY,flop_key TEXT NOT NULL UNIQUE,payload BLOB NOT NULL,sha TEXT NOT NULL,street TEXT NOT NULL);
          CREATE TABLE expected(key TEXT PRIMARY KEY,parent TEXT NOT NULL);
        ''')
        self.count=0
        self.allowed=OrderedDict()
        self.possible_cache=OrderedDict()

    def permitted(self,state):
        key=(state.board,state.actor)
        if key not in self.allowed:
            self.allowed[key]={k for k,_ in self.ranges[state.actor].weights if k[:2] not in state.board and k[2:] not in state.board}
            if len(self.allowed)>8:self.allowed.popitem(last=False)
        self.allowed.move_to_end(key)
        return self.allowed[key]

    def possible(self,board):
        board=tuple(board)
        if board not in self.possible_cache:
            try:value=next(joint_deals(self.ranges,board),None) is not None
            except StrategyError as exc:
                if str(exc)!='EMPTY_RANGE':raise
                value=False
            self.possible_cache[board]=value
            if len(self.possible_cache)>256:self.possible_cache.popitem(last=False)
        return self.possible_cache[board]

    def add(self,state,actions,rows,*,native_probabilities=None):
        validate_game(self.context,state)
        if state.terminal or state.needs_cards or not actions or any(not is_legal(state,a) for a in actions):
            raise StrategyError('DISK_POLICY_ILLEGAL_ACTION_NODE')
        ids={a.id for a in actions}
        if len(ids)!=len(actions) or set(rows)!=self.permitted(state):
            raise StrategyError('DISK_POLICY_MISSING_COMBOS_OR_DUPLICATE_ACTIONS')
        for combo,row in rows.items():
            probs=row['frequencies']
            if set(probs)!=ids or any(type(p) not in (int,float) or not 0<=p<=1 for p in probs.values()) or abs(sum(probs.values())-1)>1e-6:
                raise StrategyError('DISK_POLICY_INVALID_DISTRIBUTION')
        if native_probabilities is not None:
            if set(native_probabilities)!=set(rows):raise StrategyError('NATIVE_MATRIX_COMBOS_CHANGED')
            for key,values in native_probabilities.items():
                total=sum(values)
                if len(values)!=len(actions) or total<=0 or any(type(p) not in (float,int) or not 0<=p<=1 for p in values):
                    raise StrategyError('NATIVE_MATRIX_INVALID_VALUES')
                if any(abs(rows[key]['frequencies'][a.id]-p/total)>1e-12 for a,p in zip(actions,values)):
                    raise StrategyError('NATIVE_MATRIX_DISAGREES_WITH_VALIDATED_FREQUENCIES')
        raw=stored_node(state,actions,rows,native_probabilities)
        self._store(state,raw)

    def add_native(self,state,actions,probabilities):
        validate_game(self.context,state)
        if state.terminal or state.needs_cards or not actions or any(not is_legal(state,a) for a in actions):
            raise StrategyError('DISK_POLICY_ILLEGAL_ACTION_NODE')
        if len({a.id for a in actions})!=len(actions) or set(probabilities)!=self.permitted(state):
            raise StrategyError('DISK_POLICY_MISSING_COMBOS_OR_DUPLICATE_ACTIONS')
        for values in probabilities.values():
            if len(values)!=len(actions) or any(type(p) not in (int,float) or not 0<=p<=1 for p in values) or abs(sum(values)-1)>2e-5:
                raise StrategyError('DISK_POLICY_INVALID_NATIVE_DISTRIBUTION')
        # Exact original numbers are stored. Normalization is deferred to lookup.
        self._store(state,stored_node(state,actions,probabilities,probabilities))

    def _store(self,state,raw):
        key=state.key()
        try:self.db.execute('INSERT INTO nodes VALUES(?,?,?,?,?)',
            (key,state.flop_order_key(),zlib.compress(raw,6),hashlib.sha256(raw).hexdigest(),state.street))
        except sqlite3.IntegrityError as exc:raise StrategyError('DUPLICATE_POLICY_PUBLIC_STATE') from exc
        self.count+=1
        if self.count%128==0:self.db.commit()

    def validate_complete(self):
        """All configured action edges and physically possible runouts, not samples."""
        terminal_edges=0
        cursor=self.db.execute('SELECT key,payload FROM nodes')
        for key,compressed in cursor:
            node=decoded_node(zlib.decompress(compressed),self.ranges,include_rows=False);state=BettingState.from_dict(node['state'])
            for raw_action in node['actions']:
                child=apply_action(state,Action(**raw_action))
                if child.terminal or (child.needs_cards and min(child.stacks)<=1e-8):
                    terminal_edges+=1;continue
                children=[child]
                if child.needs_cards:
                    children=[reveal(child,c) for c in DECK if c not in child.board and self.possible(child.board+(c,))]
                for successor in children:
                    if successor.terminal:
                        terminal_edges+=1;continue
                    self.db.execute('INSERT OR IGNORE INTO expected VALUES(?,?)',(successor.key(),key))
        self.db.commit()
        missing=self.db.execute('SELECT e.key FROM expected e LEFT JOIN nodes n ON n.key=e.key WHERE n.key IS NULL LIMIT 5').fetchall()
        if missing:raise StrategyError('POLICY_INCOMPLETE_STREETS_OR_ACTIONS:'+','.join(r[0] for r in missing))
        if not self.db.execute('SELECT 1 FROM nodes WHERE key=?',(self.root.key(),)).fetchone():
            raise StrategyError('POLICY_ROOT_MISSING')
        orphan=self.db.execute('SELECT n.key FROM nodes n LEFT JOIN expected e ON n.key=e.key WHERE e.key IS NULL AND n.key!=? LIMIT 1',(self.root.key(),)).fetchone()
        if orphan:raise StrategyError('POLICY_ORPHAN_NODE')
        counts=dict(self.db.execute('SELECT street,count(*) FROM nodes GROUP BY street'))
        return dict(structurally_complete=True,validation='ALL_ACTIONS_AND_ALL_PHYSICALLY_POSSIBLE_RUNOUTS',
                    nodes_by_street=counts,public_nodes=self.count,terminal_edges=terminal_edges)

    def finish(self,quality,*,evaluation=None):
        coverage=self.validate_complete()
        quality=dict(quality,**coverage)
        quality['exported_depth_is_not_full_tree_coverage']=False
        metadata=dict(schema='software.hu-policy-disk.v1',context=asdict(self.context),root=self.root.to_dict(),
                      ranges=[r.to_dict() for r in self.ranges],menu=asdict(self.menu),quality=quality)
        if evaluation is not None:metadata['evaluation']=evaluation
        tree_hash=hashlib.sha256()
        for key,sha in self.db.execute('SELECT key,sha FROM nodes ORDER BY key'):
            tree_hash.update((key+sha).encode())
        metadata['node_content_sha256']=tree_hash.hexdigest()
        fingerprint=digest(metadata)
        self.db.execute('INSERT INTO meta VALUES(?,?)',('metadata',encoded(metadata).decode()))
        self.db.execute('INSERT INTO meta VALUES(?,?)',('fingerprint',json.dumps(fingerprint)))
        self.db.execute('DROP TABLE expected');self.db.commit()
        if self.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise StrategyError('POLICY_SQLITE_INTEGRITY_FAILED')
        self.db.close();self.db=None
        return dict(policy_sha256=fingerprint,coverage=coverage,quality=quality)

    def close(self):
        if self.db is not None:self.db.close();self.db=None


class _Nodes(Mapping):
    def __init__(self,policy):self.policy=policy
    def __getitem__(self,key):return self.policy.get_node(key)
    def __len__(self):return self.policy.node_count
    def __iter__(self):
        for (key,) in self.policy.db.execute('SELECT key FROM nodes'):yield key


class DiskPolicy:
    def __init__(self,path,*,cache_nodes=8):
        self.path=Path(path).resolve()
        self.db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        try:
            self.data=json.loads(self.db.execute("SELECT value FROM meta WHERE key='metadata'").fetchone()[0])
            self.fingerprint=json.loads(self.db.execute("SELECT value FROM meta WHERE key='fingerprint'").fetchone()[0])
            if self.data['schema']!='software.hu-policy-disk.v1' or digest(self.data)!=self.fingerprint:
                raise StrategyError('DISK_POLICY_METADATA_CORRUPTED')
            self.context=GameContext(**self.data['context']);self.root=BettingState.from_dict(self.data['root'])
            self.ranges=tuple(ComboRange.from_dict(r) for r in self.data['ranges']);self.menu=BetMenu(**self.data['menu'])
            self.quality=self.data['quality'];self.native_menu=True
            if self.quality.get('structurally_complete') is not True:raise StrategyError('DISK_POLICY_NOT_VALIDATED_COMPLETE')
            self.node_count=self.db.execute('SELECT count(*) FROM nodes').fetchone()[0]
            if self.node_count!=self.quality['public_nodes']:raise StrategyError('DISK_POLICY_NODE_COUNT_CHANGED')
            self.nodes=_Nodes(self);self._cache=OrderedDict();self.cache_limit=max(1,int(cache_nodes))
        except Exception:
            self.db.close();raise

    def get_node(self,key):
        if key not in self._cache:
            row=self.db.execute('SELECT payload,sha FROM nodes WHERE key=?',(key,)).fetchone()
            if row is None:raise KeyError(key)
            raw=zlib.decompress(row[0])
            if hashlib.sha256(raw).hexdigest()!=row[1]:raise StrategyError('DISK_POLICY_NODE_CORRUPTED')
            self._cache[key]=decoded_node(raw,self.ranges)
            if len(self._cache)>self.cache_limit:self._cache.popitem(last=False)
        self._cache.move_to_end(key)
        return self._cache[key]

    def node_key(self,state):
        row=self.db.execute('SELECT key FROM nodes WHERE key=? OR flop_key=? LIMIT 1',(state.key(),state.flop_order_key())).fetchone()
        if row is None:raise StrategyError('POLICY_PUBLIC_NODE_MISS')
        return row[0]

    def actions(self,state):return tuple(Action(**a) for a in self.get_node(self.node_key(state))['actions'])

    def row(self,state,hand):
        node=self.get_node(self.node_key(state));key=combo_key(hand)
        if key not in node['combos']:raise StrategyError('POLICY_COMBO_MISS_OR_OFF_POLICY')
        return node,node['combos'][key]

    def probabilities(self,state,hand):
        node,row=self.row(state,hand)
        return [row['frequencies'][Action(**a).id] for a in node['actions']]

    def close(self):self.db.close();self._cache.clear()
