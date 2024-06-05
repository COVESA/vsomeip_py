import time
import uuid
from threading import Thread
from someip_adapter.vsomeip import SOMEIP

SERVICE_ID_DEFAULT = 0x1234
SERVICE_INSTANCE_DEFAULT = 0x5678
SERVICE_PORT_DEFAULT = 30509


class service:
    def test(self, type: int, service: int, id: int, data: bytearray, request_id: int) -> bytearray:
        print(f"{hex(id)}, {hex(type)}({hex(request_id)}) ({self.service_name}({hex(service)}), {hex(self.service_port)}), data: {data}")
        if id == self.service_method:
            for event in self.service_events:
                self.someip.notify(event, data=bytearray(data))
        return None # no response

    def __init__(self, index: int = 0):
        configuration = SOMEIP.configuration()

        self.service_name = "service_example" + f"_{index}" + f"_{uuid.uuid4().hex.upper()[0:6]}"
        self.service_id = SERVICE_ID_DEFAULT + index
        self.service_instance = SERVICE_INSTANCE_DEFAULT
        self.service_port = SERVICE_PORT_DEFAULT + index

        configuration["applications"].append({'name': self.service_name, 'id': 0x1111 + index})
        configuration["services"].append({'service': self.service_id, 'instance': self.service_instance, 'unreliable': self.service_port})

        self.service_events = [0x8700 + index, 0x8800 + index, 0x8900 + index, 0x8600 + index] + [_ for _ in range(0x8000, 0x8100)]
        self.service_method = 0x9002

        self.someip = SOMEIP(self.service_name, self.service_id, self.service_instance, configuration=configuration)

    def activate(self):
        self.someip.create()
        self.someip.offer()
        self.someip.start()

        self.someip.on_message(self.service_method, callback=self.test)
        self.someip.offer(events=self.service_events)


class client:
    def test(self, type: int, service: int, id: int, data: bytearray, request_id: int) -> bytearray:
        print(f"{hex(id)}, {hex(type)}({hex(request_id)}) ({self.client_name}({hex(service)}), {hex(self.service_port)}), data: {data}")
        return None  # no response

    def __init__(self, index: int = 0, increment: int = 0):
        configuration = SOMEIP.configuration()

        self.client_name = "client_example" + f"_{increment}" + f"_{index}" + f"_{uuid.uuid4().hex.upper()[0:6]}"
        self.service_id = SERVICE_ID_DEFAULT + increment
        self.service_instance = SERVICE_INSTANCE_DEFAULT
        self.service_port = SERVICE_PORT_DEFAULT + increment

        configuration["applications"].append({'name': self.client_name, 'id': 0x2222 + index})
        configuration["clients"].append({'service': self.service_id, 'instance': self.service_instance}) #, 'unreliable': self.service_port})
        self.service_method = 0x9002
        self.service_events = [0x8700 + increment, 0x8800 + increment, 0x8900 + increment, 0x8600 + increment] + [_ for _ in range(0x8000, 0x8100)]  # 0x8XXX

        self.someip = SOMEIP(self.client_name, self.service_id, self.service_instance, configuration=configuration)

    def activate(self):
        self.someip.create()
        for service_event in self.service_events:
            self.someip.on_event(service_event, self.test)

        self.someip.register()
        self.someip.start()


if __name__ == '__main__':
    SOMEIP.terminate()
    time.sleep(1)

    instances = 3

    services = []
    clients = {}
    # create
    for x in range(0, instances):
        services.append(service(x))
        clients[x] = []
        for y in range(0, instances):
            clients[x].append(client(y, x))

    # start
    for instance in services:
        instance.activate()
    for _, value in clients.items():
        for instance in value:
            instance.activate()

    time.sleep(10)

    # interact
    while True:
        time.sleep(3)
        # first client for each service
        for key, _ in clients.items():
            clients[key][0].someip.request(clients[key][0].service_method, data=bytearray([65, 66, 67]))
