############################################################################
#                                                                          #
# Copyright (c)2008,2009 Digi International (Digi). All Rights Reserved.   #
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
'''\
This module is not intended for production use. It is a tool for testing
yml 'tracing' block configurations.
'''

# imports
from devices.device_base import DeviceBase
from core.tracing import get_tracer

from channels.channel_source_device_property import DPROP_PERM_GET, \
     DPROP_PERM_SET, DPROP_PERM_REFRESH, Sample, ChannelSourceDeviceProperty

# classes

class TracerTestDevice(DeviceBase):
    '''\
    This device is useful for testing tracer configuration. It simply
    presents an easy interface for creating arbitrary trace messages
    at all the different levels.
    '''

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.__tracer = get_tracer(name)
        
        settings_list = []

        ## Channel Properties Definition:
        property_list = [
            ChannelSourceDeviceProperty(name='critical',
                                         type=str,
                                         initial=Sample(value=''),
                                         perms_mask=DPROP_PERM_GET | \
                                         DPROP_PERM_SET | \
                                         DPROP_PERM_REFRESH,
                                        set_cb = \
                                        lambda x: \
                                        self.__tracer.critical(x.value)), 



            ChannelSourceDeviceProperty( name='error',
                                         type=str,
                                         initial=Sample(value=''),
                                         perms_mask=DPROP_PERM_GET|\
                                         DPROP_PERM_SET|\
                                         DPROP_PERM_REFRESH,
                                         set_cb = \
                                         lambda x: \
                                         self.__tracer.error(x.value)),

            ChannelSourceDeviceProperty( name='warning',
                                         type=str,
                                         initial=Sample(value=''),
                                         perms_mask=DPROP_PERM_GET|\
                                         DPROP_PERM_SET|\
                                         DPROP_PERM_REFRESH,
                                         set_cb = \
                                         lambda x: \
                                         self.__tracer.warning(x.value)),
                                         
            ChannelSourceDeviceProperty( name='info',
                                         type=str,
                                         initial=Sample(value=''),
                                         perms_mask=DPROP_PERM_GET|\
                                         DPROP_PERM_SET|\
                                         DPROP_PERM_REFRESH,
                                         set_cb = \
                                         lambda x: \
                                         self.__tracer.info(x.value)),
                                         
            ChannelSourceDeviceProperty( name='debug',
                                         type=str,
                                         initial=Sample(value=''),
                                         perms_mask=DPROP_PERM_GET|\
                                         DPROP_PERM_SET|\
                                         DPROP_PERM_REFRESH,
                                         set_cb = \
                                         lambda x: \
                                         self.__tracer.debug(x.value)),
        ]


        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

    def start(self):
        return True

    def stop(self):
        return True

