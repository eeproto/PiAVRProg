# -*- coding: utf-8 -*-

"""
This file is part of the PiAVRProg project
 https://github.com/eeproto/PiAVRProg

This work is licensed under a Creative Commons Attribution-ShareAlike 4.0
 International License http://creativecommons.org/licenses/by-sa/4.0/

Copyright (c) 2019 EE Proto LLC https://www.eeproto.com

Author: christian@eeproto.com
"""

import subprocess
import logging
import re
import traceback


class GpioAccessDeniedError(Exception):
    pass


class AvrDeviceNotRespondingError(Exception):
    pass


class SignatureReadError(Exception):
    pass


class SignatureDoesNotMatchError(Exception):
    pass


class FuseFormatError(Exception):
    pass


class FuseWriteError(Exception):
    pass


class FuseReadError(Exception):
    pass


class FlashWriteError(Exception):
    pass


DEVICE_SIGNATURES = {
    'm168': '1e9406',
    'atmega168': '1e9406',
    'm168p': '1e940b',
    'atmega168p': '1e940b',
    'm168pb': '1e9415',
    'atmega168pb': '1e9415',
    'm328': '1e9514',
    'atmega328': '1e9514',
    'm328p': '1e950f',
    'atmega328p': '1e950f',
    'm328pb': '1e9516',
    'atmega328pb': '1e9516',
}

HEX_BYTE_MATCH = re.compile(r'^[0-9A-Fa-f]{2}$')


class AvrDude(object):

    def __init__(self, chip_type, programming_device, programmer,
                 baudrate_slow, bitclock_slow,
                 baudrate_fast, bitclock_fast):
        self.chip_type = chip_type
        self.programming_device = programming_device
        self.programmer = programmer
        self.baudrate_slow = baudrate_slow
        self.bitclock_slow = bitclock_slow
        self.baudrate_fast = baudrate_fast
        self.bitclock_fast = bitclock_fast

    def verify_signature_and_fuses(self):
        logging.info('reading device signature to verify chip type')
        result = self._command(
            baudrate=self.baudrate_slow,
            bitclock=self.bitclock_slow,
        )
        try:
            expected = DEVICE_SIGNATURES[self.chip_type.lower()]
            # https://pythex.org/?regex=avrdude%3A%20Device%20signature%20%3D%200x(%5B0-9A-Fa-f%5D%2B)&test_string=avrdude%3A%20Device%20signature%20%3D%200x1e940b&ignorecase=0&multiline=0&dotall=0&verbose=0
            signature_pattern = re.compile(r'avrdude: Device signature = 0x([0-9A-Fa-f]+)')
            signature = signature_pattern.search(result).group(1)
        except Exception as ex:
            logging.debug(traceback.format_exc())
            raise SignatureReadError('unable to read signature', ex)
        if not signature == expected:
            raise SignatureDoesNotMatchError('signature does not match, read {}, expected {}'.format(
                signature, expected
            ))
        return signature

    def read_fuses(self):
        logging.info('reading fuses')
        result = self._command(
            baudrate=self.baudrate_slow,
            bitclock=self.bitclock_slow,
            read_fuses=True,
        )
        try:
            fuses = {}
            fuse_pattern = re.compile(r'01000000([0-9A-Fa-f]{2}).*\n:00000001FF')
            match = fuse_pattern.findall(result)
            fuses['E'] = match[0]
            fuses['H'] = match[1]
            fuses['L'] = match[2]
            logging.debug('read fuses %s', fuses)
        except Exception as ex:
            logging.debug(traceback.format_exc())
            raise FuseReadError('unable to read fuses', ex)
        return fuses

    def write_fuses(self, E=None, H=None, L=None):
        logging.info('writing fuses E=%s H=%s L=%s', E, H, L)
        result = self._command(
            baudrate=self.baudrate_slow,
            bitclock=self.bitclock_slow,
            write_E_fuse=E,
            write_H_fuse=H,
            write_L_fuse=L,
        )
        errors = []
        if E is not None:
            if not 'efuse verified' in result:
                errors.append('E fuse write error')
            else:
                logging.debug('E fuse write ok')
        if H is not None:
            if not 'hfuse verified' in result:
                errors.append('H fuse write error')
            else:
                logging.debug('H fuse write ok')
        if L is not None:
            if not 'lfuse verified' in result:
                errors.append('L fuse write error')
            else:
                logging.debug('L fuse write ok')
        if len(errors) > 0:
            raise FuseWriteError(', '.join(errors))
        else:
            return True

    def write_flash(self, flash_file):
        logging.info('writing flash file %s', flash_file)
        result = self._command(
            baudrate=self.baudrate_fast,
            bitclock=self.bitclock_fast,
            chip_erase=True,
            write_flash_file=flash_file,
        )
        try:
            flash_write_match = re.search(r'(\d+) bytes of flash verified', result)
            bytes_flashed = int(flash_write_match.group(1))
            logging.info('wrote %s bytes to flash', bytes_flashed)
            return True
        except Exception as ex:
            logging.debug(traceback.format_exc())
            raise FlashWriteError('unable to write flash', ex)

    def _command(self, baudrate, bitclock, chip_erase=False,
                 write_E_fuse=None, write_H_fuse=None, write_L_fuse=None,
                 read_fuses=False,
                 write_flash_file=None,
                 ):
        args = [
            'avrdude',
            '-c', self.programmer,
            '-P', self.programming_device,
            '-p', self.chip_type,
            '-b', baudrate,
            '-B', bitclock,
            '-q',  # no progress bars
        ]
        if chip_erase:
            args.append('-e')
        if read_fuses:
            args += ['-U', 'efuse:r:-:i', '-U', 'hfuse:r:-:i', '-U', 'lfuse:r:-:i']
        if write_E_fuse is not None:
            if HEX_BYTE_MATCH.match(write_E_fuse) is None:
                raise FuseFormatError('E fuse {} is invalid'.format(write_E_fuse))
            args += ['-U', 'efuse:w:0x{}:m'.format(write_E_fuse.upper())]
        if write_H_fuse is not None:
            if HEX_BYTE_MATCH.match(write_H_fuse) is None:
                raise FuseFormatError('H fuse {} is invalid'.format(write_H_fuse))
            args += ['-U', 'hfuse:w:0x{}:m'.format(write_H_fuse.upper())]
        if write_L_fuse is not None:
            if HEX_BYTE_MATCH.match(write_L_fuse) is None:
                raise FuseFormatError('L fuse {} is invalid'.format(write_L_fuse))
            args += ['-U', 'lfuse:w:0x{}:m'.format(write_L_fuse.upper())]
        if write_flash_file is not None:
            args += ['-U', 'flash:w:{}:i'.format(write_flash_file)]
        logging.debug('runnning avrdude command %s', args)
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        result = stdout.decode('utf-8') + stderr.decode('utf-8')
        logging.debug('avrdude result %s', result)
        if 'Unable to open file' in result:
            raise GpioAccessDeniedError('GPIO access denied')
        if 'AVR device not responding' in result:
            raise AvrDeviceNotRespondingError('AVR not found')
        return result
