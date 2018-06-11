# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import logging
import pprint
import sys

import click

from committelemetry.pulse import run_pulse_listener
from committelemetry.pushlog import send_pings_by_pushid
from .telemetry import payload_for_changeset
from committelemetry.hgmo import NoSuchChangeset


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
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    try:
        ping = payload_for_changeset(node_id, target_repo)
    except NoSuchChangeset:
        print(
            f'Error: changeset {node_id} does not exist in repository {target_repo}'
        )
        sys.exit(1)

    pprint.pprint(ping)


@click.command()
@click.option(
    '--debug',
    envvar='DEBUG',
    is_flag=True,
    help='Print debugging messages about the script\'s progress.'
)
@click.option(
    '--user',
    envvar='PULSE_USERNAME',
    help='The Pulse queue username to connect with.'
)
@click.option(
    '--password',
    prompt=True,
    hide_input=True,
    envvar='PULSE_PASSWORD',
    help='The Pulse queue user\'s password.'
)
@click.option(
    '--timeout',
    default=1.0,
    help='Timeout, in seconds, to wait for additional queue messages.'
)
@click.option(
    '--no-send',
    is_flag=True,
    help='For testing. Do not send ping data or drain any queues.'
)
def process_queue_messages(debug, user, password, timeout, no_send):
    """Process all queued mercurial repo change messages."""
    # Importing the Sentry client will automatically configure it and install
    # it as the process-wide sys.excepthook handler.

    if debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(stream=sys.stdout, level=log_level)

    run_pulse_listener(user, password, timeout, no_send)


@click.command()
@click.option(
    '--debug',
    envvar='DEBUG',
    is_flag=True,
    help='Print debugging messages about the script\'s progress.'
)
@click.option(
    '--no-send',
    is_flag=True,
    help='For testing. Do not send ping data or drain any queues.'
)
@click.argument('repo_url')
@click.argument('starting_push_id')
@click.argument('ending_push_id')
def backfill_pushlog(
    debug, no_send, repo_url, starting_push_id, ending_push_id
):
    """Process repo pushes by pushlog ID."""
    if debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(stream=sys.stdout, level=log_level)

    print(f'Checking repo {repo_url}')
    print(f'Fetching pushes {starting_push_id} to {ending_push_id}')

    send_pings_by_pushid(repo_url, starting_push_id, ending_push_id, no_send)

    print('Done.')
