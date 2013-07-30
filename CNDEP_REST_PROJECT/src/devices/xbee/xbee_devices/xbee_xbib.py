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
A Dia Driver for the XBIB-x-DEV XBee Development Boards
"""

# imports
from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *

from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS, SM_DISABLED, XBeeConfigBlockSleep
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import PROD_DIGI_UNSPECIFIED

# constants
LED_IO_MAP = {
    "led1": "P2",
    "led2": "P1",
    "led3": "D4",
}


# exception classes

# interface functions

# classes
class XBeeXBIB(XBeeBase):
    """\
        This class extends one of our base classes and is intended as an
        example of a concrete, example implementation, but it is not itself
        meant to be included as part of our developer API. Please consult the
        base class documentation for the API and the source code for this file
        for an example implementation.

    """
    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [ [0xe8, 0xc105, 0x92], [0xe8, 0xc105, 0x11] ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_DIGI_UNSPECIFIED, ]

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        ## Local State Variables:
        self.__xbee_manager = None

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Settings Table Definition:

        settings_list = [
            Setting(
                name = 'xbee_device_manager', type = str, required = False,
                default_value = ''),
            Setting(
                name = 'extended_address', type = str, required = False,
                default_value = ''),
            Setting(
                name='sleep_ms', type=int, required=False,
                default_value=1000),
            Setting(name="led1_source", type=str, required=False),
            Setting(name="led2_source", type=str, required=False),
            Setting(name="led3_source", type=str, required=False),
            # This setting is provided for advanced users:
            Setting(
                name='awake_time_ms', type=int, required=False,
                default_value=1500,
                verify_function=lambda x: x >= 0 and x <= 0xffff),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="sw1", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="sw2", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="sw3", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="sw4", type=bool,
                initial=Sample(timestamp=0, value=False),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            # gettable and settable properties
            ChannelSourceDeviceProperty(name="led1", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda sample: self.prop_set_led("led1", sample)),
            ChannelSourceDeviceProperty(name="led2", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda sample: self.prop_set_led("led2", sample)),
            ChannelSourceDeviceProperty(name="led3", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(False, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=lambda sample: self.prop_set_led("led3", sample)),
        ]

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)


    ## Functions which must be implemented to conform to the XBeeBase
    ## interface:

    @staticmethod
    def probe():
        #   Collect important information about the driver.
        #
        #   .. Note::
        #
        #       This method is a static method.  As such, all data returned
        #       must be accessible from the class without having a instance
        #       of the device created.
        #
        #   Returns a dictionary that must contain the following 2 keys:
        #           1) address_table:
        #              A list of XBee address tuples with the first part of the
        #              address removed that this device might send data to.
        #              For example: [ 0xe8, 0xc105, 0x95 ]
        #           2) supported_products:
        #              A list of product values that this driver supports.
        #              Generally, this will consist of Product Types that
        #              can be found in 'devices/xbee/common/prodid.py'

        probe_data = XBeeBase.probe()

        for address in XBeeXBIB.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeXBIB.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.sample_indication)
        xbdm_rx_event_spec.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x92),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec)

        # Create a callback specification that calls back this driver when
        # our device has left the configuring state and has transitioned
        # to the running state:
        xbdm_running_event_spec = XBeeDeviceManagerRunningEventSpec()
        xbdm_running_event_spec.cb_set(self.running_indication)
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                                        xbdm_running_event_spec)

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)
        
        # Configure node sleep behavior:
        sleep_ms = SettingsBase.get_setting(self, "sleep_ms")
        awake_time_ms = SettingsBase.get_setting(self, "awake_time_ms")
        # The original sample rate is used as the sleep rate:
        xbee_sleep_cfg = XBeeConfigBlockSleep(extended_address)
        if sleep_ms > 0:
            # Configure node to sleep for the specified interval:
            xbee_sleep_cfg.sleep_cycle_set(awake_time_ms, sleep_ms)
        else:
            # If sleep_ms is 0, disable sleeping on the node altogether:
            xbee_sleep_cfg.sleep_mode_set(SM_DISABLED)
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)

        # Configure pins DIO0 .. DIO3 for digital input:
        for io_pin in [ 'D0', 'D1', 'D2', 'D3' ]:
            xbee_ddo_cfg.add_parameter(io_pin, 3)

        # Turn off LEDs:
        for led in LED_IO_MAP:
            xbee_ddo_cfg.add_parameter(LED_IO_MAP[led], 0)

        # Assert that all pin pull-ups are enabled:
        xbee_ddo_cfg.add_parameter('PR', 0x1fff)

        # Enable I/O line monitoring on pins DIO0 .. DIO3:
        xbee_ddo_cfg.add_parameter('IC', 0xf)

        # Disable any periodic I/O sampling:
        xbee_ddo_cfg.add_parameter('IR', 0)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        # Handle channels subscribed to output their data to our led
        # properties:
        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()
        for i in range(1,4):
            setting_name = "led%d_source" % i
            channel_name = SettingsBase.get_setting(self, setting_name)
            if channel_name is not None:
                cp.subscribe(channel_name,
                    (lambda prop: lambda cn: self.update_property(prop, cn))(
                        "led%d" % i))
        
        return True


    def stop(self):

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True
        

    ## Locally defined functions:
    def running_indication(self):
        self.__tracer.info("Running indication")
        # Our device is now running, load our initial state:
        extended_address = SettingsBase.get_setting(self, "extended_address")
        io_sample = self.__xbee_manager.xbee_device_ddo_get_param(
                        extended_address, 'IS')
        self.sample_indication(io_sample, extended_address)

    def prop_set_led(self, led_name, sample):
        ddo_io_value = 0 # I/O high impedance
        if sample.value:
            ddo_io_value = 4 # I/O sinking

        led_io = LED_IO_MAP[led_name]

        extended_address = SettingsBase.get_setting(self, "extended_address")
        try:
            self.__xbee_manager.xbee_device_ddo_set_param(
                                    extended_address, led_io, ddo_io_value,
                                    apply=True)
            self.property_set(led_name,
                Sample(0, Boolean(sample.value, style=STYLE_ONOFF)))
        except:
            pass

    def update_property(self, led_name, src_channel):
        self.prop_set_led(led_name, src_channel.get())

    def sample_indication(self, buf, addr):
        self.__tracer.debug('Sample indication')
        # Parse the I/O sample:
        io_sample = parse_is(buf)

        for i in range(4):
            # Refresh switch states, if different:
            val = bool(io_sample["DIO%d" % i])
            oldval =  bool(self.property_get("sw%d" % (i+1)).value)
            if oldval != val:
                self.property_set("sw%d" % (i+1), Sample(0, val))

# internal functions & classes

