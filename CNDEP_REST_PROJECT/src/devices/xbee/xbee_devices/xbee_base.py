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
    The XBee sensor interface base class.

    All XBee sensor drivers in Dia should derive from this class.

"""

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import ChannelSourceDeviceProperty

# constants

# exception classes

# interface functions

# classes

class XBeeBase(DeviceBase):

    """\
        Defines the XBee Interface base class.

        Keyword arguments:
            * **name:** the name of the device instance.
            * **core_services:** the core services instance.
            * **settings:** the list of settings.
            * **properties:** the list of properties.

    """
    # Define a set of default endpoints that devices will send in on.
    # When a XBee Node Joins our network, it will come in on 0x95.
    ADDRESS_TABLE = [ [ 0xe8, 0xc105, 0x95 ] ]

    # Empty list of supported products.
    SUPPORTED_PRODUCTS = []

    def __init__(self, name, core_services, settings, properties):
        self.__name = name
        self.__core = core_services
        ## Local State Variables:
        self.__xbee_manager = None

        ## Settings Table Definition:
        settings_list = [
            Setting(
                name = 'xbee_device_manager', type = str, required = True),
            Setting(
                name = 'extended_address', type = str, required = True),
        ]

        # Add our settings_list entries to the settings passed to us.
        #
        # NOTE: If the settings passed to us contain a setting that
        #       is of the same name as one of ours, we will use the
        #        passed in setting, and throw ours away.

        for our_setting in settings_list:
            for setting in settings:
                if our_setting.name == setting.name:
                    break
            else:
                settings.append(our_setting)

        ## Channel Properties Definition:
        property_list = [

        ]

        # Add our property_list entries to the properties passed to us.
        properties.extend(property_list)

        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings, properties)


    ## These functions must be implemented by the sensor driver writer:
    def apply_settings(self):
        """\
            Called when new configuration settings are available.

            Should be overridden by the derived class.

        """
        raise NotImplementedError, "virtual function"
 
    def start(self):
        """\
            Start the device driver.

            Should be overridden by the derived class.

        """

        raise NotImplementedError, "virtual function"

    def stop(self):
        """\
            Stop the device driver.

            Should be overridden by the derived class.

        """

        raise NotImplementedError, "virtual function"

    @staticmethod
    def probe():
        """\
            Collect important information about the driver.

            .. Note::

                This method is a static method.  As such, all data returned
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

        probe_data = dict(address_table = [], supported_products = [])

        for address in XBeeBase.ADDRESS_TABLE:
            probe_data['address_table'].append(address)
        for product in XBeeBase.SUPPORTED_PRODUCTS:
            probe_data['supported_products'].append(product)

        return probe_data                                               


# internal functions & classes

