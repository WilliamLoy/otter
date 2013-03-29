"""
Mixins and utilities to be used for testing.
"""
import mock
import os

from zope.interface import directlyProvides


class DeferredTestMixin(object):
    """
    Class that can be used for asserting whether a ``Deferred`` has fired or
    failed
    """

    def assert_deferred_succeeded(self, deferred):
        """
        Synonym for self.successResultOf - provided for compatibility and
        because self.assert_deferred_failed is still needed to check for
        expected failures.
        """
        return self.successResultOf(deferred)

    def assert_deferred_failed(self, deferred, *expected_failures):
        """
        Asserts that the deferred should have errbacked with the given
        expected failures.  This is like
        :func:`twisted.trial.unittest.TestCase.assertFailure` except that it
        asserts that it has _already_ failed.

        :param deferred: the ``Deferred`` to check
        :type deferred: :class:`twisted.internet.defer.Deferred`

        :param expected_failures: all the failures that are expected.  If None,
            will return true so long as the deferred errbacks, with whatever
            error.  If provided, ensures that the failure matches
            one of the expected failures.
        :type expected_failures: Exceptions

        :return: whatever the Exception was that was expected, or None if the
            test failed
        """
        failure = self.failureResultOf(deferred)
        if expected_failures and not failure.check(*expected_failures):
            self.fail('\nExpected: {0!r}\nGot:\n{1!s}'.format(
                expected_failures, failure))
        return failure


def fixture(fixture_name):
    """
    :param fixture_name: The base filename of the fixture, ex: simple.atom.
    :type: ``bytes``

    :returns: ``bytes``
    """
    return open(os.path.join(
        os.path.dirname(__file__),
        'fixtures',
        fixture_name
    )).read()


def iMock(iface, **kwargs):
    """
    Creates a mock object that provides a particular interface.

    :param iface: the interface to provide
    :type iface: :class:``zope.interface.Interface``

    :returns: a mock object that is specced to have the attributes and methods
        as a provider of the interface
    :rtype: :class:``mock.MagicMock``
    """
    if 'spec' in kwargs:
        del kwargs['spec']

    imock = mock.MagicMock(spec=iface.names(), **kwargs)
    directlyProvides(imock, iface)
    return imock


def patch_testcase(test_case, name, to_be_patched, **kwargs):
    """
    Patches and starts a test case, and adds the patcher to the test case's
    `self.patches`, and the mock to the test case's `self.mocks`
    """
    if getattr(test_case, 'patches', None) is None:
        test_case.patches = {}
    if getattr(test_case, 'mocks', None) is None:
        test_case.mocks = {}

    test_case.patches[name] = mock.patch(to_be_patched, **kwargs)
    test_case.mocks[name] = test_case.patches[name].start()
    if len(test_case.patches) == 1:  # only add this once
        test_case.addCleanup(mock.patch.stopall)
        # clear out the mocks and patches so that the next time around stopping
        # the patches will be added as a cleanup
        test_case.addCleanup(test_case.patches.clear)
        test_case.addCleanup(test_case.mocks.clear)
