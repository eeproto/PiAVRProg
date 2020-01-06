# Software Installation

The Software for this Programmer is built on top a Linux distribution. I chose [PipaOS](http://pipaos.mitako.eu/) by Albert Casals because it is fast, slim, can be installed as a read-only SD-card image, and it is generally great work. The read-only image helps extending the life of SD cards a lot.

If you want a ready-to-go image instead of going through the installation, [let me know](mailto:hello@eeproto.com) as I plan to upload one.

## 1. Install The OS

Grab a fresh SD card, min. 2 GB, and download your choice of PipaOS image. I used [pipaos-stretch-6.0.img.gz](http://pipaos.mitako.eu/download/pipaos-stretch-6.0.img.gz). Use an SD-card adapter to write the image. There are plenty of tools out there, like the [balena Etcher](https://www.balena.io/etcher/). Or use `dd`. Or `dc3dd`, which works like `dd` but is a little more talkative. Writing through the `/dev/disk/by-id/` nodes instead of `/dev/sdx` helps you to flash the SD card and not accidentally your hard disk.

```bash
wget http://pipaos.mitako.eu/download/pipaos-stretch-6.0.img.gz
sudo umount /dev/disk/by-id/usb-SanDisk_SDDR-B531_012345-0*
zcat ~/Downloads/pipaos-stretch-6.0.img.gz | sudo dc3dd verb=on of=/dev/disk/by-id/usb-SanDisk_SDDR-B531_012345-0\:0
```

## 2. Configure The OS

Get access to your freshly installed OS. 

Plug the SD card into your Pi, hook it up to your Ethernet, boot it up, and SSH into it. The default credentials are user `sysop` and password `posys`. Your router might be smart enough to pick up the default hostname `pipaos`. If not, use `nmap` to find a MAC address that looks like a Pi:

```bash
# with hostname resolution
ssh sysop@pipaos

# without
sudo nmap -sP 192.168.1.1-254
# look for something like this:
#   Nmap scan report for 192.168.1.29
#   Host is up (-0.099s latency).
#   MAC Address: B8:27:xx:xx:xx:xx (Raspberry Pi Foundation)
ssh sysop@192.168.1.29
```
Make your basic OS settings, something like this:
```bash
# always change the password first
passwd

# update and install a few useful tools including avrdude
sudo apt update
sudo apt install -y vim python3-virtualenv virtualenv screen git avrdude ntpdate
sudo apt upgrade

# choose and set your hostname
export HOSTNAME=piavr
sudo sed -i -e "s/pipaos/$HOSTNAME/" /etc/hosts
sudo sed -i -e "s/pipaos/$HOSTNAME/" /etc/hostname

# set your timezone and set the clock
sudo dpkg-reconfigure tzdata
sudo service ntp stop
sudo ntpdate pool.ntp.org

# disable a few services for faster startup
#  you can skip this if you don't know what these are
sudo systemctl disable avahi-daemon
sudo systemctl disable triggerhappy
sudo systemctl disable ntp
sudo systemctl disable wpa_supplicant
sudo systemctl disable apt-daily
sudo systemctl disable apt-daily-upgrade
sudo systemctl disable pipaos-bootlogo
sudo apt remove alsa-utils
```

Make sure [SPI is enabled](https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/README.md) by checking:

```bash
lsmod | grep spi
grep spi /boot/config.txt
```
 
`lsmod` should should report a module `spidev` loaded.

This line has to be in `/boot/config.txt` without a comment `#` sign in front:

```ini
dtparam=spi=on
```

## 3. Auto Mount USB Drive 

The AVR Hex file and device configuration will be supplied on a removable USB drive. We want to plug it into the Pi at any time without worrying about mounting it manually.

This modifies your `/etc/fstab` do to just that:

```bash
sudo mkdir /media/usb
sudo chattr +i /media/usb
echo "/dev/sda1  /media/usb  vfat  defaults,sync,nofail,noexec,nosuid,noatime,nodev,user  0 0" | sudo tee -a /etc/fstab
```

## 4. avrdude

We will use [avrdude](http://savannah.nongnu.org/projects/avrdude/) to actually program the AVR. Make sure we got the right version from the repo. You want at version 6.1 or newer with linux SPI support:

```bash
avrdude
# check to see "version 6.1" or newer

avrdude -c ?type 2> >(grep linux)
# look for a line starting with "linuxspi"
```

## 5. Python Scripts

For programming standalone, the Pi will run a background service that works with the buttons, LEDs, and avrdude. Install it from github and enable it:

```bash
# choose where you would like to install this
cd /var/lib/
sudo mkdir piavr
sudo chown sysop piavr
cd piavr

# wrap it into a virtual environment
virtualenv --python=/usr/bin/python3 .
source /var/lib/piavr/bin/activate
git clone https://github.com/eeproto/PiAVRProg
pip install -r PiAVRProg/software/scripts/requirements.txt

# install as a system service on boot
sudo ln -snf /var/lib/piavr/PiAVRProg/software/etc_systemd_system/avrprogrammer.service \
 /etc/systemd/system
sudo systemctl enable avrprogrammer.service
```


## Finish

Finally, make the root filesystem read-only:

```bash
sudo pipaos-lockfs lock persistent
```

If you need to make changes in the future, boot, log in, and temporarily remount as read-write:
```bash
sudo pipaos-lockfs unlock
# do stuff ..
sudo pipaos-lockfs lock
sudo reboot
```
PipaOS is great, right?

You could also do all that by mounting the SD card on your computer like this and do some clever chrooting:

```bash
sudo mount /dev/disk/by-id/usb-SanDisk_SDDR-B531_012345-0\:0-part1 /media/boot
sudo mount /dev/disk/by-id/usb-SanDisk_SDDR-B531_012345-0\:0-part2 /media/root
# ...
```



## Troubleshoot

Here are a few things you can try in case things don't work as expected. Log in to the Pi and do this on the commandline.

Plug in a fresh AVR chip and see if avrdude can find it: 
```bash
sudo avrdude -c linuxspi -v -p atmega328p -P /dev/spidev0.0
```

Try reading a few things from the chip:
```bash
# read signature at a low baud rate
sudo avrdude -c linuxspi -v -p atmega328p -b19200 -B10 -P /dev/spidev0.0
 
# read flash to binary file at 2MHz SPI clock
sudo avrdude -c linuxspi -v -p atmega328p -P /dev/spidev0.0 -v \
 -b 2000000 \
 -U flash:r:/tmp/flash.bin:r
```

Try manually writing:
```bash
# write fuses, -D no auto erase, 19200 SPI clock rate
sudo avrdude -c linuxspi -v -p atmega328p -P /dev/spidev0.0 -v \
 -b 19200 -B10 \
 -U efuse:w:0xFF:m -U hfuse:w:0xD9:m -U lfuse:w:0xE2:m
 
# write flash, no auto erase, -e chip erase, 2 MHz SPI clock
sudo avrdude -c linuxspi -v -p atmega328p -P /dev/spidev0.0 -v \
 -b 2000000 \
 -U flash:w:/tmp/firmware.hex:i
```

Try different bit clock rates and baud rates. Check the [online docs](https://www.nongnu.org/avrdude/user-manual/avrdude.html) for details. Modify the Python scripts accordingly.
