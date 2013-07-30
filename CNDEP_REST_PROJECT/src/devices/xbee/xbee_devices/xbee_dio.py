############################################################################
#                                                                          #
# Copyright (c)2008-2011, Digi International (Digi). All Rights Reserved.  #
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
A Dia Driver for the XBee Digital IO Adapter
"""

# imports
import struct
import time

from devices.device_base import DeviceBase
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF, STYLE_TF

from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep \
    import CYCLIC_SLEEP_EXT_MAX_MS, SM_DISABLED, XBeeConfigBlockSleep
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *

from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import \
     MOD_XB_ZB, MOD_XB_S2C_ZB, PROD_DIGI_XB_ADAPTER_DIO


# constants

# Control lines for configuration
IN = 0
OUT = 1

#                   in    out
CONTROL_LINES = [ ["d8", "d4"],
                  ["d1", "d6"],
                  ["d2", "d7"],
                  ["d3", "p2"],
                  ]

INPUT_CHANNEL_TO_PIN = [ 8, 1, 2, 3 ]

# exception classes

# interface functions

# classes
class XBeeDIO(XBeeBase):
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
    SUPPORTED_PRODUCTS = [ PROD_DIGI_XB_ADAPTER_DIO, ]

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:
        self.__xbee_manager = None

        # Settings
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.
        # extended_address: the extended address of the XBee Sensor device you
        #                   would like to monitor.
        # sleep: True/False setting which determines if we should put the
        #        device to sleep between samples.
        # sleep_time_ms: If set for sleep, specifies the length of time that
        #                the module will sleep after a period of awake_time_ms
        #                each cycle.
        # sample_rate_ms: If set, then value is loaded into IR to cause period
        #                 data updated regardless of change.  Also, if non-zero
        #                 then samples are always updated (timestamp refreshed)
        #                 even if there was no change.
        #                 (Is Optional, defaults to 0/off, valid range 0-60000)
        # power: True/False setting to enable/disable the power output
        #        on terminal 6 of the adapter.
        # channel1_dir: Operating I/O mode for pin 1 of the adapter.
        #               Must be a string value comprised of one of the following:
        #                   "In" - pin is configured to be an input.
        #                   "Out" - pin is configured to be an output.
        # channel2_dir: Operating I/O mode for pin 2 of the adapter.
        #               See channel1_dir for valid setting information.
        # channel3_dir: Operating I/O mode for pin 3 of the adapter.
        #               See channel1_dir for valid setting information.
        # channel4_dir: Operating I/O mode for pin 4 of the adapter.
        #               See channel1_dir for valid setting information.
        # channel1_source: If channel1_dir is configured as an output, this
        #                  option setting may be specified to a
        #                  "device.channel" channel name.  The Boolean value
        #                  of this channel will specify to logic state for
        #                  pin 1 on the adapter.
        # channel2_source: Configures output value source channel for pin 2
        #                  of the adapter.
        #                  See channel1_source setting information.
        # channel3_source: Configures output value source channel for pin 3
        #                  of the adapter.
        #                  See channel1_source setting information.
        # channel4_source: Configures output value source channel for pin 4
        #                  of the adapter.
        #                   See channel1_source setting information.
        # awake_time_ms: How many milliseconds should the device remain
        #                awake after waking from sleep.
        # sample_predelay: How long, in milliseconds, to wait after waking
        #                  up from sleep before taking a sample from the
        #                  inputs.
        # enable_low_battery: Force an adapter to enable support for
        #                     battery-monitor pin.
        #                     It should be only enabled if adapter is using 
        #                     internal batteries. Optional, Off by default.                     

        settings_list = [
            Setting(
                name='sleep', type=Boolean, required=False,
                default_value=Boolean(False)),
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=0,
                verify_function=lambda x: x >= 0 and x <= 60000),
           Setting(
                name='sleep_time_ms', type=int, required=False,
                default_value=60000,
                verify_function=lambda x: x >= 0 and \
                                x <= CYCLIC_SLEEP_EXT_MAX_MS),
            Setting(
                name='power', type=Boolean, required=True,
                default_value=Boolean("On", STYLE_ONOFF)),
            Setting(
                name='channel1_dir', type=str, required=True),
            Setting(
                name='channel1_default', type=Boolean, required=False),
            Setting(
                name='channel1_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel2_dir', type=str, required=True),
            Setting(
                name='channel2_default', type=Boolean, required=False),
            Setting(
                name='channel2_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel3_dir', type=str, required=True),
            Setting(
                name='channel3_default', type=Boolean, required=False),
            Setting(
                name='channel3_source', type=str, required=False,
                default_value=''),
            Setting(
                name='channel4_dir', type=str, required=True),
            Setting(
                name='channel4_default', type=Boolean, required=False),
            Setting(
                name='channel4_source', type=str, required=False,
                default_value=''),

            # This setting is provided for advanced users, it is not required:
            Setting(
                name='awake_time_ms', type=int, required=False,
                default_value=5000,
                verify_function=lambda x: x >= 0 and x <= 0xffff),
            Setting(
                name='sample_predelay', type=int, required=False,
                default_value=1000,
                verify_function=lambda x: x >= 0 and x <= 0xffff),
            Setting(
                name='enable_low_battery', type=Boolean, required=False,
                default_value=Boolean("Off", STYLE_ONOFF)),                             
        ]

        ## Channel Properties Definition:
        # This device hardware can monitor the state of its output
        # pins.  Therefore, there are always four input channels.
        # The other properties and channels will be populated when we
        # know the directions of our IO ports.
        property_list = [
            ChannelSourceDeviceProperty(
                name='channel1_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET, 
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name='channel2_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET, 
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name='channel3_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET, 
                options=DPROP_OPT_AUTOTIMESTAMP),
            ChannelSourceDeviceProperty(
                name='channel4_input', type=bool,
                initial=Sample(timestamp=0, value=False, unit='bool'),
                perms_mask=DPROP_PERM_GET, 
                options=DPROP_OPT_AUTOTIMESTAMP),
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

        for address in XBeeDIO.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeDIO.SUPPORTED_PRODUCTS:
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

        # Verify that the sample predelay time when added to the awake time
        # is not over 0xffff.
        if accepted['sample_predelay'] + accepted['awake_time_ms'] > 0xffff:
            self.__tracer.error("The awake_time_ms value (%d) " + 
                                "and sample_predelay value (%d) " + 
                                "when added together cannot exceed 65535.",
                                accepted['sample_predelay'],
                                accepted['awake_time_ms'])

            rejected['awake_time_ms'] = accepted['awake_time_ms']
            del accepted['awake_time_ms']
            rejected['sample_predelay'] = accepted['sample_predelay']
            del accepted['sample_predelay']
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        cm = self.__core.get_service("channel_manager")
        cp = cm.channel_publisher_get()

        # Register ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_register(self)

        # Get the extended address of the device:
        self.__extended_address = SettingsBase.get_setting(self, 
                                                           "extended_address")

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.sample_indication)
        xbdm_rx_event_spec.match_spec_set(
            (self.__extended_address, 0xe8, 0xc105, 0x92),
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
        xbee_ddo_cfg = XBeeConfigBlockDDO(self.__extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

        # Configure pins DIO0 .. DIO3 for digital input:
        pr = 0xe1 # DIO0-3 pullups off, all else on
        ic = 0

        for io_pin in range(4):
            dir = SettingsBase.get_setting(self, 'channel%d_dir' % (io_pin+1) )
            dir = dir.lower()

            # Enable input on all pins:
            xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][IN], 3)

            # Build our change detection mask for all io pins:
            ic |= 1 << INPUT_CHANNEL_TO_PIN[io_pin]

            if dir == 'in':
                # Disable sinking driver output:
                xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][OUT], 4)

            elif dir == 'out':
                # Create the output channel for this IO pin:
                self.add_property(
                    ChannelSourceDeviceProperty(
                        name='channel%d_output' % (io_pin+1), type=Boolean,
                        initial=Sample(timestamp=0, value=Boolean(False), unit='bool'),
                        perms_mask=(DPROP_PERM_GET|DPROP_PERM_SET),
                        options=DPROP_OPT_AUTOTIMESTAMP,
                        set_cb=lambda sample, io=io_pin: \
                                self.set_output(sample, io) )
                    )

                # If set, subscribe to the channel that drives our output logic:
                source = SettingsBase.get_setting(self, 'channel%d_source' 
                                                  % (io_pin+1))
                if len(source):
                    cp.subscribe(source, 
                                 lambda chan, io=io_pin: self.update(chan, io) )

                # If not set, attempt to grab the default output setting,
                # and use that instead.
                else:
                    out = SettingsBase.get_setting(self, 'channel%d_default' 
                                                   % (io_pin+1))
                    if out == True:
                        self.__tracer.debug("Setting default output to High")
                        xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][OUT], 5)
                    elif out == False:
                        self.__tracer.debug("Setting default output to Low")
                        xbee_ddo_cfg.add_parameter(CONTROL_LINES[io_pin][OUT], 4)
                    else:
                        self.__tracer.debug("Not setting default output value")

        # if adapter is using internal batteries, then configure battery-monitor
        # pin and add low_battery channel
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # configure battery-monitor pin DIO11/P1 for digital input
            xbee_ddo_cfg.add_parameter('P1', 3)
            # add low_battery channel
            self.__tracer.info("Adapter is using internal batteries... " +
                               "adding low_battery channel")
            self.add_property(
                ChannelSourceDeviceProperty(name="low_battery", type=bool,
                    initial=Sample(timestamp=0, value=False),
                    perms_mask=DPROP_PERM_GET, options=DPROP_OPT_AUTOTIMESTAMP))
        else:
            self.__tracer.info("Adapter is not using internal batteries.")

        # Enable I/O line monitoring on pins DIO0 .. DIO3 &
        # enable change detection on DIO11:
        #
        # 0x   8    0    0
        #   1000 0000 0000 (b)
        #   DDDD DDDD DDDD
        #   IIII IIII IIII
        #   OOOO OOOO OOOO
        #   1198 7654 3210
        #   10
        #
        xbee_ddo_cfg.add_parameter('IC', ic)

        # Assert input pull-ups
        xbee_ddo_cfg.add_parameter('PR', 0x1fff)

        # this defaults to 0
        xbee_ddo_cfg.add_parameter('IR', SettingsBase.get_setting(self, 'sample_rate_ms'))

        # Enable/disable power output on terminal 6:
        power = SettingsBase.get_setting(self, "power")
        if power:
            xbee_ddo_cfg.add_parameter('p3', 5)
        else:
            xbee_ddo_cfg.add_parameter('p3', 4)

        # Register this configuration block with the XBee Device Manager:
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

        # Setup the sleep parameters on this device:
        will_sleep = SettingsBase.get_setting(self, "sleep")
        sample_predelay = SettingsBase.get_setting(self, "sample_predelay")
        awake_time_ms = (SettingsBase.get_setting(self, "awake_time_ms") +
                         sample_predelay)
        # The original sample rate is used as the sleep rate:
        sleep_time_ms = SettingsBase.get_setting(self, "sleep_time_ms")
        xbee_sleep_cfg = XBeeConfigBlockSleep(self.__extended_address)
        if will_sleep:
            xbee_sleep_cfg.sleep_cycle_set(awake_time_ms, sleep_time_ms)
        else:
            xbee_sleep_cfg.sleep_mode_set(SM_DISABLED)
        self.__xbee_manager.xbee_device_config_block_add(self, xbee_sleep_cfg)

        if will_sleep:
            # Sample time pre-delay, allow the circuitry to power up and
            # settle before we allow the XBee to send us a sample:
            xbee_ddo_wh_block = XBeeConfigBlockDDO(self.__extended_address)
            xbee_ddo_wh_block.apply_only_to_modules((MOD_XB_ZB, MOD_XB_S2C_ZB,))
            xbee_ddo_wh_block.add_parameter('WH', sample_predelay)
            self.__xbee_manager.xbee_device_config_block_add(self,
                                    xbee_ddo_wh_block)

        # Indicate that we have no more configuration to add:
        self.__xbee_manager.xbee_device_configure(self)

        return True

    def stop(self):

        # Unregister ourselves with the XBee Device Manager instance:
        self.__xbee_manager.xbee_device_unregister(self)

        return True
        

    ## Locally defined functions:
    def running_indication(self):
        # Our device is now running, load our initial state.
        # It is okay if we take an Exception here, as the device
        # might have already gone to sleep.
        extended_address = SettingsBase.get_setting(self, "extended_address")
        try:
            io_sample = self.__xbee_manager.xbee_device_ddo_get_param(
                            extended_address, 'IS')
            self.sample_indication(io_sample, extended_address)
        except:
            pass

    def sample_indication(self, buf, addr):
        #print "XBeeDIO: Got sample indication from: %s, buf is len %d." \
        #    % (str(addr), len(buf))

        now = time.time() # we need all samples 'stamped' the same - no lag/jitter
        msg = ""
        
        io_sample = parse_is(buf)

        for io_pin in range(4):
            key = 'DIO%d' % INPUT_CHANNEL_TO_PIN[io_pin]
            if io_sample.has_key(key):
                val = bool(io_sample[key])
                name = "channel%d_input" % (io_pin+1)
                msg += ' Dio%d=' % (io_pin+1)

                # Always update the channel with the new sample value, and
                # its timestamp, even if it is the same as the previous value.
                try:
                    # Make a copy of the old values.
                    old = self.property_get(name)
                    # Set the new value.
                    self.property_set(name,  Sample(now, val, "bool"))
                    # Print out some tracing about old versus new sample value.
                    if old.timestamp == 0 or old.value != val:
                        # show value with '^' for change
                        msg += '%s^' % val
                    else:
                        # show value, no change
                        msg += '%s' % val
                except Exception, e:
                    self.__tracer.error("Exception generated: %s", str(e))

        # Low battery check (attached to DIO11/P1):
        if SettingsBase.get_setting(self, "enable_low_battery"):        
            # Invert the signal it is actually not_low_battery:
            val = not bool(io_sample["DIO11"])
            self.property_set("low_battery", Sample(now, val))
            if val: # only show if true
                msg += ' low_battery=True'
    
            # NOTE - IMPORTANT: this sample has always been reset EVERY cycle
            # not when it changes. Lynn did NOT change this, plus Modbus 
            # expects low_battery.timestamp to change to indicate the DIO
            # device is live. If low_battery channel is made option, Lynn will
            # need a new method to detect health of the DIO adapter
        
        self.__tracer.debug(msg)
        return

    def set_output(self, sample, io_pin):
        new_val = False
        try:
            new_val = bool(sample.value)
        except:
            pass
        ddo_val = 4
        if new_val:
            ddo_val = 5
        cmd = CONTROL_LINES[io_pin][OUT]
        property = "channel%d_output" % (io_pin+1)
        old_val = self.property_get(property).value

#        self.__tracer.debug("set_output(%s) value=%r (old: %r) %s=%d",
#                            (property, new_val, old_val, cmd, ddo_val))

        if new_val != old_val:
            try:
                self.__xbee_manager.xbee_device_ddo_set_param(
                    self.__extended_address, cmd, ddo_val,
                    apply=True)
            except Exception, e:
                self.__tracer.error("Error setting output '%s'", str(e))
            self.property_set(property, Sample(0, new_val, "bool"))


    def update(self, channel, io_pin):
        sample = channel.get()
        self.set_output(sample, io_pin)

# internal functions & classes

