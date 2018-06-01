# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Test the hgpush message processing code.
"""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures('null_config')


# This structure is described here:
# https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/notifications.html#common-properties-of-notifications
# Example messages can be collected from this URL:
# https://tools.taskcluster.net/pulse-inspector?bindings[0][exchange]=exchange%2Fhgpushes%2Fv2&bindings[0][routingKeyPattern]=%23
test_message = {
    'payload': {
        'type': 'changegroup.1',
        'data': {
            'pushlog_pushes': [
                {
                    'time': 15278721560,
                    'pushid': 64752,
                    'push_json_url': 'https://hg.mozilla.org/integration/autoland/json-pushes?version=2&startID=64751&endID=64752',
                    'push_full_json_url': 'https://hg.mozilla.org/integration/autoland/json-pushes?version=2&full=1&startID=64751&endID=64752',
                    'user': 'someuser@mozilla.org',
                }
            ],
            'heads': [
                'ebe99842f5f8d543e5453ce78b1eae3641830b13',
            ],
            'repo_url': 'https://hg.mozilla.org/integration/autoland',
        },
    },
}   # yapf: disable

def test_process_push_message():
    from committelemetry.pulse import process_push_message

    with patch('committelemetry.pulse.send_ping') as send_ping, \
         patch('committelemetry.pulse.payload_for_changeset'), \
         patch('committelemetry.pulse.changesets_for_pushid') as changesets_for_pushid:
        changesets_for_pushid.return_value = ['ab1cd2']

        process_push_message(test_message, MagicMock())

        send_ping.assert_called_once()


