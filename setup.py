# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup

setup(
    name='committelemetry',
    version='0.1',
    packages=['committelemetry'],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'dump-telemetry=committelemetry.tool:dump_telemetry',
            'process-queue-messages=committelemetry.tool:process_queue_messages',
        ]
    }
)
