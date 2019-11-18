# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions related to processing mercurial pushlog messsages.

See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#writing-agents-that-consume-pushlog-data
"""
import logging

from committelemetry.http import requests_retry_session
from committelemetry.telemetry import payload_for_changeset, send_ping

log = logging.getLogger(__name__)


def pushes_for_range(repo_url, starting_push_id, ending_push_id):
    """Fetch a dict of pushes by ID from a repo pushlog.

    Args:
        repo_url: The full URL of the repo whose pushlog we want to process.
        starting_push_id: Integer. Process all pushes greater than this push id.
        ending_push_id: Integer.  Process all pushes less than and including
            this push id.

    Returns:
        A dict of {'pushid': {pushdata}}.  See
        https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#version-2.
    """
    # See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#version-2
    params = dict(startID=starting_push_id, endID=ending_push_id, version=2)
    response = requests_retry_session().get(f'{repo_url}/json-pushes/', params=params)
    response.raise_for_status()
    pushlog = response.json()
    return pushlog['pushes']


def send_pings_by_pushid(repo_url, starting_push_id, ending_push_id, no_send):
    """Fetch repo pushes by pushid and send pings for them.

    Args:
        repo_url: The full URL of the repo whose pushlog we want to process.
        starting_push_id: Integer. Process all pushes greater than this push id.
        ending_push_id: Integer.  Process all pushes less than and including
            this push id.
        no_send: Boolean: don't send any ping data, just print a message.
    """
    if no_send:
        log.info('transmission of ping data has been disabled')

    for pushid, pushdata in pushes_for_range(
        repo_url, starting_push_id, ending_push_id
    ).items():
        log.info(f'processing pushid {pushid}')

        # See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#version-2
        changesets = pushdata['changesets']
        log.info(f'got {len(changesets)} changesets for pushid {pushid}')

        for changeset in changesets:
            log.info(f'processing changeset {changeset}')
            ping = payload_for_changeset(changeset, repo_url)

            if no_send:
                log.info(f'ping data (not sent): {ping}')
                continue

            # Pings need a UUID so they can be de-duplicated by the ingestion
            # service.  We construct a UUID here from the first 32 characters
            # of the changeset hash.
            ping_id = str(uuid.UUID(changeset[:32]))
            send_ping(ping_id, ping)
