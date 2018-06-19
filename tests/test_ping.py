# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Test ping construction for sending to telemetry.mozilla.org.
"""
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.usefixtures('null_config')


@pytest.mark.parametrize(
    "changeset_landingsystem,expected",
    [
        # case: the landingsystem JSON field is present and has a value
        ({"landingsystem": "lando"}, "lando"),
        # case: the landingsystem JSON field is present and is null
        ({"landingsystem": None}, None),
        # case: the landingsystem JSON field is missing
        ({}, None),
    ],
)
def test_extract_landingsystem(changeset_landingsystem, expected):
    from committelemetry.telemetry import payload_for_changeset

    with patch('committelemetry.telemetry.determine_review_system'), patch(
        'committelemetry.telemetry.fetch_changeset'
    ) as fetch_changeset:
        dummy_changeset = {'pushdate': (15278721560, 0)}
        dummy_changeset.update(changeset_landingsystem)
        fetch_changeset.return_value = dummy_changeset

        payload = payload_for_changeset('', '')

        assert payload['landingSystem'] == expected
