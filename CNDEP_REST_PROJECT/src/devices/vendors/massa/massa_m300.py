############################################################################
#                                                                          #
# Copyright (c)2008, 2009, Digi International (Digi). All Rights Reserved. #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its    #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,  and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing     #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,      #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

"""\
Massa M-300 Driver Connected to XBee 485 Adapter Driver

Supports a Massa M-300 device connected to a XBee 485 driver.  The following
Massa M-300 devices are supported:

    M-300/95 (min 12 in. / max. 180 in.)
    M-300/150 (min 7 in. / max. 96 in.)
    M-300/210 (min 4 in. / max. 50 in.)

Wiring information:

    M-300 Brown --> XBee 485 Pin 1 (485 Port B {+})
    M-300 Green --> XBee 485 Pin 2 (485 Port A {-})
    M-300 Black --> XBee 485 Pin 5 (GND)
    M-300 Red   --> XBee 485 Pin 6 (+12 DC)
    M-300 White --> Not Connected

XBee RS-485 DIP Switch Configuration:

    Pins 2, 3, 4 = ON (RS-485 Mode)
    Pins 5, 6    = OFF (Disable Bias, Termination)

Dia Configuration and Setup:

    By default the Massa M300 product comes from the factory set to operate
    at a baud rate of 19200, 8 character bits, 1 stop bit and no parity.

    An example configuration in Dia should look something like::

        - name: massa_m300
          driver: devices.vendors.massa.massa_m300:MassaM300
          settings:
              xbee_device_manager: xbee_device_manager
              extended_address: "00:13:a2:00:40:52:e1:93!"
              baudrate: 19200
              stopbits: 1
              parity: none
              poll_rate_sec: 60    

NOTE: this driver at present does not support any sleep modes.

"""

# imports
import struct

from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from devices.xbee.xbee_devices.xbee_serial import XBeeSerial
from settings.settings_base import SettingsBase, Setting
from common.types.boolean import Boolean, STYLE_ONOFF, STYLE_YESNO
from channels.channel_source_device_property import *

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import gw_extended_address_tuple
from devices.xbee.common.prodid import PROD_DIGI_XB_ADAPTER_RS485

# constants

# exception classes

# interface functions

# classes
class MassaM300(XBeeSerial):

    # Our base class defines all the addresses we care about.
    ADDRESS_TABLE = [ ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_DIGI_XB_ADAPTER_RS485, ]

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        ## Local State Variables:
        self.__xbee_manager = None
        self.__response_buffer = ""
        self.__request_events = []
        self.__request_retry_events = []

        from core.tracing import get_Tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='poll_rate_sec', type=int, required=False,
                default_value=5,
                verify_function=lambda x: x >= 0),
            Setting(
                name='bus_id', type=int, required=False,
                default_value=0,
                verify_function=lambda x: x >= 0),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="strength", type=int,
                initial=Sample(timestamp=0, value=0, unit="%"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="target_detected", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_YESNO)),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="error_flag", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_YESNO)),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="range", type=int,
                initial=Sample(timestamp=0, value=0, unit="in"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),

            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, value=0.0, unit="C"),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
        ]

        ## Initialize the DeviceBase interface:
        XBeeSerial.__init__(self, self.__name, self.__core,
                                settings_list, property_list)


    ## Functions which must be implemented to conform to the XBeeSerial
    ## interface:
        
    def read_callback(self, buf):
        self.message_indication(buf)

    ## Functions which must be implemented to conform to the XBeeBase
    ## interface:

    @staticmethod
    def probe():
        """\
            Collect important information about the driver.

            .. Note::

                * This method is a static method.  As such, all data returned
                  must be accessible from the class without having a instance
                  of the device created.

            Returns a dictionary that must contain the following 2 keys:
                    1) address_table:
                       A list of XBee address tuples with the first part of the
                       address removed that this device might send data to.
                       For example: [ 0xe8, 0xc105, 0x95 ]
                    2) supported_products:
                       A list of product values that this driver supports.
                       Generally, this will consist of Product Types that
                       can be found in 'devices/xbee/common/prodid.py'
        """
        probe_data = XBeeSerial.probe()

        for address in MassaM300.ADDRESS_TABLE:
            probe_data['address_table'].append(address)

        # We don't care what devices our base class might support.
        # We do not want to support all of those devuces, so we will
        # wipe those out, and instead JUST use ours instead.
        probe_data['supported_products'] = []

        for product in MassaM300.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):
        """\
            Called when new configuration settings are available.
       
            Must return tuple of three dictionaries: a dictionary of
            accepted settings, a dictionary of rejected settings,
            and a dictionary of required settings that were not
            found.
        """

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s", rejected, not_found)
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)


    def start(self):
        """Start the device driver.  Returns bool."""

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                                       xbdm_running_event_spec)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Call the XBeeSerial function to add the initial set up of our device.
        # This will set up the destination address of the devidce, and also set
        # the default baud rate, parity, stop bits and flow control.
        XBeeSerial.initialize_xbee_serial(self, xbee_ddo_cfg)

        # TODO - these RS-485 issues should be abstracted to XBeeSerial

        # Assert that the AT node is enabled for RS-485 HIGH:
        xbee_ddo_cfg.add_parameter('D7', 7)

        # Enable +12v outpout terminal on RS-485 adapter pin 6:
        xbee_ddo_cfg.add_parameter('D2', 5)

        # Packetization timeout to 6 characters (standard M300 msg len):
        xbee_ddo_cfg.add_parameter('RO', 6)

        # Register configuration blocks with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True
        

    ## Locally defined functions:
    def running_indication(self):
        """\
            Dia will call this function when it has finished sending the
            preliminary DDO command blocks to the M300 device.
            At this point, the M300 is correctly configured at the XBee level
            to be able to accept data from us.
        """
        self.__tracer.info("running indication")
        # Scheduling first request and watchdog:
        self.__schedule_request()
        self.__reschedule_retry_watchdog()


    def make_request(self):
        self.__tracer.info("make_request")
        bus_id = SettingsBase.get_setting(self, "bus_id")
	req = [ 170, bus_id, 3, 0, 0 ]
	req.append(sum(req) % 256)
	buf = reduce(lambda s, b: s + struct.pack("B", b), req, "")

        try:
            ret = self.write(buf)
            if ret == False:
                raise Exception, "write failed"
        except:
            # try again later:
            self.__tracer.error("xmission failure, will retry.")
            self.__schedule_request()
            self.__reschedule_retry_watchdog()

    def __schedule_request(self):
        self.__tracer.info("scheduling request")
        poll_rate_sec = SettingsBase.get_setting(self, "poll_rate_sec")

        # Attempt to Cancel all/any pending request events still waiting
        # to run for our device.
        for event in self.__request_events:
            try:
                self.__xbee_manager.xbee_device_schedule_cancel(event)
            except:
                pass
        self.__request_events = []

        # Request a new event at our poll rate in the future.
        event = self.__xbee_manager.xbee_device_schedule_after(
            poll_rate_sec, self.make_request)
        if event != None:
            self.__request_events.append(event)

    def __reschedule_retry_watchdog(self):
        self.__tracer.warning("reschedule watchdog")
        poll_rate_sec = SettingsBase.get_setting(self, "poll_rate_sec")

        # Attempt to Cancel all/any pending retry request events still waiting
        # to run for our device.
        for event in self.__request_retry_events:
            try:
                self.__xbee_manager.xbee_device_schedule_cancel(event)
            except:
                pass
        self.__request_retry_events = []

        # Request a new event at our poll rate in the future.
        event = self.__xbee_manager.xbee_device_schedule_after(
            poll_rate_sec * 1.5, self.retry_request)
        if event != None:
            self.__request_events.append(event)

    def retry_request(self):
        self.__tracer.info("retry request.")
        self.make_request()
        self.__reschedule_retry_watchdog()

    def message_indication(self, buf):
        self.__tracer.info("message indication.")
        self.__response_buffer += buf

        if len(self.__response_buffer) < 6:
            # We may need to just give the network a bit more time
            # but just in case, reschedule the retry event now:
            self.__reschedule_retry_watchdog()
            return
                    
        bus_id = 0
        strength = 0.00
        target_detected = False
        error_flag = False
        range = 0
        temperature = 0
        checksum_good = False

        response = self.__response_buffer[0:6]
        self.__response_buffer = self.__response_buffer[6:]
        response = struct.unpack("6B", response)

        # Parse the response packet:

        bus_id = response[0]

        b = (response[1] & 0xf0) >> 4
        strength_tab = { 0x1: 25, 0x2: 50, 0x3: 75, 0x4: 100 }
        if b in strength_tab:
            strength = strength_tab[b]
        else:
            strength = 0

        b = (response[1] & 0xf)
        if (b & 0x8):
            target_detected = True
#	    if (b & 0x4):
#		vout_mode = True
#	    if (b & 0x2):
#		switch_mode = True
        if (b & 0x1):
            error_flag = True

        range = ((response[3] << 8) | response[2]) / 128
        temperature = (response[4] * 0.48876) - 50

        if (sum(response[0:5]) % 256 == response[5]):
            checksum_good = True

        if not checksum_good:
            # Ick!  The RS-485 reply packets may not been packetized
            # in the proper sequence.  Flush the buffer.
            self.__response_buffer = ""
        else:
            # Update our channels:
            self.property_set("strength", Sample(0, strength, "%"))
            self.property_set("target_detected",
                Sample(0, Boolean(target_detected, STYLE_YESNO)))
            self.property_set("error_flag",
                Sample(0, Boolean(error_flag, STYLE_YESNO)))
            self.property_set("range", Sample(0, range, "in"))
            self.property_set("temperature", Sample(0, temperature, "C"))

        # Schedule our next poll:
        self.__schedule_request()
        # Reschedule retry watchdog:
        self.__reschedule_retry_watchdog()
        


# internal functions & classes

