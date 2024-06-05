import time
from typing import Final
from someip_adapter.vsomeip import SOMEIP

APPLICATION_NAME: Final = 'super_cool_app_client'
APPLICATION_ID: Final = 0x0002

SERVICE_ID: Final = 0x000E
SERVICE_INSTANCE: Final = 0x0000
SERVICE_VERSION: Final = (0xFF, 0x00)
SERVICE_PORT: Final = 30509
CLIENT_IP: Final = "127.0.0.1"
CLIENT_MASK: Final = "255.255.248.0"
SERVICE_DISCOVERY_IP: Final = "224.244.224.245"
SERVICE_DISCOVERY_PORT: Final = 30490
SERVICE_DISCOVERY_ENABLE = 'true'

configuration = SOMEIP.configuration()  # template
# application
configuration["applications"].append({'name': APPLICATION_NAME, 'id': APPLICATION_ID})
configuration["clients"].append({'service': SERVICE_ID, 'instance': SERVICE_INSTANCE, "unreliable": [SERVICE_PORT]})
# host
configuration["unicast"] = CLIENT_IP
configuration["netmask"] = CLIENT_MASK
# multicasting
configuration["service-discovery"]["multicast"] = SERVICE_DISCOVERY_IP
configuration["service-discovery"]["port"] = SERVICE_DISCOVERY_PORT
configuration["service-discovery"]["enable"] = SERVICE_DISCOVERY_ENABLE


def callback(type: int, service: int, id: int, data: bytearray, request_id: int) -> bytearray:
    print(f"{hex(id)} -> {hex(type)}({hex(request_id)}) {hex(service)}, data: {data}")
    return data  # return data if want response to the request, else None


client = SOMEIP(APPLICATION_NAME, SERVICE_ID, SERVICE_INSTANCE, SERVICE_VERSION, configuration=configuration)
client.create()
client.on_event(0x8020, callback)
client.register()
client.start()

while True:
    client.request(0x001, data=bytearray(bytearray(b'hello somebody!')))
    time.sleep(3)
