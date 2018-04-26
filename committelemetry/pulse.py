# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Functions for listening to the Mozilla Pulse service.

See https://wiki.mozilla.org/Auto-tools/Projects/Pulse
"""
import logging

from kombu import Connection, Exchange, Queue

from committelemetry.telemetry import payload_for_changeset, send_ping

log = logging.getLogger(__name__)


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

    msgtype = payload['type']
    if msgtype != 'changegroup.1':
        log.info(f'skipped message of type {msgtype}')
        message.ack()

    heads = payload['data']['heads']
    hcount = len(heads)
    if hcount != 1:
        log.info(
            f'skipped message with multiple heads (expected 1, got {hcount})'
        )
        message.ack()

    changeset = heads.pop()
    repo_url = payload['data']['repo_url']
    log.debug(f'message repo URL is {repo_url}')

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

    try:
        hgpush_exchange = Exchange(
            'exchange/hgpushes/v2', 'topic', channel=connection
        )  # TODO make exchange name configurable

        # Pulse queue names need to be prefixed with the username
        queue_name = f'queue/{username}/hgpush_commit_telemetry'  # TODO make queue name configurable
        queue = Queue(
            queue_name,
            exchange=hgpush_exchange,
            routing_key=
            'integration/mozilla-inbound',  # TODO make routing key configurable
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
    finally:
        connection.release()
