"""Integration oracle: retries are separate captures, never duplicate publications."""


def assert_partial_trace(test, records, captures, phase_count):
    partials=[row for row in records if row.get('event')=='PARTIAL_CARDS_READY']
    test.assertTrue(partials, 'No partial observations were recorded')
    identities=set()
    previous={}
    phases=[]
    for row in partials:
        source=row['observation']
        key=source['table']
        test.assertEqual(key,row['table'])
        test.assertEqual(source['generation'],row['generation'])
        identity=(key,source['epoch'],source['generation'])
        test.assertNotIn(identity,identities,'A generation published partial cards twice')
        identities.add(identity)
        sequence=source['transport_sequence']
        test.assertIn((key,sequence),captures,'Observation has no transmitted source frame')
        expected=captures[key,sequence]
        test.assertTrue(source['transport_verified'])
        test.assertTrue(source['transport']['verified'])
        test.assertEqual(source['transport']['protocol'],2)
        test.assertEqual(source['source_observed'],source['transport']['not_before_monotonic'])
        test.assertEqual(source['collector_session'],expected['session'])
        test.assertEqual(source['frame_sha256'],expected['frame_sha256'])
        test.assertEqual(row['reading']['hero'],expected['hero'])
        test.assertEqual(row['reading']['board'],expected['board'])
        test.assertEqual(row['reading']['street'],{3:'flop',4:'turn',5:'river'}.get(len(expected['board'])))
        test.assertGreaterEqual(row['timing']['source_age_seconds'],0.)
        test.assertLessEqual(row['timing']['source_age_seconds'],5.)
        test.assertFalse(row['action_authorized'])
        if key in previous:
            earlier=previous[key]
            test.assertGreater(source['generation'],earlier['generation'])
            test.assertGreater(sequence,earlier['transport_sequence'])
            test.assertGreater(source['source_observed'],earlier['source_observed'])
        previous[key]=source
        if not phases or phases[-1]!=expected['phase']:
            phases.append(expected['phase'])
    # A retry can add observations within a phase. Missing phases or a delayed
    # return to a previous hand/board are still failures, even with equal cards.
    test.assertEqual(phases,list(range(phase_count)))
    return partials
