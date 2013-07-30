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

# imports
from settings.settings_base import SettingsBase
from channels.channel_source_device_property import ChannelSourceDeviceProperty

# constants

# exception classes
class DeviceBasePropertyNotFound(KeyError):
    pass

# interface functions

# classes

class DeviceBase(SettingsBase):
    """
    Base class that any device driver must derive from.

    The :class:`DeviceBase` class is extended in order to create new
    Dia device drivers. :class:`DeviceBase` defines several properties
    and methods for use in iDigi Dia devices including a name for the
    device, a set of property channels that can be populated with
    information about the device as well as the methods for
    interacting with those channels, and virtual *start* and *stop*
    methods that must be implemented in each driver.

    Parameters:

    * *name*: the name of the device
    * *settings*: configures device settings. Used to initialize
      :class:`~settings.settings_base.SettingsBase`
    * *core_services*: The system
      :class:`~core.core_services.CoreServices` object.

    """
    def __init__(self, name, core_services, settings, properties):
        self.__name = name
        self.__settings = settings
        self.__core = core_services
        self.__properties = { }

        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        # Initialize settings:
        SettingsBase.__init__(self, binding=("devices", (name,), "settings"),
                                    setting_defs=settings)

        # Initialize properties:
        for property in properties:
            self.add_property(property)

    # def __del__(self):
    #     channel_db = \
    #         self.__core.get_service("channel_manager").channel_database_get()

    #     # Walk the pending registry, if this device is in there, remove it.
    #     try:
    #         for tmp in self._settings_global_pending_registry['devices']['instance_list']:
    #             if tmp['name'] == self.__name:
    #                 try:
    #                     self._settings_global_pending_registry['devices']['instance_list'].remove(tmp)
    #                 except Exception, e:
    #                     self.__tracer.error(e)
    #                 break
                            
    #     except Exception, e:
    #         self.__tracer.error(e)

    #     # Walk the running registry, if this device is in there, remove it.
    #     try:
    #         for tmp in self._settings_global_running_registry['devices']['instance_list']:
    #             if tmp['name'] == self.__name:
    #                 try:
    #                     self._settings_global_running_registry['devices']['instance_list'].remove(tmp)
    #                 except Exception, e:
    #                     self.__tracer.error(e)
    #                 break
                    
    #     except Exception, e:
    #         self.__tracer.error(e)

    #     # When the device goes away, we need to remove all the channels
    #     # that are in the channel database, and then we need to remove
    #     # each channel itself.
    #     self.remove_all_properties()

    #     # SettingsBase.__del__(self)

    ## These functions are inherited by derived classes and need not be changed:
    def get_name(self):
        """
        Returns the name of the device.

        """
        
        return self.__name

    def __get_property_channel(self, name):
        """
        Returns channel designated by property *name*.

        """
        
        channel_db = \
            self.__core.get_service("channel_manager").channel_database_get()

        channel_db.channel_get(self.__name + '.' + name)
        if name not in self.__properties:
            raise DeviceBasePropertyNotFound, \
                "channel device property '%s' not found." % (name)
        
        return self.__properties[name]

    def add_property(self, channel_source_device_property):
        """
        Adds a channel to the set of device properties.

        """
        channel_db = \
            self.__core.get_service("channel_manager").channel_database_get()
        channel_name = "%s.%s" % \
                        (self.__name, channel_source_device_property.name)
        channel = channel_db.channel_add(
                                    channel_name,
                                    channel_source_device_property)
        self.__properties[channel_source_device_property.name] = channel

        return channel

    def property_get(self, name):
        """
        Returns the current :class:`~samples.sample.Sample` specified
        by *name* from the devices property list.

        """
        
        channel = self.__get_property_channel(name)
        return channel.producer_get()

    def property_set(self, name, sample):
        """
        Sets property specified by the string *name* to the
        :class:`~samples.sample.Sample` object *sample* and returns
        that value.

        """
        
        channel = self.__get_property_channel(name)
        return channel.producer_set(sample)

    def property_exists(self, name):
        """
        Determines if a property specified by *name* exists.

        """
        
        if name in self.__properties:
            return True
        return False

    def property_list(self):
        """
        Returns a list of all properties for the device.

        """
        
        return [name for name in self.__properties]

    def remove_all_properties(self):
        """
        Removes all properties from the set of device properties.

        """
        
        channel_db = \
            self.__core.get_service("channel_manager").channel_database_get()

        for chan in self.__properties:
            channel_name = "%s.%s" % (self.__name, chan)
            chan_obj = channel_db.channel_remove(channel_name)
            if chan_obj:
                del chan_obj
        self.__properties = { }
        
    def remove_property(self, channel_name):
        """
        Removes all properties from the set of device properties.

        """
        
        channel_db = \
            self.__core.get_service("channel_manager").channel_database_get()
        
        flag=0
        for chan in self.__properties:
            if chan == channel_name:
                flag=1
                channel = "%s.%s" % (self.__name, channel_name)
                chan_obj = channel_db.channel_remove(channel)
                if chan_obj:
                    del chan_obj
        if(flag): del self.__properties[channel_name]

    ## These functions must be implemented by the sensor driver writer:
    def start(self):
        """
        Start the device driver.  Returns bool.

        *start* is a virtual method used to start the device. For example
        implementations of the *start* method, look at the source for the
        device drivers included with the iDigi Dia. Start should return
        a boolean value dependent on the success or failure of the method.

        """
        raise NotImplementedError, "virtual function"

    def stop(self):
        """
        Stop the device driver.  Returns bool.

        *stop* is a virtual method used to stop the device. For example
        implementations of the *stop* method, look at the source for the
        device drivers included with the iDigi Dia. Stop should return
        a boolean value dependent on the success or failure of the method.

        """
        
        raise NotImplementedError, "virtual function"


# internal functions & classes
