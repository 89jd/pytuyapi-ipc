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
    def __init__(self, js_location = './', message_received_callback = None, debug = False):
        self.js_location = js_location
        self.node_rc, self.node_wc = os.pipe()
        self.py_rc, self.py_wc = os.pipe()
        self.wc_file = os.fdopen(self.node_wc, 'w')
        self.rc_file = os.fdopen(self.py_rc, 'r')
        self.message_received_callback = message_received_callback
        self.debug = debug

        os.set_inheritable(self.node_rc, True)
        os.set_inheritable(self.py_wc, True)

    async def read(self):
        loop = asyncio.get_running_loop()
        with self.rc_file as f:
            while not f.closed:
                future = loop.run_in_executor(None, self.rc_file.readline)
                data = await future
                self._on_message_received(data)
        if self.debug:
            print('Completed')

    async def read_loop(self, loop): 
        asyncio.set_event_loop(loop)
        await self.read()

    def _on_message_received(self, data):
        if self.debug:
            print('Python receive: ', data)
        ob = json.loads(data)

        if ob['type'] == 'disconnected': 
            self.rc_file.close()
            
        if self.message_received_callback:
            self.message_received_callback(json.loads(data))

    def start(self):
        loop = asyncio.get_event_loop()
        t = threading.Thread(target=asyncio.run, args=(self.read_loop(loop),))

        t.start()
        node_cmd = [get_js_executable_path(self.js_location), str('--fdr'), str(self.node_rc), str('--fdw'), str(self.py_wc)]
        if self.debug:
            node_cmd.append('--verbose')
        Popen(node_cmd, \
            stdout=sys.stdout, stderr=sys.stderr, close_fds=False)    

    def _send_message_to_tuya(self, t: str, data: str = None):
        message = {
            'type': t,
        }
        if data:
            message['data'] = data

        if self.debug:
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
    Popen(['npm', 'install', 'tuyapi-ipc'], \
            cwd=location ,stdout=sys.stdout, stderr=sys.stderr, close_fds=False) \
            .wait()

tuya = None

def main():
    init('./')
    try:
        global tuya
        tuya = TuyaNodeWrapper(message_received_callback=on_message_received, debug=True)
        tuya.start()
        tuya.connect_device(sys.argv[1], sys.argv[2], sys.argv[3])
    except:
        tuya.disconnect()

async def async_main():
    main()
    
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_main())
    