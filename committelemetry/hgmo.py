# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions for interacting with hg.mozilla.org APIs.
"""
import logging
from typing import Dict, List

from committelemetry.http import requests_retry_session
from committelemetry.sentry import client as sentry

log = logging.getLogger(__name__)


def changesets_for_pushid(pushid: int, push_json_url: str) -> List[str]:
    """Return a list of changeset IDs in a repository push.

    Reads data published by the Mozilla hgweb pushlog extension.

    Also see https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#writing-agents-that-consume-pushlog-data

    Args:
        pushid: The integer pushlog pushid we want information about.
        push_json_url: The 'push_json_url' field from a hgpush message.
            See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/notifications.html#changegroup-1
            The pushid in the URL should match the pushid argument to this
            function.

    Returns:
        A list of changeset ID strings (40 char hex strings).
    """
    log.info(f'processing pushid {pushid}')
    sentry.extra_context({'pushid': pushid})
    response = requests_retry_session().get(push_json_url)
    response.raise_for_status()

    # See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#version-2
    changesets = response.json()['pushes'][str(pushid)]['changesets']
    log.info(f'got {len(changesets)} changesets for pushid {pushid}')
    return changesets


def fetch_changeset(changesetid: str, repo_url: str) -> Dict:
    """Fetch changeset JSON from hg.mozilla.org.

    Raises:
        NoSuchChangeset if the changeset does not exist on hg.mozilla.org.
        requests.HTTPError for all other problems.
    """
    # Example URL: https://hg.mozilla.org/mozilla-central/json-rev/deafa2891c61
    response = requests_retry_session().get(f'{repo_url}/json-rev/{changesetid}')
    if response.status_code == 404:
        raise NoSuchChangeset(
            f'The changeset {changesetid} does not exist in repository {repo_url}'
        )
    response.raise_for_status()
    return response.json()


def fetch_raw_diff_for_changeset(changesetid: str, repo_url: str) -> str:
    """Fetch changeset raw 'hg export' patch text from hg.mozilla.org.

    Raises:
        NoSuchChangeset if the changeset does not exist on hg.mozilla.org.
        requests.HTTPError for all other problems.
    """
    # Example URL: https://hg.mozilla.org/mozilla-central/raw-rev/f0fe810b3d7863cdb
    response = requests_retry_session().get(f'{repo_url}/raw-rev/{changesetid}')
    if response.status_code == 404:
        raise NoSuchChangeset(
            f'The changeset {changesetid} does not exist in repository {repo_url}'
        )
    response.raise_for_status()
    return response.text



def utc_hgwebdate(hgweb_datejson):
    """Turn a (unixtime, offset) tuple back into a UTC Unix timestamp.

    Pushlog entries are not in UTC, but a tuple of (local-unixtime, utc-offset)
    created by
    https://www.mercurial-scm.org/repo/hg/file/8b86acc7aa64/mercurial/utils/dateutil.py#l63.
    This function reverses the operation that created the tuple.

    Args:
        hgweb_datejson: A 2-element JSON list of ints.
            For example: https://hg.mozilla.org/mozilla-central/json-rev/deafa2891c61
            See https://www.mercurial-scm.org/repo/hg/file/8b86acc7aa64/mercurial/utils/dateutil.py#l63
            for how this value is created.

    Returns:
        The UTC Unix time (seconds since the epoch), as an int.
    """
    assert len(hgweb_datejson) == 2
    timestamp, offset = hgweb_datejson
    return timestamp + offset


class Error(Exception):
    """Generic error class for this module."""


class NoSuchChangeset(Error):
    """Raised if the given changeset ID does not exist in the target system."""
