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
from committelemetry.sentry import client as sentry

log = logging.getLogger(__name__)

# Bugzilla attachment types
ATTACHMENT_TYPE_MOZREVIEW = 'text/x-review-board-request'
ATTACHMENT_TYPE_GITHUB = 'text/x-github-request'
ATTACHMENT_TYPE_PHABRICATOR = 'text/x-phabricator-request'

# Match "Differential Revision: https://phabricator.services.mozilla.com/D861"
PHABRICATOR_COMMIT_RE = re.compile(r'Differential Revision: ([\w:/.]*)(D[0-9]{3,})')

# Match "Backed out 4 changesets (bug 1448077) for xpcshell failures at..."
BACKOUT_RE = re.compile(r'^back(ed|ing|) out ', re.IGNORECASE)

# Match 'no bug' anywhere in the commit message summary
NOBUG_RE = re.compile(r'\bno bug\b', re.IGNORECASE)

# Match 'a=foo,bar' flags in the commit message summary
UPLIFT_RE = re.compile(r'\ba=\w+\b', re.IGNORECASE)

# Match '[wpt PR 1234] - summary a=testonly'
WPT_SYNC_BOT_RE = re.compile(r'\[wpt PR \d+\](.*) a=testonly')


class ReviewSystem(Enum):
    """The review system used for a commit.

    Enum values are serialized for sending as telemetry.

    Attributes:
        phabricator Indicates the commit was reviewed with Phabricator.
        mozreview: Indicates the commit was reviewed with MozReview.
        bmo: Indicates the commit was reviewed in bugzilla.mozilla.org.
        no_bug: Indicates that the process to determine the review system had to
            stop because the commit summary clearly stated 'no bug' or access to
            the bug in the commit summary was denied.
        review_unneeded: For commits that do not need review, like back-outs,
            uplifts on a closed tree, or commits flagged with a=testonly.
        unknown: Indicates that the commit data and bug data have no markers
            that we know of to determine how (or if) the commit was reviewed.
        not_applicable: Indicates the commit was a merge, etc.
    """

    phabricator = 'phabricator'
    mozreview = 'mozreview'
    bmo = 'bmo'
    no_bug = 'no_bug'
    review_unneeded = 'review_unneeded'
    unknown = 'unknown'
    not_applicable = 'not_applicable'


def is_patch(attachment):
    """Is the given BMO attachment JSON for a patch attachment?"""
    # Example: https://bugzilla.mozilla.org/rest/bug/1447193/attachment?exclude_fields=data
    return attachment['is_patch'] == 1 or attachment['content_type'] in (
        ATTACHMENT_TYPE_MOZREVIEW,
        ATTACHMENT_TYPE_GITHUB,
        ATTACHMENT_TYPE_PHABRICATOR,
    )


def fetch_attachments(bug_id):
    """Fetch the given bug's attachment list from Bugzilla."""
    # Example: https://bugzilla.mozilla.org/rest/bug/1447193/attachment?exclude_fields=data
    url = f'{config.BMO_API_URL}/bug/{bug_id}/attachment?exclude_fields=data'
    response = requests_retry_session().get(url)

    # TODO Workaround for bug 1462349.  Can be removed when API calls return the correct value.
    if 'error' in response.json():
        response.status_code = 401

    if response.status_code == 401:
        raise NotAuthorized()

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

    if response.status_code == 401:
        raise NotAuthorized()

    response.raise_for_status()
    history = response.json()['bugs'][0]['history']
    return history


def collect_review_attachments(attachments):
    """Collect review-related attachments from a BMO bug attachment list.

    Only active attachments (attachments where "is_obsolete" == 0) are kept.

    MozReview attachments are not returned because MozReview has been decommissioned.

    Args:
        attachments: A list of JSON attachment dict objects.

    Returns:
        A list of JSON attachment dictionaries for attachments related to code review
        systems.
    """
    return [
        a
        for a in attachments
        if a["is_obsolete"] == 0
        and (
            a["content_type"] in (ATTACHMENT_TYPE_GITHUB, ATTACHMENT_TYPE_PHABRICATOR)
            or a["is_patch"] == 1
        )
    ]


def has_phab_markers(attachments):
    """Does the given review description point to a Phabricator Revision?"""
    patches = [a for a in attachments if is_patch(a)]
    for patch_attachment in patches:
        if patch_attachment['content_type'] == ATTACHMENT_TYPE_PHABRICATOR:
            return True
    return False


def has_backout_markers(revision_description):
    """Is the given revision description for a back-out request?"""
    return bool(re.search(BACKOUT_RE, revision_description))


def has_merge_markers(revision_json):
    """Is the given revision a merge?"""
    # If the node has more than one parent then it's a merge.
    return len(revision_json['parents']) > 1


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


def has_no_bug_marker(summary: str) -> bool:
    """Does the commit summary explicitly say 'no bug'?"""
    return bool(re.search(NOBUG_RE, summary))


def has_uplift_markers(summary: str) -> bool:
    """Is the commit flagged as an uplift with a=...?"""
    uplift_flags = re.search(UPLIFT_RE, summary)
    log.debug(f'matching uplift flags: {uplift_flags}')
    return bool(uplift_flags)


def has_wpt_uplift_markers(commit_author: str, summary: str) -> bool:
    """Was this commit by the Web Platform Test Sync Bot?

    See https://hg.mozilla.org/mozilla-central/rev/e2dced9fda47999677b840a58f5e39b2217881e8
    for an example commit.
    """
    return bool(re.search(WPT_SYNC_BOT_RE, summary)) or (
        commit_author == "moz-wptsync-bot <wptsync@mozilla.com>"
    )


def split_summary(s: str) -> str:
    """Split a commit message summary from the long-form description.

    For a commit message with a summary line of 'bug 1234 - foo', followed
    by a blank line and a longer commit description body, this function will
    return just the summary line.
    """
    return s.splitlines()[0]


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
    fulldesc = revision_json['desc']
    summary = split_summary(fulldesc)
    changeset = revision_json['node']
    author = revision_json['user']

    # Check for changesets that don't need review.
    if has_backout_markers(summary):
        log.info(f'changeset {changeset}: changeset is a back-out commit')
        return ReviewSystem.review_unneeded
    elif has_merge_markers(revision_json):
        log.info(f'changeset {changeset}: is a merge commit')
        return ReviewSystem.not_applicable
    elif has_no_bug_marker(summary):
        log.info(f'changeset {changeset}: summary is marked "no bug"')
        return ReviewSystem.no_bug
    elif has_uplift_markers(summary):
        log.info(f'changeset {changeset}: summary is marked uplift')
        return ReviewSystem.review_unneeded
    elif has_wpt_uplift_markers(author, summary):
        log.info(f'changeset {changeset}: changeset was requested by moz-wptsync-bot')
        return ReviewSystem.review_unneeded

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
        log.debug(f'changeset {changeset}: parsed bug ID {bug_id}')
    except IndexError:
        log.info(
            f'could not determine review system for changeset {changeset}: unable to '
            f'find a bug id in the changeset summary'
        )
        sentry.captureMessage(
            "could not determine review system for changeset", level=logging.INFO
        )
        return ReviewSystem.unknown

    try:
        attachments = fetch_attachments(bug_id)
        bug_history = fetch_bug_history(bug_id)
    except NotAuthorized:
        log.info(f'changeset {changeset}: not authorized to view bug {bug_id}')
        # For reporting purposes explicitly lump commits with confidential
        # bugs in with commits that have a 'no bug - do stuff' summary line.
        return ReviewSystem.no_bug
    except requests.exceptions.HTTPError as err:
        log.info(
            f'could not determine review system for changeset {changeset} with bug '
            f'{bug_id}: {err}'
        )
        sentry.captureMessage(
            "could not determine review system for changeset", level=logging.INFO
        )
        return ReviewSystem.unknown

    review_attachments = collect_review_attachments(attachments)

    if has_phab_markers(review_attachments):
        return ReviewSystem.phabricator

    # Check for a review using just BMO attachments, e.g. splinter
    if has_bmo_patch_review_markers(review_attachments, bug_history):
        return ReviewSystem.bmo

    log.info(
        f'could not determine review system for changeset {changeset} with bug '
        f'{bug_id}: the changeset is missing all known review system markers'
    )
    sentry.captureMessage(
        "could not determine review system for changeset", level=logging.INFO
    )
    return ReviewSystem.unknown


class Error(Exception):
    """Generic error"""


class NotAuthorized(Error):
    """We are not authorized to view this HTTP resource"""


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
