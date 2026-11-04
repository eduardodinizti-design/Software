"""Source identity and monotonic timing for observations; never an action permit."""
from hashlib import sha256

MAX_SOURCE_AGE = 5.0


def frame_sha256(rgb):
    # Same pixel identity as EvidenceArchive, independent of compression on disk.
    return sha256(rgb.tobytes() + str(rgb.shape).encode()).hexdigest()


def observation(sample, generation, epoch):
    item, rgb, stamp, _ = sample
    proof=item.get('transport') or {}
    verified=proof.get('verified') is True
    return dict(table=item['table_key'], generation=generation, epoch=epoch,
                frame_sha256=frame_sha256(rgb), source_observed=stamp,
                clock_basis=('central_capture_ticket_issue_monotonic' if verified else 'central_ingress_monotonic'),
                transport_verified=verified,transport=proof,ingress_observed=item.get('ingress_observed',stamp),
                transport_sequence=item.get('sequence'),
                collector_session=item.get('collector_session'))


def pending_reading(reason):
    return dict(status='pending', reason=reason, hero=[], board=[], street=None,
                hand_id=None, actions=[], observed_actions=[], hero_buttons=[],
                action_pending=False, pot=None, hero_stack=None)
