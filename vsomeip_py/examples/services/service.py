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
from typing import Final
from vsomeip_py.vsomeip import vSOMEIP


APPLICATION_NAME: Final = 'super_cool_app_service'
APPLICATION_ID: Final = 0x0001

SERVICE_ID: Final = 0x000E
SERVICE_INSTANCE: Final = 0x0000
SERVICE_VERSION: Final = (0x01, 0x00)
SERVICE_PORT: Final = 30509
SERVICE_IP: Final = "127.0.0.1"
SERVICE_MASK: Final = "255.255.248.0"
SERVICE_DISCOVERY_IP: Final = "224.244.224.245"
SERVICE_DISCOVERY_PORT: Final = 30490

configuration = vSOMEIP.configuration()  # template
# application
configuration["applications"].append({'name': APPLICATION_NAME, 'id': APPLICATION_ID})
configuration["services"].append({'service': SERVICE_ID, 'instance': SERVICE_INSTANCE, 'unreliable': SERVICE_PORT})
# host
configuration["unicast"] = SERVICE_IP
configuration["netmask"] = SERVICE_MASK
# multicasting
configuration["service-discovery"]["multicast"] = SERVICE_DISCOVERY_IP
configuration["service-discovery"]["port"] = SERVICE_DISCOVERY_PORT


def callback(type: int, service: int, id: int, data: bytearray, request_id: int) -> bytearray:
    print(f"{hex(id)} -> {hex(type)}({hex(request_id)}) {hex(service)}, data: {data}")
    return data  # return data if want response to the request, else None


service = vSOMEIP(APPLICATION_NAME, SERVICE_ID, SERVICE_INSTANCE, SERVICE_VERSION, configuration=configuration)
service.create()
service.offer()
service.start()

service.on_message(0x01, callback=callback)
service.offer(events=[0x8020])

while True:
    service.notify(0x8020, data=bytearray(b'hello everybody!'))
    time.sleep(3)
