# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""Application configuration values pulled from the environment."""

import os

BMO_API_URL = os.environ.get('BMO_API_URL', 'https://bugzilla.mozilla.org/rest')

PULSE_EXCHANGE = os.environ.get('PULSE_EXCHANGE', 'exchange/hgpushes/v2')
PULSE_QUEUE_NAME = os.environ['PULSE_QUEUE_NAME']
PULSE_QUEUE_ROUTING_KEY = os.environ['PULSE_QUEUE_ROUTING_KEY']