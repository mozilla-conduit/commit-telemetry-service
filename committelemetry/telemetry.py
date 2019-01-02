# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions for building and sending telemetry.mozilla.org pings.
"""

import logging
from typing import Dict

import requests

from committelemetry import config, patch
from committelemetry.classifier import ReviewSystem, determine_review_system
from committelemetry.hgmo import (
    fetch_changeset,
    fetch_raw_diff_for_changeset,
    utc_hgwebdate,
)

log = logging.getLogger(__name__)


def diffstat_for_changeset(patch_text: str) -> Dict:
    """Calculate and return a raw patch's diffstat as JSON."""
    diffstat = patch.diffstat(patch_text)
    return {
        'changedFiles': diffstat.files_changed,
        'additions': diffstat.additions,
        'deletions': diffstat.deletions,
    }


def payload_for_changeset(changesetid: str, repo_url: str) -> Dict:
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
    changeset = fetch_changeset(changesetid, repo_url)

    reviewsystem = determine_review_system(changeset)
    landingsystem = changeset.get('landingsystem')
    utc_pushdate = utc_hgwebdate(changeset['pushdate'])

    # Only compute diffstats for review systems we host.
    if reviewsystem in (ReviewSystem.phabricator, ReviewSystem.bmo):
        log.debug(f'changeset {changeset}: calculating diffstat')
        patch_text = fetch_raw_diff_for_changeset(changesetid, repo_url)
        diffstat = diffstat_for_changeset(patch_text)
    else:
        diffstat = None

    return {
        'changesetID': changesetid,
        'diffstat': diffstat,
        'landingSystem': landingsystem,
        'reviewSystemUsed': reviewsystem.value,
        'repository': repo_url,
        'pushDate': utc_pushdate,
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
