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

import os, sys
import json
import threading
import time
import importlib
import tempfile
from enum import Enum
from typing import Callable, List, Tuple, Final
import re
import socket
import atexit

is_windows = sys.platform.startswith('win')


class vSOMEIP:
    """
    Bindings for simple operations for service/client with
    vsomeip (<a href=https://github.com/COVESA/vsomeip>vsomip</a>)
    """

    ANY: Final[int] = 0xFFFF  # default (ALL), 'ANY_EVENT' (vsomeip\constants.hpp)
    module = importlib.import_module('vsomeip_ext')

    class Message_Type(Enum):
        REQUEST = 0x00
        NOTIFICATION = 0x02
        RESPONSE = 0x80
        UNKNOWN = 0xFF

    _configuration = {}  # global shared so routing service knows all the routes
    _lock = threading.Lock()
    _routing = None

    @staticmethod
    def _purge(pattern):
        # todo: smarter faster stronger better
        dir = os.path.join(tempfile.gettempdir())
        retry = 3
        flag = False
        for f in os.listdir(dir):
            if re.search(pattern, f):
                while True:
                    retry = retry - 1
                    try:
                        os.remove(os.path.join(dir, f))
                        flag = True
                    except Exception as ex:
                        time.sleep(1)
                        pass  # eat-it, Todo: not eat
                    if retry < 0:
                        break
        return flag

    def __init__(self, name: str, id: int, instance: int, version: Tuple[int, int] = (0x00, 0x00), configuration: dict = {}, force=False):
        """
        create instance
        :param name: application name
        :param id: service id
        :param instance: service instance
        :param version:
        :param configuration: json style dictionary of vsomeip configuration file.
        :param force: remove any OS locks
        """
        self._name = name
        self._id = id
        self._instance = instance
        self._is_service = None
        self._version = version

        with vSOMEIP._lock:  # protect while accessing external features
            if configuration:
                vSOMEIP._configuration = configuration
            else:
                vSOMEIP._configuration = self._configuration_template()

            if force or is_windows:
                # https://github.com/COVESA/vsomeip/issues/289, https://github.com/COVESA/vsomeip/issues/615
                self._purge("vsomeip*.lck")

            if vSOMEIP._configuration["services"]:  # if no services configured no router is needed!
                if not vSOMEIP._routing:
                    vSOMEIP._routing = self._name
                vSOMEIP._configuration['routing'] = vSOMEIP._routing

            # note: default configuration file if none given!!!
            with open('vsomeip.json', "w", newline='\n') as file_handle:
                json.dump(vSOMEIP._configuration, file_handle, sort_keys=True, indent=2)
                file_handle.flush()

        atexit.register(vSOMEIP.terminate)  # executed at interpreter termination

    @staticmethod
    def terminate():
        """ reload underlying c-api module(s) """
        # todo:  not there should be proper way to close service hosting routing daemon
        del vSOMEIP.module
        vSOMEIP.module = importlib.import_module('vsomeip_ext')
        time.sleep(0)  # yield

    def __del__(self):
        """ cleanup """
        try:
            self.stop()
        except OSError:
            pass  # eat-it, catch exception if not found

    @staticmethod
    def _configuration_template():
        """
        default configuration template
        :return: configuration
        """
        configuration = {}
        with open(os.path.join(os.path.realpath(os.path.dirname(__file__)), 'templates', 'vsomeip_template.json'),
                  "r") as handle:
            configuration = json.load(handle)

        configuration["unicast"] = '127.0.0.1'
        if is_windows:
            configuration["unicast"] = socket.gethostbyname(socket.gethostname())
        return configuration

    @staticmethod
    def configuration() -> dict:
        """
        reference of configuration used
        :return: configuration
        """
        if not vSOMEIP._configuration:
            vSOMEIP._configuration = vSOMEIP._configuration_template()
        return vSOMEIP._configuration

    def create(self):
        """
        create application
        """
        vSOMEIP.module.create(self._name, self._id, self._instance)

    def start(self):
        """
        start application
        """
        vSOMEIP.module.start(self._name, self._id, self._instance)

    def stop(self):
        """
        stop application
        """
        try:
            vSOMEIP.module.stop(self._name, self._id, self._instance)
        except SystemError:  # todo: why eating...
            pass

        with vSOMEIP._lock:
            if hasattr(self, '_name'):
                if vSOMEIP._routing == self._name:  # if we are the router remove
                    vSOMEIP._routing = None
                    vSOMEIP._configuration = self._configuration_template()  # clear!

    def register(self):
        """
        register to service offering
        :except: 'UserWarning'
        """
        if self._is_service:
            raise UserWarning("client registers, service offer")
        vSOMEIP.module.request_service(self._name, self._id, self._instance, self._version[0], self._version[1])

    def request(self, id: int, data: bytearray = None, is_tcp: bool = False) -> int:
        """
        request message
        :param id: message id
        :param data: message data
        :param is_tcp: else udp  # todo: determine from configuration (e.g. "reliable")
        :except: 'UserWarning'
        :return: request_id
        """
        if self._is_service:
            raise UserWarning("client requests, service responds")

        if data is None:
            data = bytearray([0x00])  # NULL
        request_id = vSOMEIP.module.send_service(self._name, self._id, self._instance, id, -1 if is_tcp else 0, data)
        return request_id

    def callback(self, type: int, service: int, instance: int, id: int, data: bytearray, request_id: int) -> bytearray:
        """
        :param type: enum Message_Type
        :param service:  service id
        :param instance: service instance id
        :param id: message id
        :param data: message data
        :param request_id:  client + session
        :return: message data
        :except: '
        """
        print(f"{type} -> service/id: [{hex(service)} - {hex(instance)}]/{hex(id)}, data: {data}")

        # todo:  handle action based on request message type
        if self._is_service:  # only service responds to request if it has data in this case
            return data  # this is the response
        return None

    def on_message(self, id: int, callback: Callable[[int, int, int, int, bytearray, int], bytearray] = None):
        """
        register for message
        :param id:  id
        :param callback: function for on message
        """
        if callback is None:
            callback = self.callback
        vSOMEIP.module.register_message(self._name, self._id, self._instance, id, callback)

    def on_event(self, id: int, callback: Callable[[int, int, int, int, bytearray, int], bytearray] = None, group: int = ANY):
        """
        register for event
        :param id: event id (ex: 0x8???)
        :param callback: function for on event
        :param group: define group, else default
        """
        if callback is None:
            callback = self.callback

        vSOMEIP.module.request_event_service(self._name, self._id, self._instance, id, group, self._version[0], self._version[1])
        self.on_message(id, callback)

    def on_availability(self, id: int ,instance: int ,callback: Callable[[int, int, bool], None] = None):
        """
        register for availability
        :param service:  service id
        :param instance: service instance id
        :param callback: function for on availability
        """
        if callback is None:
            raise UserWarning("please offer callback function")
            return None
        vSOMEIP.module.register_availability(self._name, id, instance, callback)

    def remove(self, id, group: int = ANY):
        """
        unregister for event
        :param id: event id (ex: 0x08??)
        :param group: define group, else default
        """
        vSOMEIP.module.unrequest_event_service(self._name, self._id, self._instance, id, group)

    def offer(self, events: List[int] = None, group: int = ANY):
        """
        service and event offerings
        :param events: if any events to offer
        :param group: define group, else default
        """
        self._is_service = True  # if offering something, then must be a service

        if events:
            for event in events:
                vSOMEIP.module.offer_event_service(self._name, self._id, self._instance, event, group)
        else:
            vSOMEIP.module.offer_service(self._name, self._id, self._instance, self._version[0], self._version[1])

    def notify(self, id: int, data: bytearray = None):
        """
        service event firing
        :param id:
        :param data:
        :except: 'UserWarning'
        """
        if not self._is_service:
            raise UserWarning("client consumes event")

        if data is None:
            data = bytearray([0x00])  # NULL, have to send something
        vSOMEIP.module.notify_clients(self._name, self._id, self._instance, id, data)
