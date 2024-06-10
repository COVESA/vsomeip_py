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

import time
from test_base import *


class ServiceTestCase(BaseTestCase):
    def test_configuration(self):
        self.assertTrue(self.service.configuration())

    def test_register(self):
        with self.assertRaises(UserWarning):
            self.service.register()

    def test_request(self):
        with self.assertRaises(UserWarning):
            self.service.request(self.method_id, data=self.data)

    def test_response(self):
        self.assertEqual(self.service.callback(SOMEIP.Message_Type.REQUEST.value, self.service._id, self.method_id, self.data, 0), self.data)

    def test_on_message(self):
        self.service.on_message(self.method_id)
        count = self.service.counter
        request_ids = []
        self.service.request_ids = []  # clear
        while True:
            request_ids.append(self.client.request(self.method_id, self.data))
            time.sleep(3)
            if self.service.counter > count:
                break
        self.assertTrue(self.service.counter > count)

        check = []
        tx_ids = request_ids
        rx_ids = self.service.request_ids
        for tx in tx_ids:
            check.append(True if tx in rx_ids else False)
        self.assertTrue(all(check))

    def test_on_event(self):
        for event_id in self.event_ids:
            self.service.on_event(event_id)

    def test_offer(self):
        self.service.offer(self.event_ids)
        # test can do again?
        self.service.offer(self.event_ids)

        for group_id in self.event_groups:
            self.service.offer(self.event_ids, group=group_id)

    def test_notify(self):
        event_id = self.event_ids[0]

        count = self.service.counter
        self.client.on_event(event_id)
        while True:
            self.service.notify(event_id, self.data)
            time.sleep(3)
            if self.client.counter > count:
                break


if __name__ == '__main__':
    unittest.main()
