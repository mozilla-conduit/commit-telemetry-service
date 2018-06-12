# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""Application configuration values pulled from the environment."""

import os

BMO_API_URL = os.environ.get('BMO_API_URL', 'https://bugzilla.mozilla.org/rest')

# For reading message from the Mozilla Pulse messaging service.
# See https://wiki.mozilla.org/Auto-tools/Projects/Pulse
PULSE_EXCHANGE = os.environ.get('PULSE_EXCHANGE', 'exchange/hgpushes/v2')
PULSE_QUEUE_NAME = os.environ['PULSE_QUEUE_NAME']
PULSE_QUEUE_ROUTING_KEY = os.environ['PULSE_QUEUE_ROUTING_KEY']

# For sending pings to the generic ping ingestion service.
# See https://docs.google.com/document/d/1PqiF1rF2fCk_kQuGSwGwildDf4Crg9MJTY44E6N5DSk
TMO_BASE_URL = os.environ.get(
    'TMO_BASE_URL', 'http://incoming.telemetry.mozilla.org/submit'
)
TMO_PING_NAMESPACE = os.environ['TMO_PING_NAMESPACE']
TMO_PING_DOCTYPE = os.environ['TMO_PING_DOCTYPE']
TMO_PING_DOCVERSION = os.environ['TMO_PING_DOCVERSION']
