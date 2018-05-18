# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions for building and sending telemetry.mozilla.org pings.
"""

import logging

import requests

from committelemetry import config
from committelemetry.classifier import determine_review_system
from committelemetry.http import requests_retry_session

log = logging.getLogger(__name__)


def payload_for_changeset(changesetid, repo_url):
    """Build a telemetry.mozilla.org ping payload for the given changeset ID.

    The payload conforms to https://github.com/mozilla-services/mozilla-pipeline-schemas/blob/dev/schemas/eng-workflow/hgpush/hgpush.1.schema.json

    Args:
        changesetid: The 40 hex char changeset ID for the given repo.
        repo_url: The URL of the repo the changeset lives in.

    Returns:
        A dict that can be turned into JSON and posted to the
        telemetry.mozilla.org service.  See https://github.com/mozilla-services/mozilla-pipeline-schemas/blob/dev/schemas/eng-workflow/hgpush/hgpush.1.schema.json

    Raises:
        NoSuchChangeset: the requested changeset ID does not exist in the given
        mercurial repository.
    """
    # Example URL: https://hg.mozilla.org/mozilla-central/json-rev/deafa2891c61
    response = requests_retry_session(
    ).get(f'{repo_url}/json-rev/{changesetid}')

    if response.status_code == 404:
        raise NoSuchChangeset(
            f'The changeset {changesetid} does not exist in repository {repo_url}'
        )

    response.raise_for_status()
    pushdata = response.json()

    system = determine_review_system(pushdata)

    utc_pushdate = utc_hgwebdate(pushdata['pushdate'])

    return {
        'changesetID': changesetid,
        'reviewSystemUsed': system.value,
        'repository': repo_url,
        'pushDate': utc_pushdate
    }


def send_ping(ping_id, payload):
    """Send an event ping to the Mozilla telemetry service.

    See http://docs.telemetry.mozilla.org for details.

    Args:
        ping_id: A unique ID string for this ping event. Used for event
            de-duplication by the telemetry ingestion service.
        payload: A JSON-serializable Python dict that will be sent as the
            ping event payload.
    """
    log.info(f'sending ping: {payload}')

    # We will send pings to the generic ping ingestion service.
    # See https://docs.google.com/document/d/1PqiF1rF2fCk_kQuGSwGwildDf4Crg9MJTY44E6N5DSk
    base_url = config.TMO_BASE_URL
    namespace = config.TMO_PING_NAMESPACE
    doctype = config.TMO_PING_DOCTYPE
    docversion = config.TMO_PING_DOCVERSION
    docid = ping_id
    url = f'{base_url}/{namespace}/{doctype}/{docversion}/{docid}'

    response = requests.put(url, json=payload)
    response.raise_for_status()


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
