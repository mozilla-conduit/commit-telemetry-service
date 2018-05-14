# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions for listening to the Mozilla Pulse service.

See https://wiki.mozilla.org/Auto-tools/Projects/Pulse
"""
import logging
from contextlib import closing

import requests
from kombu import Connection, Exchange, Queue

from committelemetry import config
from committelemetry.telemetry import payload_for_changeset, send_ping

log = logging.getLogger(__name__)


def changesets_for_pushid(pushid, push_json_url):
    """Return a list of changeset IDs in a repository push.

    Reads data published by the Mozilla hgweb pushlog extension.

    Also see https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#writing-agents-that-consume-pushlog-data

    Args:
        pushid: The integer pushlog pushid we want information about.
        push_json_url: The 'push_json_url' field from a hgpush message.
            See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/notifications.html#changegroup-1
            The pushid in the URL should match the pushid argument to this
            function.

    Returns:
        A list of changeset ID strings (40 char hex strings).
    """
    log.info(f'processing pushid {pushid}')
    response = requests.get(push_json_url)
    response.raise_for_status()

    # See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#version-2
    changesets = response.json()['pushes'][str(pushid)]['changesets']
    log.info(f'got {len(changesets)} changesets for pushid {pushid}')
    return changesets


def process_push_message(body, message):
    """Process a hg push message from Mozilla Pulse.

    The message body structure is described by https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/notifications.html#common-properties-of-notifications

    Messages can be inspected by visiting https://tools.taskcluster.net/pulse-inspector?bindings[0][exchange]=exchange%2Fhgpushes%2Fv2&bindings[0][routingKeyPattern]=%23

    Args:
        body: The decoded JSON message body as a Python dict.
        message: A AMQP Message object.
    """
    log.debug(f'received message: {message}')

    payload = body['payload']
    log.debug(f'message payload: {payload}')

    msgtype = payload['type']
    if msgtype != 'changegroup.1':
        log.info(f'skipped message of type {msgtype}')
        message.ack()
        return

    pushlog_pushes = payload['data']['pushlog_pushes']
    # The count should always be 0 or 1.
    # See https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/notifications.html#changegroup-1
    pcount = len(pushlog_pushes)
    if pcount == 0:
        log.info(f'skipped message with zero pushes')
        message.ack()
        return
    elif pcount > 1:
        # Raise this as a warning to draw attention.  According to
        # https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/notifications.html#changegroup-1
        # this isn't supposed to happen, and we should contact the hgpush
        # service admin in #vcs on IRC.
        log.warning(
            f'skipped invalid message with multiple pushes (expected 0 or 1, got {pcount})'
        )
        message.ack()
        return

    pushdata = pushlog_pushes.pop()

    repo_url = payload['data']['repo_url']

    for changeset in changesets_for_pushid(
        pushdata['pushid'], pushdata['push_json_url']
    ):
        log.info(f'processing changeset {changeset}')
        ping = payload_for_changeset(changeset, repo_url)

        # Pings need a unique ID so they can be de-duplicated by the ingestion
        # service.  We can use the changeset ID for the unique key.
        send_ping(changeset, ping)

    message.ack()


def run_pulse_listener(username, password, timeout):
    """Run a Pulse message queue listener.

    This function does not return.
    """
    connection = Connection(
        hostname='pulse.mozilla.org',
        port=5671,
        ssl=True,
        userid=username,
        password=password,
    )

    # Connect and pass in our own low value for retries so the connection
    # fails fast if there is a problem.
    connection.ensure_connection(
        max_retries=1
    )  # Retries must be >=1 or it will retry forever.

    with closing(connection):
        hgpush_exchange = Exchange(
            config.PULSE_EXCHANGE, 'topic', channel=connection
        )

        # Pulse queue names need to be prefixed with the username
        queue_name = f'queue/{username}/{config.PULSE_QUEUE_NAME}'
        queue = Queue(
            queue_name,
            exchange=hgpush_exchange,
            routing_key=config.PULSE_QUEUE_ROUTING_KEY,
            durable=True,
            exclusive=False,
            auto_delete=False,
            channel=connection,
        )

        # Passing passive=True will assert that the exchange exists but won't
        #  try to declare it.  The Pulse server forbids declaring exchanges.
        hgpush_exchange.declare(passive=True)

        # Queue.declare() also declares the exchange, which isn't allowed by
        # the Pulse server. Use the low-level Queue API to only declare the
        # queue itself.
        queue.queue_declare()
        queue.queue_bind()

        # Pass auto_declare=False so that Consumer does not try to declare the
        # exchange.  Declaring exchanges is not allowed by the Pulse server.
        with connection.Consumer(
            queue, callbacks=[process_push_message], auto_declare=False
        ) as consumer:
            log.info('reading messages')
            connection.drain_events(timeout=timeout)
