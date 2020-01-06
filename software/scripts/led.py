# -*- coding: utf-8 -*-

"""
This file is part of the PiAVRProg project
 https://github.com/eeproto/PiAVRProg

This work is licensed under a Creative Commons Attribution-ShareAlike 4.0
 International License http://creativecommons.org/licenses/by-sa/4.0/

Copyright (c) 2019 EE Proto LLC https://www.eeproto.com

Author: christian@eeproto.com
"""

import RPi.GPIO as GPIO
import threading
import time


class LED(object):

    def __init__(self, pin):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.pin = pin
        GPIO.setup(self.pin, GPIO.OUT)
        self._is_flashing = None
        self._flashing_thread = None
        self._flashing_on_ms = 0
        self._flashing_off_ms = 0
        self.off()

    def on(self):
        self._is_flashing = None
        GPIO.output(self.pin, GPIO.HIGH)

    def off(self):
        self._is_flashing = None
        GPIO.output(self.pin, GPIO.LOW)

    def set(self, onoff):
        if onoff:
            self.on()
        else:
            self.off()

    def _flash_toggle(self):
        while self._is_flashing is not None:
            if self._is_flashing == 1:
                GPIO.output(self.pin, GPIO.HIGH)
                self._is_flashing = 0
                time.sleep(self._flashing_on_ms/1000)
            else:
                GPIO.output(self.pin, GPIO.LOW)
                self._is_flashing = 1
                time.sleep(self._flashing_off_ms/1000)



    def blink(self, on_ms, off_ms):
        self._flashing_on_ms = on_ms
        self._flashing_off_ms = off_ms
        if (self._flashing_thread is None or
                not self._flashing_thread.is_alive()):
            self._flashing_thread = threading.Thread(
                      target = self._flash_toggle)
            self._is_flashing = 1
            self._flashing_thread.start()
