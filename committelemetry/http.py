# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions related to basic network communication tasks.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry


def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None
):
    """Return a python-requests Session that retries on HTTP failure.

    For usage see
    https://www.peterbe.com/plog/best-practice-with-retries-with-requests.

    Args:
        retries: optional int, number of retries to attempt.
        backoff_factor: See https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#module-urllib3.util.retry.
        status_forcelist: optional list of HTTP status codes that will trigger
            a retry.
        session: optional pre-built requests.Session object.

    Returns:
        A requests.Session object we can use to call .get(), post() etc.
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
