"""Route observed flops to individually validated on-disk policy files."""
from pathlib import Path
import json
from collections import deque

from strategy.confirmed_history import ConfirmedHistory
from strategy.operational_profile import OperationalProfile
from strategy.policy_observer import PolicyObserver
from strategy.policy_disk import DiskPolicy
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash
from strategy.suit_policy import flop_signature,exact_suit_map,SuitPolicy


class PolicyLibrary:
    def __init__(self,path):
        self.path=Path(path).resolve();self.base=self.path.parent
        self._verified={};self.reload()

    def reload(self):
        value=json.loads(self.path.read_text())
        if value.get('schema')!='software.hu-policy-library.v1':raise StrategyError('POLICY_LIBRARY_SCHEMA_MISMATCH')
        entries={};equivalent={}
        for entry in value['entries']:
            key=tuple(sorted(entry['board']))
            if key in entries:raise StrategyError('AMBIGUOUS_LIBRARY_FLOP')
            target=(self.base/entry['path']).resolve()
            if not target.is_relative_to(self.base):raise StrategyError('LIBRARY_POLICY_PATH_OUTSIDE_BANK')
            entries[key]=dict(entry,resolved_path=target)
            equivalent.setdefault(flop_signature(key),[]).append(entries[key])
        self.entries,self.data,self.equivalent=entries,value,equivalent
        self.signature=self.path.stat().st_mtime_ns

    def verify_file(self,entry):
        path=entry['resolved_path'];signature=(str(path),path.stat().st_size,path.stat().st_mtime_ns)
        if self._verified.get(signature)!=entry['file_sha256']:
            if file_hash(path)!=entry['file_sha256']:raise StrategyError('LIBRARY_POLICY_FILE_CHANGED')
            self._verified[signature]=entry['file_sha256']

    def prepare(self):
        """Verify the bank before observing hands, not during the first decision."""
        for entry in self.entries.values():self.verify_file(entry)

    def _open_entry(self,entry):
        path=entry['resolved_path'];self.verify_file(entry)
        policy=DiskPolicy(path)
        if policy.fingerprint!=entry['policy_sha256']:
            policy.close();raise StrategyError('LIBRARY_POLICY_IDENTITY_CHANGED')
        return policy

    def open(self,board):
        if self.path.stat().st_mtime_ns!=self.signature:self.reload()
        entry=self.entries.get(tuple(sorted(board[:3])))
        if entry:return self._open_entry(entry)
        candidates=self.equivalent.get(flop_signature(board[:3]),())
        if not candidates:raise StrategyError('FLOP_NOT_YET_IN_VALIDATED_LIBRARY')
        matches=[]
        try:
            for candidate in candidates:
                source=self._open_entry(candidate)
                try:mapping=exact_suit_map(source.root.board[:3],board[:3],source.ranges)
                except StrategyError:source.close();continue
                matches.append(SuitPolicy(source,mapping))
            if len(matches)>1:raise StrategyError('AMBIGUOUS_SUIT_EQUIVALENT_LIBRARY_FLOP')
            if not matches:raise StrategyError('SUIT_EQUIVALENCE_DOES_NOT_PRESERVE_BOTH_PRIORS')
            return matches.pop()
        finally:
            for policy in matches:policy.close()


class LibraryHistory:
    """Keep preflop observations, bind the policy when the actual flop appears.

    Each table owns one SQLite view. Unbound preflop collection uses the same
    family context/precision, and never emits a postflop decision for that seed.
    """
    def __init__(self,library,journal,*,profile_settings=None):
        self.library,self.journal=library,journal
        self.preflop_manifest=None
        self.settings=dict(library.data.get('profile_settings',{}) if profile_settings is None else profile_settings)
        if 'policy_sha256' in self.settings:raise StrategyError('LIBRARY_PROFILE_HASH_IS_PER_POLICY')
        if not library.entries:raise StrategyError('NO_VALIDATED_POLICIES_YET')
        library.prepare()
        self.seed=library.open(next(iter(library.entries)))
        self.seed_profile=OperationalProfile(self.seed.fingerprint,**self.settings)
        self._tables={}
        self.observer=LibraryObserver(self)

    def _table(self,table_id,hand_id):
        key=str(table_id);old=self._tables.get(key)
        if old and old['hand_id']!=str(hand_id):
            if old['policy'] is not None:old['policy'].close()
            if self.journal:self.journal.close_hand(key,old['hand_id'])
            old=None
        if old is None:
            placeholder=ConfirmedHistory(self.seed,self.seed_profile,None)
            old=dict(hand_id=str(hand_id),history=placeholder,policy=None,profile=None)
            self._tables[key]=old
        return old

    def current(self,table_id):
        table=self._tables.get(str(table_id))
        return table['history'].current(str(table_id)) if table else None

    def binding(self,table_id,hand_id):
        table=self._tables.get(str(table_id))
        if not table or table['hand_id']!=str(hand_id) or table['policy'] is None:
            raise StrategyError('LIBRARY_POLICY_NOT_BOUND_TO_CONFIRMED_HAND')
        return table['policy'],table['profile']

    def observe(self,result,*,table_id,buttons,sample_id,captured_at=None):
        hand=result.get('hand') or {};hid=hand.get('hand_id') or hand.get('hand_number')
        ts=result.setdefault('table_state',{})
        if hid is None:
            ts.pop('strategy_state',None);out=dict(status='PENDING',reason='HISTORY_HAND_ID_UNREADABLE')
            ts['confirmed_history']=out;return out
        table=self._table(table_id,hid);board=(result.get('board') or {}).get('cards') or []
        if board and table['policy'] is None:
            try:
                policy=self.library.open(board)
                if policy.context!=self.seed.context:
                    policy.close();raise StrategyError('LIBRARY_FAMILY_CONTEXT_CHANGED')
                profile=OperationalProfile(policy.fingerprint,**self.settings)
                collector=ConfirmedHistory(policy,profile,self.journal)
                buffered=table['history'].current(str(table_id))
                if buffered:
                    target=collector._entry(str(table_id),hid)
                    if target['state'] is None:target['preflop']=deque(buffered['preflop'],maxlen=128)
                table.update(policy=policy,profile=profile,history=collector)
            except StrategyError as exc:
                ts.pop('strategy_state',None);out=dict(status='PENDING',reason=str(exc));ts['confirmed_history']=out;return out
        table['history'].preflop_manifest=self.preflop_manifest
        return table['history'].observe(result,table_id=table_id,buttons=buttons,sample_id=sample_id,captured_at=captured_at)

    def close(self):
        for table in self._tables.values():
            if table['policy'] is not None:table['policy'].close()
        self.seed.close()


class LibraryObserver:
    def __init__(self,history):self.history=history

    def advise(self,**kwargs):
        try:
            policy,profile=self.history.binding(kwargs['table_key'],kwargs['hand_key'])
            return PolicyObserver(policy,profile).advise(**kwargs)
        except StrategyError as exc:
            reason=(kwargs['table_state'].get('confirmed_history') or {}).get('reason') or str(exc)
            return dict(status='CONTEXT_MISSING',reason=reason,execution_allowed=False)
