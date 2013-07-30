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
A Generic Dia XBee Serial Driver


To Use:
-------

This XBee Serial class is intended to be used by deriving a new class based
on this class.

This driver attempts to shield the user from the low level details
on how to set various serial settings that use cryptic AT commands.

The function calls that are intended to be used by the driver writer are:

* :py:func:`~XBeeSerial.initialize_xbee_serial`
* :py:func:`~XBeeSerial.write`
* :py:func:`~XBeeSerial.set_baudrate`
* :py:func:`~XBeeSerial.get_baudrate`
* :py:func:`~XBeeSerial.set_parity`
* :py:func:`~XBeeSerial.get_parity`
* :py:func:`~XBeeSerial.set_stopbits`
* :py:func:`~XBeeSerial.get_stopbits`
* :py:func:`~XBeeSerial.set_hardwareflowcontrol`
* :py:func:`~XBeeSerial.get_hardwareflowcontrol`

When deriving from this class, the user should be aware of 2 things:

1. During your 'start' function, you should declare a ddo config block,
   then pass that config block into the
   :py:func:`~XBeeSerial.initialize_xbee_serial` function.

   This class will add commands to your config block to set up the
   serial parameters.

   For example::

       xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)
       XBeeSerial.initialize_xbee_serial(self, xbee_ddo_cfg)
       self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

2. The user needs to declare a 'read_callback' function.
   Whenever serial data is received, this driver will forward this data
   to the derived class that has this function declared.


Settings:
---------

* **baudrate:** Optional parameter. Acceptable integer baud rates are from
  8 through 921600. If not set, the default value of 9600 will be used.
* **parity:** Optional parameter. Acceptable parity values are the follow
  strings:

    * none
    * even
    * odd
    * mark
    
    If not set, the default value of 'none' will be used.
* **stopbits:** Optional parameter. Acceptable stopbit values are:

    * 1
    * 2
    
    If not set, the default value of 1 will be used.
    
    .. Note::
        Not all XBee/ZigBee Serial firmware supports setting the stop bit 
        value. In these cases, the stop bit will always be 1.

* **hardwareflowcontrol:** Optional parameter. Acceptable hardware flow 
  control values are:

    * **True:** Will set RTS/CTS flow control.
    * **False:** Will turn OFF RTS/CTS flow control.
    
    If not set, the default value of False will be used.

* **enable_low_battery:** Optional parameter. Force an adapter to enable support
  for battery-monitor pin. It should be only enabled if adapter is using 
  internal batteries. Acceptable enable low battery values are:

    * **On:** Will turn ON low battery.
    * **Off:** Will turn OFF low battery.

    If not set, the default value of Off will be used.

"""

# imports
import struct
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from common.types.boolean import Boolean, STYLE_ONOFF
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
    import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import PROD_DIGI_XB_ADAPTER_RS232, \
    PROD_DIGI_XB_ADAPTER_RS485

# constants

# exception classes

# interface functions

# classes
class XBeeSerial(XBeeBase):
    """\
        A Generic XBee Serial base class.

        This class allows a user to build upon it to create their
        own driver for an XBee serial based device.

        Keyword arguments: 

            * **name:** The name of the XBee device instance.  
            * **core_services:** The Core Services instance.  
            * **settings:** The list of settings.  
            * **properties:** The list of properties.  

    """

    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [ [0xe8, 0xc105, 0x11], [0xe8, 0xc105, 0x92] ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ PROD_DIGI_XB_ADAPTER_RS232, PROD_DIGI_XB_ADAPTER_RS485, ]

    BAUD_RATES = {
        1200:   0,
        2400:   1,
        4800:   2,
        9600:   3,
        19200:  4,
        38400:  5,
        57600:  6,
        115200: 7, }

    def __init__(self, name, core_services, settings, properties):
        self.__name = name
        self.__core = core_services

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local State Variables:

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='baudrate', type=int, required=False,
                default_value=9600,
                verify_function=self.__verify_baudrate),
            Setting(
                name='parity', type=str, required=False,
                default_value='none',
                verify_function=self.__verify_parity),
            Setting(
                name='stopbits', type=int, required=False,
                default_value=1,
                verify_function=self.__verify_stopbits),
            Setting(
                name='hardwareflowcontrol', type=bool, required=False,
                default_value=False),
                
            # These settings are provided for advanced users, they are not required:
            Setting(
                name='enable_low_battery', type=Boolean, required=False,
                default_value=Boolean("Off", STYLE_ONOFF)),                            
        ]

        # Add our settings_list entries to the settings passed to us.
        settings.extend(settings_list)


        ## Channel Properties Definition:
        property_list = [

        ]

        # Add our property_list entries to the properties passed to us.
        properties.extend(property_list)

        ## Initialize the XBeeBase interface:
        XBeeBase.__init__(self, self.__name, self.__core, settings,
                          properties)


    ## Functions which must be implemented to conform to the XBeeSerial
    ## interface:
            
    def read_callback(self):
        raise NotImplementedError, "virtual function"


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
        probe_data = XBeeBase.probe()

        for address in XBeeSerial.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeSerial.SUPPORTED_PRODUCTS:
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
        raise NotImplementedError, "virtual function"


    def start(self):
        """Start the device driver.  Returns bool."""
        raise NotImplementedError, "virtual function"


    def stop(self):
        """Stop the device driver.  Returns bool."""
        raise NotImplementedError, "virtual function"


    ## Locally defined functions:

    def initialize_xbee_serial(self, xbee_ddo_cfg):
        """\
Creates a DDO command sequence of the user selected serial settings. Forces an
adapter to enable support for battery-monitor pin, too. It is only enabled if 
adapter is using internal batteries.

.. Note::
    * During your 'start' function, you should declare a ddo config block,
      then pass that config block into this function.
    * This function will add commands to your config block to set up the
      serial parameters and to enable support for battery-monitor pin if only 
      adapter is using internal batteries.

For example::
    xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)
    XBeeSerial.initialize_xbee_serial(self, xbee_ddo_cfg)
    self.__xbee_manager.xbee_device_config_block_add(self, xbee_ddo_cfg)

Returns True if successful, False on failure.
        """

        # Fetch the XBee Manager name from the Settings Manager:
        xbee_manager_name = SettingsBase.get_setting(self, "xbee_device_manager")
        dm = self.__core.get_service("device_driver_manager")
        self.__xbee_manager = dm.instance_get(xbee_manager_name)

        # Get the extended address of the device:
        extended_address = SettingsBase.get_setting(self, "extended_address")

        # Create a callback specification for our device address, endpoint
        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec.cb_set(self.__read_callback)
        xbdm_rx_event_spec.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x11),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec)

        # Digi XBee profile and sample cluster id:
        xbdm_rx_event_spec2 = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec2.cb_set(self.__sample_indication)
        xbdm_rx_event_spec2.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x92),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec2)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)

        # Set up the baud rate for the device.
        try:
            baud = SettingsBase.get_setting(self, "baudrate")
        except:
            baud = 9600
        baud = self.__derive_baudrate(baud)
        xbee_ddo_cfg.add_parameter('BD', baud)

        # Set up the parity for the device.
        try:
            parity = SettingsBase.get_setting(self, "parity")
        except:
            parity = 'none'
        parity =  self.__derive_parity(parity)
        xbee_ddo_cfg.add_parameter('NB', parity)

        # Set up the stop bits for the device.
        try:
            stopbits = SettingsBase.get_setting(self, "stopbits")
        except:
            stopbits = 1
        stopbits = self.__derive_stopbits(stopbits)
        # The SB command is new.
        # It may or may not be supported on the XBee Serial Device/Adapter.
        # If its not supported, then we know the device
        # is simply at 1 stop bit, and we can ignore the failure.
        xbee_ddo_cfg.add_parameter('SB', stopbits,
                                   failure_callback=self.__ignore_if_fail)

        # Set up the hardware flow control mode for the device.
        try:
            hwflow = SettingsBase.get_setting(self, "hardwareflowcontrol")
        except:
            hwflow = False
        rtsflow, ctsflow = self.__derive_hardwareflowcontrol(hwflow)
        xbee_ddo_cfg.add_parameter('D6', rtsflow)
        xbee_ddo_cfg.add_parameter('D7', ctsflow)

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
            self.__tracer.info("Adapter is not using internal batteries")

        ic = 0        
        xbee_ddo_cfg.add_parameter('IC', ic)

        return True

    def write(self, data):
        """\
Writes a buffer of data out the XBee.

Returns True if successful, False on failure.
        """

        ret = False
        extended_address = SettingsBase.get_setting(self, "extended_address")
        addr = (extended_address, 0xe8, 0xc105, 0x11)
        try:
            self.__xbee_manager.xbee_device_xmit(0xe8, data, addr)
            ret = True
        except:
            pass
        return ret

    def set_baudrate(self, baud):
        """\
Sets the baud rate.

.. Note::
    * Acceptable values are 8 through 921600.
    * Direct values are the following:

        * 1200
        * 2400
        * 4800
        * 9600
        * 19200
        * 38400
        * 57600
        * 115200
    * If a baud rate is specified that is NOT in the above list,
      the XBee firmware will pick the closest baud rate that it
      is able to support.
    * A call to get_baudrate() will allow the caller to determine
      the real value the firmware was able to support.

Returns True if successful, False on failure.
        """

        ret = False
        ext_addr = SettingsBase.get_setting(self, "extended_address")
        baud = self.__derive_baudrate(baud)
        try:
            self.__xbee_manager.xbee_device_ddo_set_param(ext_addr, 'BD', baud)
            ret = True
        except:
            pass
        return ret

    def get_baudrate(self):
        """\
Returns the baud rate the device is currently set to, 0 on failure.
        """

        ext_addr = SettingsBase.get_setting(self, "extended_address")
        try:
            baud = self.__xbee_manager.xbee_device_ddo_get_param(ext_addr, 'BD')
            baud = self.__decode_baudrate(baud)
        except:
            self.__tracer.error("Failed to retrieve baudrate from device.")
            baud = 0
        return baud

    def set_parity(self, parity):
        """\
Sets the parity.

.. Note::
    Acceptable parity values are:
    * none
    * even
    * odd
    * mark

Returns True if successful, False on failure.
        """

        ret = False
        ext_addr = SettingsBase.get_setting(self, "extended_address")
        parity = self.__derive_parity(parity)
        try:
            self.__xbee_manager.xbee_device_ddo_set_param(ext_addr, 'NB', parity)
            ret = True
        except:
            pass
        return ret

    def get_parity(self):
        """\
Returns the parity value the device is currently set to.
        """

        ext_addr = SettingsBase.get_setting(self, "extended_address")
        try:
            par = self.__xbee_manager.xbee_device_ddo_get_param(ext_addr, 'NB')
            par = self.__decode_parity(par)
        except:
            self.__tracer.error("Failed to retrieve parity value from device.")
            par = 'none'
        return par

    def set_stopbits(self, stopbits):
        """\
Sets the number of stop bits.

.. Note::
    * Acceptable parity values are 1 or 2.
    * The SB command is new.
    * It may or may not be supported on the XBee Serial Device/Adapter.
    * If its not supported, then we know the device is simply at
      1 stop bit, and we can ignore the failure.

Returns  True if successful, False on failure.
        """

        ret = False
        ext_addr = SettingsBase.get_setting(self, "extended_address")
        stopbits = self.__derive_stopbits(stopbits)
        try:
            self.__xbee_manager.xbee_device_ddo_set_param(ext_addr, 'SB', stopbits)
            ret = True
        except:
            pass
        return ret

    def get_stopbits(self):
        """\
Returns the number of stop bits the device is currently set to.

.. Note:: 
    * The SB command is new.
    * It may or may not be supported on the XBee Serial Device/Adapter.
    * If its not supported, then we know the device is simply at
      1 stop bit, and we can ignore the failure.

Returns 1 or 2 on success, 1 on failure.
        """

        ext_addr = SettingsBase.get_setting(self, "extended_address")
        try:
            sb = self.__xbee_manager.xbee_device_ddo_get_param(ext_addr, 'SB')
            sb = self.__decode_stopbits(sb)
        except:
            self.__tracer.error("Failed to retrieve stopbits "+ 
                                "value from device.")
            sb = 1
        return sb

    def set_hardwareflowcontrol(self, hwflow):
        """\
Sets whether hardware flow control (RTS and CTS) should be set.

.. Note::
    Acceptable parity values are:
    * True
    * False

Returns True if successful, False on failure.
        """

        ret = False
        ext_addr = SettingsBase.get_setting(self, "extended_address")
        rtsflow, ctsflow = self.__derive_hardwareflowcontrol(hwflow)
        try:
            self.__xbee_manager.xbee_device_ddo_set_param(ext_addr, 'D6', rtsflow)
            ret = True
        except:
            pass

        if ret == False:
            return False
        ret = False

        try:
            self.__xbee_manager.xbee_device_ddo_set_param(ext_addr, 'D7', ctsflow)
            ret = True
        except:
            pass
        return ret

    def get_hardwareflowcontrol(self):
        """\
Returns whether the device is currently set to do hardware flow 
control, False on failure
        """

        ext_addr = SettingsBase.get_setting(self, "extended_address")
        try:
            rts = self.__xbee_manager.xbee_device_ddo_get_param(ext_addr, 'D6')
            cts = self.__xbee_manager.xbee_device_ddo_get_param(ext_addr, 'D7')
            hwflow = self.__decode_hardwareflowcontrol(rts, cts)
        except:
            self.__tracer.error("Failed to retrieve hardware flowcontrol " + 
                                "value from device.")
            hwflow = False
        return hwflow


    # Internal class functions - Not to be used outside of this class.

    def __verify_baudrate(self, baud):
        if baud > 7 and baud <= 921600:
            return
        raise ValueError, "Invalid baud rate '%s': The value must be above 7 and equal or less than 921600" % \
            (baud)


    def __verify_parity(self, parity):
        p = parity.lower()
        if p == 'none' or p == 'even' or p != 'odd' or p != 'mark':
            return
        raise ValueError, "Invalid parity '%s': The value must be either \'none\', \'even\', \'odd\', \'mark\'"


    def __verify_stopbits(self, stopbits):
        if stopbits == 1 or stopbits == 2:
            return
        raise ValueError, "Invalid stopbits '%s': The value must be either \'1\' or \'2\'"


    def __derive_baudrate(self, baud):
        # Attempt to figure out the baud rate as one of the direct bauds the
        # firmware supports.
        # If we can't, we can tell the unit the baud rate we really want,
        # and it will attempt to pick the closest baud rate it can actually do.
        try:
            baud = self.BAUD_RATES[baud]
        except:
            pass
        return baud


    def __decode_baudrate(self, baud):
        baud = struct.unpack("I", baud)
        baud = baud[0]

        # If baud is above 8, we have the actual baud rate already.
        if baud > 8:
            return baud

        # Otherwise, the baud has to be looked up in our table.
        for i, j in self.BAUD_RATES.iteritems():
           if j == baud:
               return i

        return baud


    def __derive_parity(self, parity):
        parity = parity.lower()
        if parity == 'none':
            parity = 0
        elif parity == 'even':
            parity = 1
        elif parity == 'odd':
            parity = 2
        elif parity == 'space':
            parity = 3
        else:
            parity = 0
        return parity


    def __decode_parity(self, parity):
        parity = struct.unpack("B", parity)
        parity = parity[0]
        if parity == 0:
           return 'none'
        elif parity == 1:
           return 'even'
        elif parity == 2:
           return 'odd'
        elif parity == 3:
           return 'space'
        else:
           return 'none'


    def __derive_stopbits(self, stopbits):
        if stopbits == 1:
           stopbits = 0
        elif stopbits == 2:
           stopbits = 1
        else:
           stopbits = 0
        return stopbits


    def __decode_stopbits(self, stopbits):
        stopbits = struct.unpack("B", stopbits)
        stopbits = stopbits[0]
        if stopbits == 0:
           return 1
        elif stopbits == 1:
           return 2
        else:
           return 1


    def __derive_hardwareflowcontrol(self, hwflow):
        if hwflow:
            rtsflow = 1
            ctsflow = 1
        else:
            rtsflow = 0
            ctsflow = 0

        return rtsflow, ctsflow


    def __decode_hardwareflowcontrol(self, rtsflow, ctsflow):
        rtsflow = struct.unpack("B", rtsflow)
        rtsflow = rtsflow[0]
        ctsflow = struct.unpack("B", ctsflow)
        ctsflow = ctsflow[0]
        if rtsflow == 1 and ctsflow == 1:
            return True
        else:
            return False


    def __read_callback(self, buf, addr):
        self.__tracer.debug("Got sample indication from: %s, buf is len %d.",
                            str(addr), len(buf))

        self.read_callback(buf)


    def __sample_indication(self, buf, addr):
        # Parse the I/O sample:
        io_sample = parse_is(buf)

        # Low battery check (attached to DIO11/P1):
        if SettingsBase.get_setting(self, "enable_low_battery"):
            # Invert the signal it is actually not_low_battery:
            low_battery = not bool(io_sample["DIO11"])
            self.property_set("low_battery", Sample(0, low_battery))


    def __ignore_if_fail(self, mnemonic, value):
        return True



# internal functions & classes

