"""\
A XBee_Transfer_device for the iDigi_Dia Platform.  This device driver serves as an extraction
device from Series 2 Digi Radios devices.

Devepoled in January, 2013 
@author: eng. Nikolay Jivkov, master student at Technical University of Sofia, branch Plovdiv
email: nikolaijivkov@gmail.com
"""

# imports
from devices.xbee.xbee_devices.xbee_base import XBeeBase
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo \
import XBeeConfigBlockDDO
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs \
    import *
from devices.xbee.common.addressing import *
from devices.xbee.common.io_sample import parse_is
from devices.xbee.common.prodid import PROD_DIGI_UNSPECIFIED, \
    PROD_DIGI_XB_WALL_ROUTER, PROD_DIGI_XB_SENSOR_LT , PROD_DIGI_XB_SENSOR_LTH, \
    PROD_DIGI_XB_ADAPTER_RS232, PROD_DIGI_XB_ADAPTER_RS485

from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
import time
import sys, os
from binascii import hexlify, unhexlify

class ZigBeeTransferDevice(XBeeBase, threading.Thread):

    # Define a set of endpoints that this device will send in on.
    ADDRESS_TABLE = [ [0xe8, 0xc105, 0x92], [0xe8, 0xc105, 0x11] ]

    # The list of supported products that this driver supports.
    SUPPORTED_PRODUCTS = [ 
        PROD_DIGI_UNSPECIFIED, 
        PROD_DIGI_XB_WALL_ROUTER, 
        PROD_DIGI_XB_SENSOR_LT, 
        PROD_DIGI_XB_SENSOR_LTH,
        PROD_DIGI_XB_ADAPTER_RS232,
        PROD_DIGI_XB_ADAPTER_RS485
    ]

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        self.__xbee_manager = None
        
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        # Settings:
        #
        # xbee_device_manager: must be set to the name of an XBeeDeviceManager
        #                      instance.
        # extended_address: is the extended address of the XBee device you
        #                   would like to monitor.
        # sample_rate_ms:   is the sample rate of the XBee device.

        settings_list = [
            Setting(
                name='xbee_device_manager', type=str, required=False,
                default_value=''),
            Setting(
                name='extended_address', type=str, required=False,
                default_value=''),
            Setting(
                name='sample_rate_ms', type=int, required=False,
                default_value=2000,
                verify_function=lambda x: x > 0 and x < 0xffff),
            Setting(
                name='channel_settings', type=str, required=False,
                default_value="name,unit"),
        ]
        ## Channel Properties Definition:
        property_list = []
                                            
        ## Initialize the DeviceBase interface:
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

        for address in ZigBeeTransferDevice.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in ZigBeeTransferDevice.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:
    def apply_settings(self):

        SettingsBase.merge_settings(self)
        accepted, rejected, not_found = SettingsBase.verify_settings(self)

        if len(rejected) or len(not_found):
            # there were problems with settings, terminate early:
            return (accepted, rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)
    
    def start(self):
        """Start the device driver.  Returns bool."""
        print "Starting xbee_using_transfer_device"
        try:
            self.ch_name, self.ch_unit = SettingsBase.get_setting(self, "channel_settings").split(',')
        except:
            self.ch_name, self.ch_unit = 'name', 'unit'
        
        self.add_property(
            ChannelSourceDeviceProperty(name=self.ch_name, type=str,
                initial=Sample(timestamp=0, value="", unit=self.ch_unit),
                perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP
            )
        )
        
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
        xbdm_rx_event_spec_92 = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec_92.cb_set(self._sample_indication_92)
        xbdm_rx_event_spec_92.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x92),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec_92)
        
        xbdm_rx_event_spec_11 = XBeeDeviceManagerRxEventSpec()
        xbdm_rx_event_spec_11.cb_set(self._sample_indication_11)
        xbdm_rx_event_spec_11.match_spec_set(
            (extended_address, 0xe8, 0xc105, 0x11),
            (True, True, True, True))
        self.__xbee_manager.xbee_device_event_spec_add(self,
                                xbdm_rx_event_spec_11)
        # Create a DDO configuration block for this device:
        xbee_ddo_cfg = XBeeConfigBlockDDO(extended_address)

        # Get the gateway's extended address:
        gw_xbee_sh, gw_xbee_sl = gw_extended_address_tuple()

        # Set the destination for I/O samples to be the gateway:
        xbee_ddo_cfg.add_parameter('DH', gw_xbee_sh)
        xbee_ddo_cfg.add_parameter('DL', gw_xbee_sl)
        # Register this configuration block with the XBee Device Manager:
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
    def _sample_indication_92(self, buf, addr):
        #print '_sample_indication_92'
        try: 
            data = hexlify(str(buf))
        except Exception, e : print e
        self.property_set(self.ch_name, Sample(0, str(data), self.ch_unit))
    
    def _sample_indication_11(self, buf, addr):
        #print '_sample_indication_11'
        try: 
            data = hexlify(str(buf))
        except Exception, e : print e
        self.property_set(self.ch_name, Sample(0, str(data), self.ch_unit))
        
    def get_properties(self):
        cm = self.__core.get_service("channel_manager")
        cd = cm.channel_database_get()
        return cd.channel_list()
# internal functions & classes

def main():
    pass

if __name__ == '__main__':
    import sys
    status = main()
    sys.exit(status)
