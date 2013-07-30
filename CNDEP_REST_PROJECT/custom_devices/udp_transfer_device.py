"""\
A UDP_Transfer_device for the iDigi_Dia Platform.

Devepoled in January, 2013 
@author: eng. Nikolay Jivkov, master student at Technical University of Sofia, branch Plovdiv
email: nikolaijivkov@gmail.com
"""

# imports
from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
import time
import sys, os
from binascii import hexlify, unhexlify
from socket import *
from crypto.cipher.aes import AES
from crypto.cipher.base import noPadding, padWithPadLen
from binascii import a2b_hex, b2a_hex, hexlify, unhexlify

class UDPTransferDevice(DeviceBase, threading.Thread):

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        settings_list = [
            Setting(
                name='extended_address', type=str, required=False,
                default_value=''),
            Setting(
                name='sample_rate_ms', type=int, required=False),
            Setting(
                name='channel_settings', type=str, required=False,
                default_value="name,unit"),
            Setting(
                name='encryption', type=bool, required=False,
                default_value=False)
        ]
        ## Channel Properties Definition:
        property_list = []
        
        ## Initialize the DeviceBase interface:
        DeviceBase.__init__(self, self.__name, self.__core, settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)
        
    ## Functions which must be implemented to conform to the XBeeBase
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
        try:
            self.ip, self.port=SettingsBase.get_setting(self, "extended_address").split(':')
            self.port=int(self.port)
        except: 
            print 'error!'
        
        try:
            self.ch_name, self.ch_unit = SettingsBase.get_setting(self, "channel_settings").split(',')
        except:
            self.ch_name, self.ch_unit = 'name', 'unit'
        self.add_property(
            ChannelSourceDeviceProperty(name=self.ch_name, type=str,
                initial=Sample(timestamp=0, value="", unit=self.ch_unit),
                perms_mask=(DPROP_PERM_GET),
                options=DPROP_OPT_AUTOTIMESTAMP,
            )
        )
        
        threading.Thread.start(self)
        
        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""
        self.__stopevent.set()
        time.sleep(1)
        try:
            self.sd.close()
        except:
            pass
        return True
    
    def run(self):
        """run when our device driver thread is started"""
        enc = SettingsBase.get_setting(self, "encryption")
        if enc:
            enc_key = '%016x' % 0x1234
            kSize = len(enc_key)
            aes = AES(enc_key, keySize=kSize, padding=padWithPadLen())
            
        self.sd = socket(AF_INET, SOCK_DGRAM)
        self.sd.bind((self.ip, self.port))
        self.sd.setblocking(0)
        
        while self.__stopevent.isSet()==False:
            while self.__stopevent.isSet()==False:
                try:
                    buf, addr = self.sd.recvfrom(255)
                    break
                except:
                    time.sleep(0.01)
            try:
                data=str(buf)
            except:
                data='data error'
            if enc:
                data=aes.decrypt(data)
            
            self.property_set(self.ch_name, Sample(0, str(data), self.ch_unit))
                
                
        self.__stopevent.clear()
        
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
