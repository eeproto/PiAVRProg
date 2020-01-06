# -*- coding: utf-8 -*-

"""
This file is part of the PiAVRProg project
 https://github.com/eeproto/PiAVRProg

This work is licensed under a Creative Commons Attribution-ShareAlike 4.0
 International License http://creativecommons.org/licenses/by-sa/4.0/

Copyright (c) 2019 EE Proto LLC https://www.eeproto.com

Author: christian@eeproto.com
"""

# based on https://raspberrypi.stackexchange.com/users/8996/larsks
# at https://raspberrypi.stackexchange.com/a/76738

import RPi.GPIO as GPIO
import threading


class ButtonHandler(threading.Thread):
    def __init__(self, pin, func, edge='both', bouncetime=200):
        super().__init__(daemon=True)

        self.edge = edge
        self.func = func
        self.pin = pin
        self.bouncetime = float(bouncetime) / 1000

        self.lastpinval = GPIO.input(self.pin)
        self.lock = threading.Lock()

    def __call__(self, *args):
        if not self.lock.acquire(blocking=False):
            return
        self.lastpinval = GPIO.input(self.pin)
        t = threading.Timer(self.bouncetime, self.read, args=args)
        t.start()
        #print("timer started")

    def read(self, *args):
        pinval = GPIO.input(self.pin)

        #print("read", self.edge, pinval, self.lastpinval)
        if (
                ((pinval == 0 and self.lastpinval == 0) and
                 (self.edge in ['falling', 'both'])) or
                ((pinval == 1 and self.lastpinval == 1) and
                 (self.edge in ['rising', 'both']))
        ):
            #print("calling")
            self.func(*args)

        self.lastpinval = pinval
        self.lock.release()


class Button(object):

    def __init__(self, pin, callback, bouncetime=100):
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        cb = ButtonHandler(pin, callback, edge='rising', bouncetime=bouncetime)
        cb.start()
        GPIO.add_event_detect(pin, GPIO.RISING, callback=cb)
