# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions for calculating commit telemetry and serializing the results.
"""
import logging
import re
from enum import Enum

from mozautomation.commitparser import parse_bugs
import requests

log = logging.getLogger(__name__)

# Bugzilla attachment types
ATTACHMENT_TYPE_MOZREVIEW = 'text/x-review-board-request'
ATTACHMENT_TYPE_GITHUB = 'text/x-github-request'
ATTACHMENT_TYPE_PHABRICATOR = 'text/x-phabricator-request'

# FIXME turn this into an environment variable
BMO_API_URL = 'https://bugzilla.mozilla.org/rest'

# Match "Differential Revision: https://phabricator.services.mozilla.com/D861"
PHABRICATOR_COMMIT_RE = re.compile(
    'Differential Revision: ([\w:/.]*)(D[0-9]{3,})'
)

# Match "Backed out 4 changesets (bug 1448077) for xpcshell failures at..."
BACKOUT_RE = re.compile('^back(ed|ing|) out ', re.IGNORECASE)


class ReviewSystem(Enum):
    """The review system used for a commit.

    Enum values are serialized for sending as telemetry.
    """
    phabricator = 'phabricator'
    mozreview = 'mozreview'
    bmo = 'bmo'
    unknown = 'unknown'
    not_applicable = 'not_applicable'


def is_patch(attachment):
    """Is the given BMO attachment JSON for a patch attachment?"""
    # Example: https://bugzilla.mozilla.org/rest/bug/1447193/attachment?exclude_fields=data
    return (
        attachment['is_patch'] == 1 or attachment['content_type'] in (
            ATTACHMENT_TYPE_MOZREVIEW,
            ATTACHMENT_TYPE_GITHUB,
            ATTACHMENT_TYPE_PHABRICATOR,
        )
    )


def fetch_attachments(bug_id):
    """Fetch the given bug's attachment list from Bugzilla."""
    # Example: https://bugzilla.mozilla.org/rest/bug/1447193/attachment?exclude_fields=data
    url = f'{BMO_API_URL}/bug/{bug_id}/attachment?exclude_fields=data'
    response = requests.get(url)
    response.raise_for_status()
    attachments = response.json()['bugs'][str(bug_id)]
    return attachments


def fetch_bug_history(bug_id):
    """Fetch the given bug's history from Bugzilla."""
    # Example: https://bugzilla.mozilla.org/rest/bug/1447193/history
    url = f'{BMO_API_URL}/bug/{bug_id}/history'
    response = requests.get(url)
    response.raise_for_status()
    history = response.json()['bugs'][0]['history']
    return history


def has_phab_markers(revision_description):
    """Does the given review description point to a Phabricator Revision?"""
    return bool(re.search(PHABRICATOR_COMMIT_RE, revision_description))


def has_backout_markers(revision_description):
    """Is the given revision description for a back-out request?"""
    return bool(re.search(BACKOUT_RE, revision_description))


def has_merge_markers(revision_json):
    """Is the given revision a merge?"""
    # If the node has more than one parent then it's a merge.
    return len(revision_json['parents']) > 1


def has_mozreview_markers(attachments):
    """Is there an attachment pointing to a MozReview review request?"""
    patches = [a for a in attachments if is_patch(a)]
    for patch_attachment in patches:
        if patch_attachment['content_type'] == ATTACHMENT_TYPE_MOZREVIEW:
            return True
    return False


def has_bmo_patch_review_markers(attachments, bug_history):
    """Is there an attachment pointing to a reviewed patch?
    """
    # 1. Does this bug have at least one patch attached?
    # Check for raw patches only, not x-phabricator-request or similar
    # patch attachments.
    patches = [a for a in attachments if a['is_patch'] == 1]
    if not patches:
        return False

    # 2. Does this bug have a review+ flag?
    # Don't balance review? and review+ changes, just assume that if there is
    # one review+ flag then a review was completed and the change landed.
    for change_group in bug_history:
        for change in change_group['changes']:
            if change['field_name'] != 'flagtypes.name':
                continue
            flags_added = change['added'].split(',')
            if 'review+' in flags_added:
                return True

    return False


def payload_for_changeset(changesetid, repo_url):
    """Build a telemetry.mozilla.org ping payload for the given changeset ID.

    The payload conforms to the 'commit-pipeline/mozilla-central-commit' schema.

    Args:
        changesetid: The 40 hex char changeset ID for the given repo.
        repo_url: The URL of the repo the changeset lives in.

    Returns:
        A dict that can be turned into JSON and posted to the
        telemetry.mozilla.org service.

    Raises:
        NoSuchChangeset: the requested changeset ID does not exist in the given
        mercurial repository.
    """
    # Example URL: https://hg.mozilla.org/mozilla-central/json-rev/deafa2891c61
    response = requests.get(f'{repo_url}/json-rev/{changesetid}')

    if response.status_code == 404:
        raise NoSuchChangeset(
            f'The changeset {changesetid} does not exist in repository {repo_url}'
        )

    response.raise_for_status()

    system = determine_review_system(response.json())

    return {'changesetID': changesetid, 'reviewSystemUsed': system.value}


def determine_review_system(revision_json):
    """Look for review system markers and guess which review system was used.

    Args:
        revision_json: A JSON structure for a specific changeset ID.  The
            structure is return by Mercurial's hgweb. For example:
            https://hg.mozilla.org/mozilla-central/json-rev/deafa2891c61

    Returns:
        A ReviewSystem enum value representing our guess about which review
        system was used, if any.
    """
    summary = revision_json['desc']
    changeset = revision_json['node']

    # 0. Check for changesets that don't need review.
    if has_backout_markers(summary) or has_merge_markers(revision_json):
        log.info(
            f'no review system for changeset {changeset}: changeset is a back-out or merge commit'
        )
        return ReviewSystem.not_applicable

    # 1. Check for Phabricator because it's easiest.
    # TODO can we rely on BMO attachments for this?
    if has_phab_markers(summary):
        return ReviewSystem.phabricator

    # TODO handle multiple bugs?
    try:
        bug_id = parse_bugs(summary).pop()
    except IndexError:
        log.info(
            f'could not determine review system for changeset {changeset}: unable to find a bug id in the changeset summary'
        )
        return ReviewSystem.unknown

    try:
        attachments = fetch_attachments(bug_id)
        bug_history = fetch_bug_history(bug_id)
    except requests.exceptions.HTTPError as err:
        log.info(
            f'could not determine review system for changeset {changeset} with bug {bug_id}: {err}'
        )
        return ReviewSystem.unknown

    # 2. Check BMO for MozReview review markers because that's next-easiest.
    if has_mozreview_markers(attachments):
        return ReviewSystem.mozreview

    # 3. Check for a review using just BMO attachments, e.g. splinter
    if has_bmo_patch_review_markers(attachments, bug_history):
        return ReviewSystem.bmo

    log.info(
        f'could not determine review system for changeset {changeset} with bug {bug_id}: the changeset is missing all known review system markers'
    )
    return ReviewSystem.unknown


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
    base_url = 'BASEURL'  # FIXME need a real service base URL
    namespace = 'eng-workflow'
    doctype = 'SOMEDOCTYPE'    # FIXME need a real doctype
    docversion = 'SOMEDOCVERSION'  # FIXME need a real doc version
    docid = ping_id
    url = f'{base_url}/{namespace}/{doctype}/{docversion}/{docid}'

    # TODO temporary until we have a real service endpoint to send to
    #response = requests.post(url, json=payload)
    #response.raise_for_status()


class Error(Exception):
    """Generic error class for this module."""


class NoSuchChangeset(Error):
    """Raised if the given changeset ID does not exist in the target system."""


# Test revs:
# Reviewed with BMO: deafa2891c61a4570bcadb80b90adac0930b1d10
# https://hg.mozilla.org/mozilla-central/rev/deafa2891c61

# Reviewed with Phabricator: e0cb209d9f3f307826944eae2d552b5a5bbe83e4
# https://hg.mozilla.org/mozilla-central/rev/e0cb209d9f3f

# Reviewed with MozReview: 2926745a0fee53547f6e464321cbe4915c2fff7f
# https://hg.mozilla.org/mozilla-central/rev/2926745a0fee

# Backed out single change
# https://hg.mozilla.org/mozilla-central/rev/b5065c61bbd7

# Backed out multiple revs
# https://hg.mozilla.org/mozilla-central/rev/daa5f1f165ed
