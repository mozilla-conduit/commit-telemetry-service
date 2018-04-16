# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from flask import Flask, render_template, request
from flask.json import dumps

from committelemetry import telemetry

# FIXME turn this into an environment variable
TARGET_REPO = 'https://hg.mozilla.org/mozilla-central/'

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/', methods=['POST'])
def index_post():
    # TODO: validate changeset input format
    ping = telemetry.payload_for_changeset(
        request.form['changesetid'], TARGET_REPO
    )
    return render_template(
        'index.html', ping_body=dumps(ping), repo=TARGET_REPO
    )


if __name__ == '__main__':
    app.run()
