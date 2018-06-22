# Mozilla Commit Telemetry Service

A simple queue worker that produces Mozilla code repository telemetry.

The `bin/process-queue-messages` script reads messages about Mozilla source
code pushes from the [Mozilla
Pulse](https://wiki.mozilla.org/Auto-tools/Projects/Pulse) messaging service.
It adds some data about the code review system used by the commit author and
submits the data to [telemetry.mozilla.org](https://telemetry.mozilla.org/)
where we can build nifty dashboards.

----

## Setup

You will need to create an account on [Mozilla
Pulse](https://wiki.mozilla.org/Auto-tools/Projects/Pulse) to collect messages about hgpush events.

These programs were designed to run on Heroku and follow the [Heroku Architectural Principles](https://devcenter.heroku.com/articles/architecting-apps).  They read their settings from environment variables.

See the file [dotenv.example.txt](dotenv.example.txt) in the project root for possible values.  The values that must be present in your local and/or heroku execution
environments:

```console
$ cp dotenv.example.txt .env
$ vim .env
# Add your personal environment's configuration
```

Run the following command to check that everything works.  It won't send any data:

```console
$ PYTHONPATH=. bin/process-queue-messages --no-send
```

----

## Local Usage

```console
$ PYTHONPATH=. bin/process-queue-messages
```
Read all push messages from the hgpush event queue, figure out which review
system was used for each, and send the result to telemetry.mozilla.org.

Use `--help` for full command usage info.

Use `--debug` for full command debug output.

Use `--no-send` to gather all the data and build a payload, but do not
send any real pings.  All push event messages remain in queues, too. This is 
great for testing changes or diagnosing problems against a live queue.

```console
$ PYTHONPATH=. bin/dump-telemetry SOME_COMMIT_SHA1
```

Calculate and print the ping that would have been sent to telemetry.mozilla.org
for a given changeset ID.  This command does not send any data to
telemetry.mozilla.org.  Useful for debugging troublesome changesets and testing
service connectivity.

Use `--help` for full command usage info.

Use `--debug` for full command debug output.

```console
$ PYTHONPATH=. bin/backfill-pushlog REPO_URL STARTING_PUSHID ENDING_PUSHID
```

Read the Mercurial repository pushlog at REPO_URL, fetch all pushes from
STARTING_PUSHID to ENDING_PUSHID, then calculate and publish their
telemetry.  This can be used to back-fill pushes missed by service gaps. 

Use `--help` for full command usage info.

Use `--debug` for full command debug output.

Use `--no-send` to gather all the data and build a payload, but do not
send any real pings.


----

## Development

### Environment setup

Use [pyenv](https://github.com/pyenv/pyenv) to install the same python version 
listed in the project's [.python-version](.python-version) file: 

```console
$ pyenv install
```

Set up a virtual environment (e.g. with [pyenv virtualenv](https://github.com/pyenv/pyenv-virtualenv))
and install the project development dependencies:

```console
$ pip install -r requirements.txt -r dev-requirements.txt
```

### Hacking

Code formatting is done with [black](https://github.com/ambv/black).

`requirements.txt` and `dev-requirements.txt` are updated using [hashin](https://github.com/peterbe/hashin).

Push event messages are read from a Pulse message queue. You can inspect a live hgpush 
message queue with [Pulse Inspector](https://tools.taskcluster.net/pulse-inspector?bindings[0][exchange]=exchange%2Fhgpushes%2Fv2&bindings[0][routingKeyPattern]=%23).

Messages use the [hgpush message format](https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/notifications.html#changegroup-1).

Push events are generated from the [mercurial repo pushlogs](https://mozilla-version-control-tools.readthedocs.io/en/latest/hgmo/pushlog.html#writing-agents-that-consume-pushlog-data).

Pings (telemetry data) are sent to TMO using the [hgpush ping schema](https://github.com/mozilla-services/mozilla-pipeline-schemas/tree/dev/schemas/eng-workflow).
Make sure you match the schema or your pings will be dropped!

### Testing

#### Automated tests

The unit test suite can be run with [py.test](https://docs.pytest.org/en/latest/).

#### Manual tests

Manual testing can be done with:

```console
$ PYTHONPATH=. bin/dump-telemetry --debug  <SOME_CHANGESET_SHA>
```

and

```console
$ PYTHONPATH=. bin/process-queue-messages --no-send --debug
```

If you need a message queue with a lot of traffic for testing you may want to
listen for messages on `integration/mozilla-inbound`.  To switch the message 
queue set the following environment variables:

```shell
PULSE_QUEUE_NAME=hgpush-inbound-test-queue
PULSE_QUEUE_ROUTING_KEY=integration/mozilla-inbound
```

#### Testing ping schema changes

After deploying a schema change check these monitors:

* [Graph of all pings for the last 8 days (successes and failures)](https://pipeline-cep.prod.mozaws.net/dashboard_output/graphs/analysis.moz_generic_error_monitor.eng_workflow.html)
* [List of the last 10 ingested pings (both successful and rejected)](https://pipeline-cep.prod.mozaws.net/dashboard_output/analysis.moz_generic_eng_workflow_hgpush_1_pings.submissions.json)
* [Reason for the last 10 ping rejections](https://pipeline-cep.prod.mozaws.net/dashboard_output/analysis.moz_generic_eng_workflow_hgpush_1_pings.errors.txt)

You can also write custom monitors using hand-crafted [CEP dashboards](https://docs.telemetry.mozilla.org/cookbooks/view_pings_cep.html).

Ask in `#datapipeline` on IRC if you need help with this.

