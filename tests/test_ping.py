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
    "changeset_landingsystem, expected",
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
    ) as fetch_changeset, patch(
        'committelemetry.telemetry.diffstat_for_changeset'
    ), patch(
        'committelemetry.telemetry.fetch_raw_diff_for_changeset'
    ):
        dummy_changeset = {'pushdate': (15278721560, 0), 'parents': []}
        dummy_changeset.update(changeset_landingsystem)
        fetch_changeset.return_value = dummy_changeset

        payload = payload_for_changeset('', '')

        assert payload['landingSystem'] == expected


@pytest.mark.parametrize(
    "changeset_parents", [({"parents": []}), ({"parents": ["123abc"]})]
)
def test_diffstat_is_computed_for_non_merge_changesets(changeset_parents):
    from committelemetry.telemetry import payload_for_changeset

    with patch('committelemetry.telemetry.determine_review_system'), patch(
        'committelemetry.telemetry.fetch_changeset'
    ) as fetch_changeset, patch(
        'committelemetry.telemetry.fetch_raw_diff_for_changeset'
    ), patch(
        'committelemetry.telemetry.diffstat_for_changeset'
    ) as diffstat_for_changeset:

        dummy_changeset = {'pushdate': (15278721560, 0), 'parents': []}
        dummy_changeset.update(changeset_parents)
        fetch_changeset.return_value = dummy_changeset

        payload_for_changeset('', '')

        diffstat_for_changeset.assert_called_once()


def test_diffstat_is_not_computed_for_merges():
    from committelemetry.telemetry import payload_for_changeset

    with patch('committelemetry.telemetry.determine_review_system'), patch(
        'committelemetry.telemetry.fetch_changeset'
    ) as fetch_changeset, patch(
        'committelemetry.telemetry.diffstat_for_changeset'
    ) as diffstat_for_changeset:
        # Merge changesets have more than one parent.
        merge_changeset = {
            'pushdate': (15278721560, 0),
            'parents': ['123abc', '456def'],
        }
        fetch_changeset.return_value = merge_changeset

        payload = payload_for_changeset('', '')

        diffstat_for_changeset.assert_not_called()
        assert payload['diffstat'] is None


def test_diffstat_payload_is_computed():
    from committelemetry.telemetry import payload_for_changeset

    with patch('committelemetry.telemetry.determine_review_system'), patch(
        'committelemetry.telemetry.fetch_changeset'
    ) as fetch_changeset, patch(
        'committelemetry.telemetry.fetch_raw_diff_for_changeset'
    ) as fetch_raw_diff_for_changeset:
        dummy_changeset = {'pushdate': (15278721560, 0), 'parents': []}
        fetch_changeset.return_value = dummy_changeset

        patch_text = """
diff --git a/hello.txt b/hello.txt
--- a/hello.txt
+++ b/hello.txt
@@ -1,1 +1,1 @@
-hello world
+Hello World
"""
        fetch_raw_diff_for_changeset.return_value = patch_text

        payload = payload_for_changeset('', '')

        assert {'additions': 1, 'changedFiles': 1, 'deletions': 1} == payload[
            'diffstat'
        ]
