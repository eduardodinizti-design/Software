import os
import sys
import unittest

sys.path.insert(0, "/app/applet/repo_visualpilot")
sys.path.insert(0, "/app/applet/repo_visualpilot/tests")

from test_multi_table_tracker import TestMultiTableTracker

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMultiTableTracker)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
