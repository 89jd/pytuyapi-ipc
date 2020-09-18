import base64
import json
import os
import sys
import asyncio
import threading

from typing import Any, Dict, List

from subprocess import Popen, PIPE
import time

def get_js_executable_path(location):
    return f'{location}/node_modules/.bin/tuyapi-ipc'

class TuyaNodeWrapper:
    def __init__(self, js_location = './', message_received_callback = None):
        self.js_location = js_location
        self.node_rc, self.node_wc = os.pipe()
        self.py_rc, self.py_wc = os.pipe()
        self.wc_file = os.fdopen(self.node_wc, 'w')
        self.rc_file = os.fdopen(self.py_rc, 'r')
        self.message_received_callback = message_received_callback
        os.set_inheritable(self.node_rc, True)
        os.set_inheritable(self.py_wc, True)

    async def read(self):
        loop = asyncio.get_running_loop()
        with self.rc_file as f:
            while not f.closed:
                future = loop.run_in_executor(None, self.rc_file.readline)
                data = await future
                self._on_message_received(data)
        print('Completed')

    def read_loop(self, loop): 
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.read())

    def _on_message_received(self, data):
        print('Python receive: ', data)
        ob = json.loads(data)

        if ob['type'] == 'disconnected': 
            self.rc_file.close()
            
        if self.message_received_callback:
            self.message_received_callback(json.loads(data))

    def start(self):
        loop = asyncio.get_event_loop()
        t = threading.Thread(target=self.read_loop, args=(loop,))

        t.start()

        Popen([get_js_executable_path(self.js_location), str(self.node_rc), str(self.py_wc)], \
            stdout=sys.stdout, stderr=sys.stderr, close_fds=False)    

    def _send_message_to_tuya(self, t: str, data: str = None):
        message = {
            'type': t,
        }
        if data:
            message['data'] = data

        print('Python send: ', message)

        self.wc_file.write(json.dumps(message))
        self.wc_file.write('\n')
        self.wc_file.flush()

    def connect_device(self, ip: int, device_id: int, key: int):
        self._send_message_to_tuya('connect', {'ip': ip, 'id': device_id, "key": key})
    
    def set_dps(self, dps: int, value: str):
        self._send_message_to_tuya('set', {'dps': dps, 'value': value})

    def disconnect(self):
        self._send_message_to_tuya("disconnect")
 

def on_message_received(message):
    if message['type'] == 'ready':
        tuya.disconnect()

def init(location):
    if not os.path.exists(get_js_executable_path(location)):
        Popen(['npm', 'install', 'tuyapi-ipc'], \
                cwd=location ,stdout=sys.stdout, stderr=sys.stderr, close_fds=False) \
                .wait()

if __name__ == '__main__':
    init('./')
    try:
        tuya = TuyaNodeWrapper(message_received_callback=on_message_received)
        tuya.start()
        tuya.connect_device(sys.argv[1], sys.argv[2], sys.argv[3])
    except:
        tuya.disconnect()