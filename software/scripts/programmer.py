#!/usr/bin/env python
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
import time
import json
import os
import logging
import traceback
import signal
import sys

import led
import button
import avrdude

DEVICE_FILE_PATH = '/media/usb/device.json'
FLASH_FILE_PATH = '/media/usb/firmware.hex'
DEVICE_KEYS = ['H', 'L', 'E', 'type']
SPI_DEVICE = '/dev/spidev0.0'
PROGRAMMER = 'linuxspi'
BAUDRATE_SLOW = '19200'
BITRATE_SLOW = '10'
BAUDRATE_FAST = '200000'
BITCLOCK_FAST = '1'
LOG_LEVEL = logging.INFO
VERSION = '0.2'


class PiProgrammer(object):

    def __init__(self):
        self.init_gpio()
        self.leds = {}
        self.led_ready = led.LED(6)
        self.leds['programming'] = led.LED(22)
        self.leds['flash_pass'] = led.LED(17)
        self.leds['flash_fail'] = led.LED(18)
        self.leds['fuse_pass'] = led.LED(23)
        self.leds['fuse_fail'] = led.LED(24)
        self.buffer_switch = led.LED(5)
        self.go_button = button.Button(27, self.button_pressed)
        self.clear_leds()
        self._alive = True

    def init_gpio(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

    def led_cycle(self, *args):
        l = list(self.leds.keys())
        l.sort()
        self.leds[l[self.x]].off()
        self.x = (self.x + 1) % len(self.leds)
        self.leds[l[self.x]].on()

    def clear_leds(self):
        for l in self.leds.values():
            l.off()
        self.led_ready.off()

    def load_firmware(self):
        device = {}
        try:
            logging.debug('reading device configuration from %s', DEVICE_FILE_PATH)
            with open(DEVICE_FILE_PATH, 'r') as f:
                device = json.load(f)
            device_ok = (len(set(device.keys()) & set(DEVICE_KEYS)) == len(DEVICE_KEYS))
            logging.debug('found %s keys in device file %s', len(DEVICE_KEYS), DEVICE_FILE_PATH)
        except Exception as ex:
            device_ok = False
            logging.error('error loading device file: %s', ex)
        try:
            logging.debug('opening flash file %s', FLASH_FILE_PATH)
            flash_size = os.path.getsize(FLASH_FILE_PATH)
            logging.debug('found %s byte flash file %s', flash_size, FLASH_FILE_PATH)
            flash_ok = (flash_size > 0)
        except Exception as ex:
            flash_ok = False
            logging.error('error loading flash file: %s', ex)
        return device, device_ok, flash_ok

    def button_pressed(self, *args):
        self.clear_leds()
        if self._ready_to_go:
            try:
                logging.info('begin programming')
                self.leds['programming'].on()
                self.buffer_switch.on()
                self.run_programming()
            except avrdude.AvrDeviceNotRespondingError as ex:
                logging.error('device not ready %s %s', type(ex), ex.args)
                logging.debug(traceback.format_exc())
                self.leds['fuse_fail'].blink(500, 500)
            except avrdude.SignatureReadError as ex:
                logging.error('can not read sig %s %s', type(ex), ex.args)
                logging.debug(traceback.format_exc())
                self.leds['flash_fail'].blink(500, 500)
            except avrdude.SignatureDoesNotMatchError as ex:
                logging.error('signature mismatch %s %s', type(ex), ex.args)
                logging.debug(traceback.format_exc())
                self.leds['fuse_pass'].blink(500, 500)
            except Exception as ex:
                logging.error('programming error %s %s', type(ex), ex.args)
                logging.debug(traceback.format_exc())
            finally:
                self.buffer_switch.off()
                self.leds['programming'].off()

    def run_programming(self):
        dude = avrdude.AvrDude(
            self.device['type'],
            SPI_DEVICE, PROGRAMMER, BAUDRATE_SLOW, BITRATE_SLOW, BAUDRATE_FAST, BITCLOCK_FAST)
        read_signature = dude.verify_signature_and_fuses()
        logging.info('device signature verified as %s', read_signature)
        time.sleep(0.1)
        read_fuses = dude.read_fuses()
        fuses_same = (
                self.device['E'] == read_fuses['E'] and
                self.device['H'] == read_fuses['H'] and
                self.device['L'] == read_fuses['L']
        )
        logging.info('device fuses read %s, same as device settings? %s', read_fuses, fuses_same)
        if not fuses_same:
            time.sleep(0.1)
            fuses_ok = dude.write_fuses(
                E=self.device['E'],
                H=self.device['H'],
                L=self.device['L'],
            )
            logging.info('fuse write done')
            if fuses_ok:
                self.leds['fuse_pass'].on()
                self.leds['fuse_fail'].off()
            else:
                self.leds['fuse_pass'].off()
                self.leds['fuse_fail'].on()
        time.sleep(0.1)
        flash_ok = dude.write_flash(FLASH_FILE_PATH)
        logging.info('flash write result %s', flash_ok)
        if flash_ok:
            self.leds['flash_pass'].on()
            self.leds['flash_fail'].off()
        else:
            self.leds['flash_pass'].off()
            self.leds['flash_fail'].on()

    def run(self):
        while self._alive:
            self.device, device_file_ok, flash_file_ok = self.load_firmware()
            self._ready_to_go = device_file_ok and flash_file_ok
            if self._ready_to_go:
                self.led_ready.on()
            else:
                self.led_ready.blink(500, 500)
            time.sleep(2)
        logging.info('shut down')

    def shutdown(self):
        self._alive = False
        self.clear_leds()
        sys.exit(0)




def signal_received_handler(signum, frame):
    logging.info("signal %s received in frame %s", signum, frame)
    if signum in (signal.SIGINT, signal.SIGTERM):
        global prog
        prog.shutdown()


def main():
    signal.signal(signal.SIGINT, signal_received_handler)
    signal.signal(signal.SIGTERM, signal_received_handler)
    signal.signal(signal.SIGHUP, signal_received_handler)
    signal.signal(signal.SIGTSTP, signal_received_handler)
    logging.basicConfig(level=LOG_LEVEL)
    logging.info('PiAVR programmer version %s', VERSION)
    global prog
    prog = PiProgrammer()
    prog.run()


if __name__ == '__main__':
    main()
