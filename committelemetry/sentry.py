# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
Sentry client instance.
"""

from raven import Client

client = Client(
    # DSN is automatically pulled from os.environ if present
    # dsn='https://<key>:<secret>@sentry.io/<project>',
    include_paths=[__name__.split('.', 1)[0]],
    # The release name should come from the HEROKU_SLUG_COMMIT environment var.
    # release=fetch_git_sha(os.path.dirname(__file__)),
    processors=('raven.processors.SanitizePasswordsProcessor', ),
)
