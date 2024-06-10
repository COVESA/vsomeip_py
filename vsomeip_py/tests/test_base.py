"""
SPDX-FileCopyrightText: Copyright (c) 2023 Contributors to COVESA

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

import unittest
from typing import Tuple, List
import tracemalloc
from vsomeip_py.vsomeip import vSOMEIP


class SOMEIP_Test(vSOMEIP):
    def __init__(self, name: str, id: int, instance: int, version: Tuple[int, int] = (0x00, 0x00), configuration: dict = {}):
        super().__init__(name, id, instance, version, configuration)
        self.counter = 0
        self.request_ids = []

    def callback(self, type: int, service: int, id: int, data: bytearray, request_id: int) -> bytearray:
        self.request_ids.append(request_id)
        self.counter = self.counter + 1
        return super().callback(type, service, id, data, request_id)


def setup_client(index: int = 0) -> SOMEIP_Test:
    configuration = vSOMEIP.configuration()

    client_name = "client_example" + f"_{index}"
    service_id = 0x1234 + index
    service_instance = 0x5678
    service_port = 30509 + index

    configuration["applications"].append({'name': client_name, 'id': 0x2222 + index})
    configuration["clients"].append({'service': service_id, 'instance': service_instance, 'unreliable': service_port})

    return SOMEIP_Test(client_name, service_id, service_instance, configuration=configuration)


def setup_service(index: int = 0) -> SOMEIP_Test:
    configuration = vSOMEIP.configuration()

    service_name = "service_example" + f"_{index}"
    service_id = 0x1234 + index
    service_instance = 0x5678
    service_port = 30509 + index

    configuration["applications"].append({'name': service_name, 'id': 0x1111 + index})
    configuration["services"].append({'service': service_id, 'instance': service_instance, 'unreliable': service_port})

    return SOMEIP_Test(service_name, service_id, service_instance, configuration=configuration)


class BaseTestCase(unittest.TestCase):
    client = None
    service = None
    service_extra = None

    data = bytearray([0x1, 0x2, 0x3])
    method_id = 0x9002
    event_ids = [0x8778]
    event_groups = [0x000A, 0x000B, 0x000C]

    @classmethod
    def setUpClass(cls):
        tracemalloc.start()

        cls.service = setup_service()
        cls.service_extra = setup_service(1)
        cls.client = setup_client()

        cls.service.create()
        cls.service_extra.create()
        cls.client.create()

        cls.service_extra.offer()
        cls.service_extra.start()

        cls.service.offer()
        cls.service.on_message(cls.method_id)
        cls.service.offer(events=cls.event_ids)
        cls.service.start()

        cls.client.start()
        cls.client.register()

    @classmethod
    def tearDownClass(cls):
        cls.service.stop()
        cls.client.stop()
