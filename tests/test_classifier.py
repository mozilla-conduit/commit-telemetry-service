# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import copy
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.usefixtures('null_config')


################
#
#  Sample data
#
################

mozreview_attachment = {
    "attacher": "author@mozilla.com",
    "bug_id": 1447193,
    "content_type": "text/x-review-board-request",
    "creation_time": "2018-03-23T20:12:30Z",
    "creator": "author@mozilla.com",
    "description": "Bug 1447193 - Remove all displayport suppression logic from AsyncTabSwitcher.",
    "file_name": "reviewboard-230756-url.txt",
    "flags": [
        {
            "creation_date": "2018-03-28T21:33:02Z",
            "id": 1736449,
            "modification_date": "2018-03-28T22:20:23Z",
            "name": "review",
            "setter": "reviewer@mozilla.com",
            "status": "+",
            "type_id": 4,
        }
    ],
    "id": 8961928,
    "is_obsolete": 0,
    "is_patch": 0,
    "is_private": 0,
    "last_change_time": "2018-03-28T22:20:23Z",
    "size": 59,
    "summary": "Bug 1447193 - Remove all displayport suppression logic from AsyncTabSwitcher.",
}

phabricator_attachment = {
    "attacher": "author@mozilla.com",
    "bug_id": 1481097,
    "content_type": "text/x-phabricator-request",
    "creation_time": "2018-09-11T06:53:40Z",
    "creator": "author@mozilla.com",
    "description": "Bug 1481097 - vixl: Remove vixl assembler workaround for gcc 4.8.2 bug. r?sstangl",
    "file_name": "phabricator-D5506-url.txt",
    "flags": [],
    "id": 9007980,
    "is_obsolete": 0,
    "is_patch": 0,
    "is_private": 0,
    "last_change_time": "2018-09-11T06:53:40Z",
    "size": 46,
    "summary": "Bug 1481097 - vixl: Remove vixl assembler workaround for gcc 4.8.2 bug. r?sstangl",
}

bmo_patch_attachment = {
    "attacher": "author@mozilla.com",
    "bug_id": 1463962,
    "content_type": "text/plain",
    "creation_time": "2018-09-26T01:34:24Z",
    "creator": "author@mozilla.com",
    "description": "patch",
    "file_name": "patch",
    "flags": [
        {
            "creation_date": "2018-09-26T01:34:24Z",
            "id": 1810123,
            "modification_date": "2018-09-26T01:43:55Z",
            "name": "review",
            "setter": "reviewer@mozilla.com",
            "status": "+",
            "type_id": 4,
        }
    ],
    "id": 9012005,
    "is_obsolete": 0,
    "is_patch": 1,
    "is_private": 0,
    "last_change_time": "2018-09-26T01:43:55Z",
    "size": 1337,
    "summary": "patch",
}

revision_json = {
    "node": "445d1a7b050419f0ea266b0c191001d788f7850d",
    "date": [1537934817.0, -28800],
    "desc": "Bug 1463962 - crash near null in [@ mozilla::a11y::DocAccessible::BindToDocument], r=jamie",
    "backedoutby": "",
    "branch": "default",
    "bookmarks": [],
    "tags": [],
    "user": "Test User \u003cauthor@mozilla.com\u003e",
    "parents": ["83f4bc25eec8e4ff1b340d8a33e10baf62aa36d1"],
    "phase": "public",
    "pushid": 34713,
    "pushdate": [1537966541, 0],
    "pushuser": "pushuser@mozilla.com",
    "landingsystem": None,
}


patch_review_history = [
    {
        "changes": [
            {
                "added": "review+",
                "attachment_id": 9012005,
                "field_name": "flagtypes.name",
                "removed": "review?(jteh@mozilla.com)",
            }
        ],
        "when": "2018-09-26T01:43:55Z",
        "who": "jteh@mozilla.com",
    }
]


###########
#
#  Tests
#
###########


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("no bug - foo", True),
        ("bar baz - No bug, blah", True),
        ("bar baz - NO BUG", True),
        ("Bug 1234 - blah blah", False),
        ("Bug 1234 - No blah for bug", False),
    ],
)
def test_nobug_marker(test_input, expected):
    from committelemetry.classifier import has_no_bug_marker

    assert has_no_bug_marker(test_input) == expected


@pytest.mark.parametrize(
    "test_input,expected", [("foo", "foo"), ("foo\nbar\nbaz", "foo")]
)
def test_summary_splitting(test_input, expected):
    from committelemetry.classifier import split_summary

    assert split_summary(test_input) == expected


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("Bug 123 - [wpt PR 123] foo bar a=testonly", True),
        ("Bug 123 - [wpt PR 123] foo bar a=testonly extra", True),
        ("Bug 123 - [wpt PR 123]", False),
        ("Bug 123 - foo bar a=testonly", False),
    ],
)
def test_has_wpt_uplift_markers_in_summary(test_input, expected):
    from committelemetry.classifier import has_wpt_uplift_markers

    assert has_wpt_uplift_markers('', test_input) == expected


def test_has_wpt_uplift_markers_if_syncbot_is_author():
    from committelemetry.classifier import has_wpt_uplift_markers

    assert has_wpt_uplift_markers("moz-wptsync-bot <wptsync@mozilla.com>", "summary")
    assert not has_wpt_uplift_markers("someone <anon@mozilla.com>", "summary")


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("Bug 123 - foo bar a=testonly", True),
        ("Bug 123 - foo bar a=testonly extra", True),
        ("Bug 123 - foo bar a=multiple,somethings r=me", True),
        ("Bug 123 - foo bar a=merge", True),
        ("Bug 123 - r=testonly", False),
    ],
)
def test_has_uplift_markers(test_input, expected):
    from committelemetry.classifier import has_uplift_markers

    assert has_uplift_markers(test_input) == expected


def test_obsolete_attachments_are_filtered_out():
    from committelemetry.classifier import collect_review_attachments

    obsolete = copy.deepcopy(mozreview_attachment)
    obsolete["is_obsolete"] = 1
    active = copy.deepcopy(phabricator_attachment)
    active["is_obsolete"] = 0

    attachments = [obsolete, active]
    assert collect_review_attachments(attachments) == [active]


def test_mozreview_attachments_are_filtered_out():
    from committelemetry.classifier import collect_review_attachments

    mozreview = copy.deepcopy(mozreview_attachment)
    mozreview["is_obsolete"] = 0
    phabricator = copy.deepcopy(phabricator_attachment)
    phabricator["is_obsolete"] = 0

    attachments = [mozreview, phabricator]
    assert collect_review_attachments(attachments) == [phabricator]


def test_patch_attachments_are_kept():
    from committelemetry.classifier import collect_review_attachments

    phabricator = copy.deepcopy(phabricator_attachment)
    phabricator["is_obsolete"] = 0
    patch = copy.deepcopy(bmo_patch_attachment)
    patch["is_patch"] = 1
    patch["is_obsolete"] = 0

    attachments = [phabricator, patch]
    assert collect_review_attachments(attachments) == [phabricator, patch]


def test_phabricator_is_preferred_if_present():

    phab_attachment = copy.deepcopy(phabricator_attachment)
    phab_attachment["is_obsolete"] = 0
    patch_attachment = copy.deepcopy(bmo_patch_attachment)
    patch_attachment["is_patch"] = 1
    patch_attachment["is_obsolete"] = 0

    with patch(
        "committelemetry.classifier.fetch_attachments",
        return_value=[phab_attachment, patch_attachment],
    ), patch("committelemetry.classifier.fetch_bug_history"):
        from committelemetry.classifier import determine_review_system, ReviewSystem

        revision = copy.deepcopy(revision_json)
        assert determine_review_system(revision) is ReviewSystem.phabricator


def test_plain_old_patch_is_preferred_if_mozreview_present():

    mozrev_attachment = copy.deepcopy(mozreview_attachment)
    mozrev_attachment["is_obsolete"] = 0
    patch_attachment = copy.deepcopy(bmo_patch_attachment)
    patch_attachment["is_patch"] = 1
    patch_attachment["is_obsolete"] = 0

    with patch(
        "committelemetry.classifier.fetch_attachments",
        return_value=[mozrev_attachment, patch_attachment],
    ), patch(
        "committelemetry.classifier.fetch_bug_history",
        return_value=patch_review_history,
    ):
        from committelemetry.classifier import determine_review_system, ReviewSystem

        revision = copy.deepcopy(revision_json)
        assert determine_review_system(revision) is ReviewSystem.bmo
