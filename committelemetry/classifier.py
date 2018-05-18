# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions for determining the review system used for a mercurial changeset.
"""

import logging
import re
from enum import Enum

import requests
from mozautomation.commitparser import parse_bugs

from committelemetry import config
from committelemetry.http import requests_retry_session

log = logging.getLogger(__name__)

# Bugzilla attachment types
ATTACHMENT_TYPE_MOZREVIEW = 'text/x-review-board-request'
ATTACHMENT_TYPE_GITHUB = 'text/x-github-request'
ATTACHMENT_TYPE_PHABRICATOR = 'text/x-phabricator-request'

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
    url = f'{config.BMO_API_URL}/bug/{bug_id}/attachment?exclude_fields=data'
    response = requests_retry_session().get(url)

    # TODO Workaround for bug 1462349.  Can be removed when API calls return the correct value.
    if 'error' in response.json():
        response.status_code = 401

    response.raise_for_status()
    attachments = response.json()['bugs'][str(bug_id)]
    return attachments


def fetch_bug_history(bug_id):
    """Fetch the given bug's history from Bugzilla."""
    # Example: https://bugzilla.mozilla.org/rest/bug/1447193/history
    url = f'{config.BMO_API_URL}/bug/{bug_id}/history'
    response = requests_retry_session().get(url)

    # TODO Workaround for bug 1462349.  Can be removed when API calls return the correct value.
    if 'error' in response.json():
        response.status_code = 401

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
        # Take the first bug # found.  For Firefox commits this is usually at
        # the front of the string, like "Bug XXXXXX - fix the bar".  try to
        # avoid messages where there is a second ID in the message, like
        # 'Bug 1458766 [wpt PR 10812] - [LayoutNG] ...'.
        # NOTE: Bugs with the BMO bug # at the end will still get the wrong ID,
        # such as:
        # '[wpt PR 10812] blah blah (bug 1111111) r=foo'
        bug_id = parse_bugs(summary)[0]
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
