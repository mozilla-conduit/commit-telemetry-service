# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest


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
