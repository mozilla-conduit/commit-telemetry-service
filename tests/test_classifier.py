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
