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
A Dia Driver for the Digi XBee SmartPlug with Power Management
"""

# imports
import struct
import time

from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *


from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is, sample_to_mv
from devices.xbee.common.prodid import PROD_DIGI_XB_RPM_SMARTPLUG

# constants

initial_states = ["on", "off", "same"]

# exception classes

# interface functions

# classes
class XBeeRPM(XBeeBase):
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
    SUPPORTED_PRODUCTS = [ PROD_DIGI_XB_RPM_SMARTPLUG, ]

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:
        self.__xbee_manager = None
        self.offset = 520.0
        self.__power_on_time = 0


        # Settings
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.
        # extended_address: the extended address of the XBee device you
        #                   would like to monitor.
        # sample_rate_ms: the sample rate of the XBee SmartPlug.
        # default_state: "On"/"Off"/"Same", if "On" the plug will default to
        #                being switched on.
        # idle_off_seconds: Number of seconds to go by before forcing power off.
        #                   If not set the value defauts to 0, which means
        #                   the device never idles out.  
        # power_on_source: optional setting; string name of a Boolean
        #                  "device.channel" to be used as the state.  For
        #                  example, if set to the name of a channel which
        #                  changes value from False to True, the SmartPlug
        #                  would change from being off to on.
        # pf_adjustment: optional setting; floating point value between 
        #                0 and 1, that is used to adjust the current 
        #                output given a known power factor.
        #                defaults to 1 (i.e no adjustment)
        #                Note: The unit cannot determine the pf, 
        #                it is strictly a user supplied value.
        # device_profile: optional setting; string value corresponding
        #                 to a preset pf_adjustment value.  
        #                 These values are by not intended to be precise;
        #                 they are only estimates.  
        #                 For a list of valid device_profile settings see the
        #                 check_profiles() function in the driver source.

        settings_list = [
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=1000,
                verify_function=lambda x: x > 0 and x < 0xffff),
            Setting(
                name='default_state', type=str, required=False,
                default_value="on",
                parser=lambda s: s.lower(),
                verify_function=lambda s: s in initial_states),
            Setting(
                name='idle_off_seconds', type=int, required=False,
                default_value=0, verify_function=lambda x: x >= 0),
            Setting(name="power_on_source", type=str, required=False),
            Setting(name="pf_adjustment", type=float, required=False,
                    default_value=1.0,
                    verify_function=lambda i:0 < i and i <= 1.0),
            Setting(name="device_profile", type=str, required=False),
        ]

        ## Channel Properties Definition:
        property_list = [
            # gettable properties
            ChannelSourceDeviceProperty(name="light", type=float,
                initial=Sample(timestamp=0, unit="brightness", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="temperature", type=float,
                initial=Sample(timestamp=0, unit="C", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="current", type=float,
                initial=Sample(timestamp=0, unit="A", value=0.0),
                perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(name="power_on", type=Boolean,
                initial=Sample(timestamp=0,
                    value=Boolean(True, style=STYLE_ONOFF)),
                perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                options=DPROP_OPT_AUTOTIMESTAMP,
                set_cb=self.prop_set_power_control),
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

        for address in XBeeRPM.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeRPM.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            self.__tracer.error("Settings rejected/not found: %s %s",
                                rejected, not_found)
            return (accepted, rejected, not_found)

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

        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

        # Configure pins DI1 .. DI3 for analog input:
        for io_pin in [ 'D1', 'D2', 'D3' ]:
            xbee_ddo_cfg.add_parameter(io_pin, 2)

        # Get the extended address of the device:
        default_state = SettingsBase.get_setting(self, "default_state")

        if default_state != "same":
            # Configure pin DI4 for digital output, default state setting:
            self.prop_set_power_control(Sample(0,
                                               Boolean(default_state,
                                                       STYLE_ONOFF)))
        else:
            # Retrieve current state from device for channel
            d4 = self.__xbee_manager.xbee_device_ddo_get_param(extended_address,
                                                               "d4")

            d4 = struct.unpack('B', d4)[0]
            
            if d4 == 5:
                state = True

                # Treat as having just been turned on for shut-off
                self.__power_on_time = time.time()
            elif d4 == 4:
                state = False
            else:
                raise Exception, "Unrecognized initial power_on state"

            self.property_set("power_on",
                              Sample(0,
                                     Boolean(state,
                                             style=STYLE_ONOFF)))
            
        # Configure the IO Sample Rate:
        sample_rate = SettingsBase.get_setting(self, "sample_rate_ms")
        xbee_ddo_cfg.add_parameter('IR', sample_rate)

        # Handle subscribing the devices output to a named channel,
        # if configured to do so:
        power_on_source = SettingsBase.get_setting(self, 'power_on_source')
        if power_on_source is not None:
            cm = self.__core.get_service("channel_manager")
            cp = cm.channel_publisher_get()
            cp.subscribe(power_on_source, self.update_power_state)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def get_power_factor(self):
        pf_setting = SettingsBase.get_setting(self, 'pf_adjustment')
        dev_prof = SettingsBase.get_setting(self, 'device_profile')

        if dev_prof is not None:
            return self.check_profiles(dev_prof)
        else:
            return pf_setting

    def stop(self):

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True


    ## Locally defined functions:
    def check_profiles(self, device):
        """
            Preset device profiles and their power factors.
            These values are by no means meant to be precise,
            and at best represent ball-park estimates.
        """
        string = device.lower()

        if string == 'fluor-mag':
            return 0.4
        elif string == 'fluor-electronic':
            return 0.6
        elif string == '1/3hp-dc-motor':
            return 0.6
        elif string == 'laptop':
            return 0.53
        elif string == 'lcd_monitor':
            return 0.65
        elif string == 'workstation':
            return 0.97 #p.s with pf correction
        else:
            self.__tracer.warning("Couldn't find device profile %s, using 1.0",
                                  string)
            return 1.0


    def sample_indication(self, buf, addr):
        # Parse the I/O sample:
        io_sample = parse_is(buf)

        # Calculate channel values:
        light_mv, temperature_mv, current_mv = \
            map(lambda cn: sample_to_mv(io_sample[cn]), ("AD1", "AD2", "AD3"))
        light = round(light_mv,0)
        if light < 0:
            # clamp to be zero or higher
            light = 0

        power_state = self.property_get("power_on").value

        # TODO: CRA Max could you remove this offset code?  Change to clip at 0.
        if not power_state:
            self.offset = current_mv * (157.0 /47.0)
            if self.offset >= 600.0: ## Probably a current spike from flipping the power relay
                self.offset = 520.0

        current = round(
                    (current_mv * (157.0 / 47.0) - self.offset) / 180.0 * 0.7071,
                    3)

        pf_adj = self.get_power_factor()
        # compute powerfactor adjusted current
        if 1.0 >= pf_adj and 0.0 <= pf_adj:
            current *= pf_adj

        if current <= 0.05:
            # Clip the noise at the bottom of this sensor:
            current = 0.0
        temperature = (temperature_mv - 500.0) / 10.0
        # self-heating correction
        temperature = (temperature - 4.0) - (0.017*current**2 + 0.631*current)
        temperature = round(temperature, 2)

        # Update channels:
        self.property_set("light", Sample(0, light, "brightness"))
        self.property_set("temperature", Sample(0, temperature, "C"))
        self.property_set("current", Sample(0, current, "A"))

        # check the realtime clock and compare to the last power_on_time
        # turn off if the idle_off_setting has been met or exceeded
        idle_off_setting = SettingsBase.get_setting(self, "idle_off_seconds")
        if (power_state and idle_off_setting > 0):
            if ((time.time() - self.__power_on_time)  >= idle_off_setting):
                power_on_state_bool = self.property_get("power_on")
                power_on_state_bool.value = False
                self.prop_set_power_control(power_on_state_bool)

    def update_power_state(self, chan):
        # Perform power control:
        self.prop_set_power_control(chan.get())

    def prop_set_power_control(self, bool_sample):

        if bool_sample.value:
            ddo_io_value = 5 # on
            self.__power_on_time = time.time()
        else:
            ddo_io_value = 4 # off


        extended_address = SettingsBase.get_setting(self, "extended_address")
        try:
            self.__xbee_manager.xbee_device_ddo_set_param(
                                    extended_address, 'D4', ddo_io_value,
                                    apply=True)
        except:
            pass

        self.property_set("power_on",
            Sample(0, Boolean(bool_sample.value, style=STYLE_ONOFF)))


# internal functions & classes

