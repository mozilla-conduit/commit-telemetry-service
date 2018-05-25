# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest

pytestmark = pytest.mark.usefixtures('null_config')


@pytest.fixture
def null_config(monkeypatch):
    """Set all of our environment configuration to harmless values."""
    keys = [
        'TARGET_REPO',
        'PULSE_USERNAME',
        'PULSE_PASSWORD',
        'PUSH_NOTIFICATION_TOPIC',
        'PULSE_QUEUE_NAME',
        'PULSE_QUEUE_ROUTING_KEY',
        'TMO_PING_NAMESPACE',
        'TMO_PING_DOCTYPE',
        'TMO_PING_DOCVERSION',
    ]
    for k in keys:
        monkeypatch.setenv(k, 'x')


@pytest.mark.parametrize(
    "test_input,expected", [
        ("no bug - foo",                True),
        ("bar baz - No bug, blah",      True),
        ("bar baz - NO BUG",            True),
        ("Bug 1234 - blah blah",        False),
        ("Bug 1234 - No blah for bug",  False),
    ]
) # yapf: disable
def test_nobug_marker(test_input, expected):
    from committelemetry.classifier import has_no_bug_marker
    assert has_no_bug_marker(test_input) == expected


@pytest.mark.parametrize(
    "test_input,expected", [
        ("foo",             "foo"),
        ("foo\nbar\nbaz",   "foo"),
    ]
) # yapf: disable
def test_summary_splitting(test_input, expected):
    from committelemetry.classifier import split_summary
    assert split_summary(test_input) == expected


@pytest.mark.parametrize(
    "test_input,expected", [
        ("Bug 123 - [wpt PR 123] foo bar a=testonly", True),
        ("Bug 123 - [wpt PR 123] foo bar a=testonly extra", True),
        ("Bug 123 - [wpt PR 123]",          False),
        ("Bug 123 - foo bar a=testonly",    False),
    ]
) # yapf: disable
def test_has_wpt_uplift_markers(test_input, expected):
    from committelemetry.classifier import has_wpt_uplift_markers
    assert has_wpt_uplift_markers(test_input) == expected
