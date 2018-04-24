# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pprint
import sys

import click

from .telemetry import NoSuchChangeset, payload_for_changeset


@click.command()
@click.option(
    '--debug',
    envvar='DEBUG',
    is_flag=True,
    help='Print debugging messages about the script\'s progress.'
)
@click.option(
    '--target-repo',
    envvar='TARGET_REPO',
    metavar='URL',
    default='https://hg.mozilla.org/mozilla-central/',
    help='The URL of the repository where the given changeset can be found.'
)
@click.argument('node_id')
def dump_telemetry(debug, target_repo, node_id):
    """Dump the commit telemetry JSON for the given mercurial changeset ID."""
    if debug:
        print(f'Checking repo {target_repo}')

    try:
        ping = payload_for_changeset(node_id, target_repo)
    except NoSuchChangeset:
        print(
            f'Error: changeset {node_id} does not exist in repository {target_repo}'
        )
        sys.exit(1)

    pprint.pprint(ping)
