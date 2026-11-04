import unittest
from unittest.mock import patch
from tools.validate_desktop_distribution import require_desktop_validation, REQUIRED_CHECKS
from visualpilot.viz.launcher import BUILD_ID


class DesktopReleaseTests(unittest.TestCase):
    def test_zero_exit_or_passed_status_without_desktop_checks_cannot_release(self):
        with self.assertRaisesRegex(RuntimeError, 'não foram validados'):
            require_desktop_validation(dict(status='passed', mode='frozen', platform='win32', build=BUILD_ID), 'dist')

    def test_changed_packaged_assets_invalidate_desktop_proof(self):
        report = dict(status='passed', mode='frozen', platform='win32', build=BUILD_ID,
            checks=list(REQUIRED_CHECKS), bundles={name: dict(sha256='old', files=2)
                for name in ('VisualPilot_Central', 'VisualPilot_Coletor')})
        with patch('tools.validate_desktop_distribution.fingerprint', return_value=dict(sha256='changed', files=2)):
            with self.assertRaisesRegex(RuntimeError, 'diferem'):
                require_desktop_validation(report, 'dist')
