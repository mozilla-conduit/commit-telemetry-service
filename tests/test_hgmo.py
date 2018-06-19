# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Tests for the hg.mozilla.org API communication code.
"""
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures('null_config')


def test_successful_fetch_changeset():
    from committelemetry.hgmo import fetch_changeset

    with patch('committelemetry.hgmo.requests_retry_session') as requests:
        response = MagicMock()
        requests().get.return_value = response
        result = fetch_changeset('abcd', 'foo')

        requests().get.assert_called_once()
        assert result
