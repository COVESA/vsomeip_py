"""
SPDX-FileCopyrightText: Copyright (c) 2023 Contributors to the
Eclipse Foundation

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
SPDX-FileType: SOURCE
SPDX-License-Identifier: Apache-2.0
"""

import multiprocessing
import threading
import time
from typing import Final
from test_base import *

TIMEOUT: Final[float] = 10


def _start_stop_process(index=0):
    services = []
    clients = []

    services.append(setup_service(99 + index))
    services.append(setup_service(99 - index))

    clients.append(setup_client(99 + index))

    for service in services:
        service.create()
    for client in clients:
        client.create()
    time.sleep(TIMEOUT)

    for service in services:
        service.start()
        service.offer()
    time.sleep(TIMEOUT)
    for client in clients:
        client.start()
        client.register()
    time.sleep(TIMEOUT)

    for client in clients:
        client.stop()
    for service in services[::-1]:  # feels good to stop service that launched router last
        service.stop()
    time.sleep(TIMEOUT)


class ClientTestCase(unittest.TestCase):

    def test_stop(self):
        for index in range(1, 20):
            print()
            print(f"cycle: {index}")
            print()

            SOMEIP.terminate()  # do first for bad restarts

            process = multiprocessing.Process(target=_start_stop_process, args=(index,))
            process.start()
            process.join()


