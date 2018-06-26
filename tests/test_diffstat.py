# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures('null_config')

from committelemetry import patch


def load_sample(filename: str) -> str:
    """Load a file of sample data.

    Returns the file contents as a string.
    """
    here = Path(__file__).parent
    sample = here / 'samples' / filename
    return sample.read_text()


@pytest.mark.parametrize(
    "samplefile, expected_files_changed, expected_additions, expected_deletions",
    [
        ('trivial-patch.txt', 1, 1, 1),
        ('large-patch.txt', 2, 19, 3),
        ('binary-patch.txt', 1, 0, 0),
        ('rename-file-patch.txt', 1, 0, 0),
        ('deleted-file-patch.txt', 1, 0, 1),
        ('plus-and-minus-chars-patch-body.txt', 1, 5, 5),
    ]
)
def test_patch_permutations(samplefile, expected_files_changed, expected_additions,
                            expected_deletions):
    patchtext = load_sample(samplefile)
    diffstat = patch.diffstat(patchtext)
    assert expected_files_changed == diffstat.files_changed
    assert expected_additions == diffstat.additions
    assert expected_deletions == diffstat.deletions
