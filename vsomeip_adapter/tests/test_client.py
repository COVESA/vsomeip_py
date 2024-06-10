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


class ClientTestCase(BaseTestCase):
    def test_configuration(self):
        self.assertTrue(self.client.configuration())

    def test_register(self):
        self.client.register()

    def test_request(self):
        self.client.request(self.method_id, data=self.data)

    def test_response(self):
        self.assertEqual(self.client.callback(vSOMEIP.Message_Type.RESPONSE.value, self.client._id, self.method_id, self.data, 0), None)

    def test_on_message(self):
        self.client.on_message(self.method_id)

        count = self.client.counter
        request_ids = []
        self.client.request_ids = []  # clear
        while True:
            request_ids.append(self.client.request(self.method_id, self.data))
            time.sleep(3)
            if self.client.counter > count:
                break
        self.assertTrue(self.client.counter > count)

        check = []
        tx_ids = request_ids
        rx_ids = self.client.request_ids
        for tx in tx_ids:
            check.append(True if tx in rx_ids else False)
        self.assertTrue(all(check))

    def test_on_event(self):
        for event_id in self.event_ids:
            #self.client.on_event(event_id)
            for group_id in self.event_groups:
                self.client.on_event(event_id, group=group_id)

        count = self.client.counter + len(self.event_ids)
        while True:
            time.sleep(1)
            for event_id in self.event_ids:
                self.service.notify(event_id, self.data)
                time.sleep(3)
            if self.client.counter > count:
                break
        self.assertTrue(self.client.counter > count)

    def test_remove_event(self):
        self.test_on_event()

        for event_id in self.event_ids:
            #self.client.remove_event(event_id)
            for group_id in self.event_groups:
                self.client.remove(event_id, group=group_id)

        count = self.client.counter
        wait = 3
        while True:
            time.sleep(1)
            for event_id in self.event_ids:
                self.service.notify(event_id, self.data)
                time.sleep(3)
            wait = wait - 1
            if wait <= 0:
                break

        self.assertTrue(self.client.counter == count)  # no change

    @unittest.skip("Skipping as it indicates service verse client")
    def test_offer(self):
        self.client.offer(self.event_ids)

    def test_notify(self):
        for event_id in self.event_ids:
            with self.assertRaises(UserWarning):
                self.client.notify(event_id, self.data)


if __name__ == '__main__':
    unittest.main()
