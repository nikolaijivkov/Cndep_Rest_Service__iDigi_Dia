"""\
CNDEP Restful Web Service.    
Provide a meaning to do Restful oriented service, capable of extracting sensor data (real or emulated) and converting that data in simple xml.
Operations below are managed in a Restful way:
  GET    - extract data from sensors on one or multiple devices on the list and convert that data in simple xml;
  PUT    - add sensor device to the list of devices;
  POST   - edit existing device in the list;/remove sensor devices (real or emulated);
  DELETE - remove sensor device from the list of devices.
PUT, POST, GET and DELETE are http methods used for the current operation.
for more accurate description try [ip]:[port]/cndep/description once the service is started.
  
Created on April, 2012
Last update on Match, 2013 
@author: eng. Nikolay Jivkov, master student at Technical University of Sofia, branch Plovdiv
email: nikolaijivkov@gmail.com

device_type can be: xbee_sensor, xbee_wall_router, ecg, spo2, bp, rr, bg, bt.
#===============================================================
METHOD: GET
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/help
URL: http://192.168.2.106:8080/cndep/description
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/list
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/all
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/id_from_name/{device_name}
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/{device_id}
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/{device_id}/{channel_name}

#===============================================================
METHOD: PUT
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device

Body:
<?xml version="1.0" ?>
<request>
    <device id='1' name='new_device' type='ecg' mac='01:23:45:67:89:ab:cd:ef!' sample_rate='5.0'/>
</request>
<request>
    <device id='1' name='new_device' type='ecg' mac='10.10.101.0:1234' sample_rate='5.0'/>
</request>
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/{channel_name}
Body:
<?xml version="1.0" ?>
<request>
    <sensor unit='hex'/>
</request>
_or_
<request>
    <sensor/>
</request>

#===============================================================
METHOD: POST
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device

Body:
<?xml version="1.0" ?>
<request>
    <device id='1' id_new='5' name='new_device' type='ecg' mac='01:23:45:67:89:ab:cd:ef!' sample_rate='5.0'/>
</request>
_or_
<request>
    <device id='1' id_new='5' name='new_device' type='ecg' mac='10.10.101.0:1234' sample_rate='5.0'/>
</request>
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/{device_id}/{channel_name}
Body:
<?xml version="1.0" ?>
<request>
    <sensor value='123' unit='hex'/>
</request>
_or_
<request>
    <sensor value='123'/>
</request>
#===============================================================
METHOD: DELETE
#---------------------------------------------------------------
URL: http://192.168.2.106:8080/cndep/device/{id}
"""
# imports for forcing bulder to build modules
try: import custom_devices.xbee_transfer_device
except: pass
try: import custom_devices.udp_transfer_device
except: pass
try: import custom_devices.hr_spo2_device
except: pass
try: import devices.xbee.xbee_devices.xbee_xbr
except: pass
try: import devices.xbee.xbee_devices.xbee_sensor
except: pass
try: import devices.xbee.xbee_device_manager.xbee_device_manager
except: pass

# imports
import traceback
from devices.device_base import DeviceBase
from services.service_base import ServiceBase
from settings.settings_base import SettingsBase, Setting
from channels.channel_source_device_property import *
from channels.channel import \
    PERM_GET, PERM_SET, PERM_REFRESH, \
    OPT_AUTOTIMESTAMP, OPT_DONOTLOG, OPT_DONOTDUMPDATA
from samples.sample import Sample
import threading
import time, datetime
import urllib
from itty import *
import etree.ElementTree as ET
import sys

if sys.platform.startswith('digi'):
    dev_list_path = 'WEB/python/'
else:
    dev_list_path = 'C:/'
sys.path.append(dev_list_path)
try:
    from device_list import device_list
except:
    print "DEVICE LIST is empty!!!"
    device_list = {}
    '''
        '1': {'type': 'xbee_sensor', 'name': 'Xbee_device_1', 'mac':'mac address 1', 'sample_rate': 30.0},
        '2': {'type': 'xbee_wall_router', 'name': 'Xbee_device_2', 'mac':'mac address 2', 'sample_rate': 10.0},
        '3': {'type': 'ecg', 'name': 'Xbee_device_3', 'mac':'mac address 3', 'sample_rate': 5.0},
    '''

#driver names (like 'xbee_sensor') MUST be only lower case in Driver_map dict!!!
Driver_map = {
    #Digi Devices:
    'xbee_sensor':{
        'path':'devices.xbee.xbee_devices.xbee_sensor:XBeeSensor',
        'settings':'xbee_device_manager, sample_rate_ms'},
    'xbee_wall_router':{
        'path':'devices.xbee.xbee_devices.xbee_xbr:XBeeXBR',
        'settings':'xbee_device_manager, sample_rate_ms'},
    #Medical devices:
    #Hearth_Rate and SPO2 real device
    'hr_spo2_device':{
        'path':'custom_devices.hr_spo2_device:HrSpo2Device',
        'settings':'sample_rate_ms'},
    #ECG emulation
    'ecg_zb':{
        'path':'custom_devices.xbee_transfer_device:ZigBeeTransferDevice',
        'settings':'xbee_device_manager, sample_rate_ms, channel_settings',
        'channel_settings':'ECG,mV'},
    'ecg_udp':{
        'path':'custom_devices.udp_transfer_device:UDPTransferDevice',
        'settings':'sample_rate_ms, channel_settings',
        'channel_settings':'ECG,mV'},
    #Heart_Rate emulation
    'hr_zb':{
        'path':'custom_devices.xbee_transfer_device:ZigBeeTransferDevice',
        'settings':'xbee_device_manager, sample_rate_ms, channel_settings',
        'channel_settings':'HR,BPM'},
    'hr_udp':{
        'path':'custom_devices.udp_transfer_device:UDPTransferDevice',
        'settings':'sample_rate_ms, channel_settings',
        'channel_settings':'HR,BPM'},
    #Oxigen_Saturation emulation
    'spo2_zb':{
        'path':'custom_devices.xbee_transfer_device:ZigBeeTransferDevice',
        'settings':'xbee_device_manager, sample_rate_ms, channel_settings',
        'channel_settings':'SpO2,%'},
    'spo2_udp':{
        'path':'custom_devices.udp_transfer_device:UDPTransferDevice',
        'settings':'sample_rate_ms, channel_settings',
        'channel_settings':'SpO2,%'},
    #Respiratory_Rate emulation
    'rr_zb':{
        'path':'custom_devices.xbee_transfer_device:ZigBeeTransferDevice',
        'settings':'xbee_device_manager, sample_rate_ms, channel_settings',
        'channel_settings':'RR,BPM'},
    'rr_udp':{
        'path':'custom_devices.udp_transfer_device:UDPTransferDevice',
        'settings':'sample_rate_ms, channel_settings',
        'channel_settings':'RR,BPM'},
    #Blood_Glucose emulation
    'bg_zb':{
        'path':'custom_devices.xbee_transfer_device:ZigBeeTransferDevice',
        'settings':'xbee_device_manager, sample_rate_ms, channel_settings',
        'channel_settings':'BG,mmol/l'},
    'bg_udp':{
        'path':'custom_devices.udp_transfer_device:UDPTransferDevice',
        'settings':'sample_rate_ms, channel_settings',
        'channel_settings':'BG,mmol/l'},
    #Body_Temperature emulation
    'bt_zb':{
        'path':'custom_devices.xbee_transfer_device:ZigBeeTransferDevice',
        'settings':'xbee_device_manager, sample_rate_ms, channel_settings',
        'channel_settings':'BT,°C'},
    'bt_udp':{
        'path':'custom_devices.udp_transfer_device:UDPTransferDevice',
        'settings':'sample_rate_ms, channel_settings',
        'channel_settings':'BT,°C'},
    #Blood_Pressure emulation
    'bp_zb':{
        'path':'custom_devices.xbee_transfer_device:ZigBeeTransferDevice',
        'settings':'xbee_device_manager, sample_rate_ms, channel_settings',
        'channel_settings':'Systolic/Diastolic,mmHg'},
    'bp_udp':{
        'path':'custom_devices.udp_transfer_device:UDPTransferDevice',
        'settings':'sample_rate_ms, channel_settings',
        'channel_settings':'Systolic/Diastolic,mmHg'},
    }

@error(404)
def not_found(request, exception):
    #'Not Found'
    builder = ET.TreeBuilder()
    
    builder.start('response', {'status':'404'})
    
    builder.start('message', {})
    builder.data('Not Found: ' + str(exception))
    builder.end('message')
    
    xml = builder.end('response')
    
    xml_str = ET.tostring(xml, encoding="utf8")
    response = Response(xml_str, status=404, content_type='text/xml')
    return response.send(request._start_response)

@error(409)
def conflict(request, exception):
    #'Conflict'
    builder = ET.TreeBuilder()
    
    builder.start('response', {'status':'409'})
    
    builder.start('message', {})
    builder.data('conflict: ' + str(exception))
    builder.end('message')
    
    xml = builder.end('response')
    
    xml_str = ET.tostring(xml, encoding="utf8")
    response = Response(xml_str, status=409, content_type='text/xml')
    return response.send(request._start_response)
    
@error(500)
def app_error(request, exception):
    #'Application Error'
    builder = ET.TreeBuilder()
    
    builder.start('response', {'status':'500'})
    
    builder.start('message', {})
    builder.data('application error: ' + str(exception))
    builder.end('message')
    
    xml = builder.end('response')
    
    xml_str = ET.tostring(xml, encoding="utf8")
    response = Response(xml_str, status=500, content_type='text/xml')
    return response.send(request._start_response)

Device_types = []
for i in Driver_map:
    Device_types.append(i.lower())

class Restful(ServiceBase, threading.Thread):
    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        self.xbee_device_manager_name = None
        ## Settings Table Definition:
        settings_list = [
            Setting(
                name='server_ip', type=str, required=False,
                default_value="192.168.33.106"),
            Setting(
                name='server_port', type=int, required=False,
                default_value="8080"),
        ]

        ## Channel Properties Definition:
        #property_list = [ ]
                                            
        ## Initialize the DeviceBase interface:
        ServiceBase.__init__(self, self.__name, settings_list)
        
        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        #threading.Thread.setDaemon(self, True)
        
        self.chs_last_ts = {}
        
        #self.device_list=device_list #it shoud be self.device_list so we can see it from others Classes/Objects.
        
        for i in device_list:
            device_id = i
            device_type = device_list[i].get('type').lower()
            device_name = device_list[i].get('name')
            device_mac = device_list[i].get('mac')
            device_sample_rate = device_list[i].get('sample_rate')
            
            instance_name = device_name
            driver_path = Driver_map[device_type].get('path')
            
            settings = {}
            if Driver_map[device_type].get('settings').find('xbee_device_manager') != -1:
                if(self.xbee_device_manager_name == None):
                    self.xbee_device_manager_name = 'xbee_device_manager'
                    self.driver_add('xbee_device_manager', 'devices.xbee.xbee_device_manager.xbee_device_manager:XBeeDeviceManager', settings={'worker_threads':2})
                    time.sleep(1)
                
                settings['xbee_device_manager'] = self.xbee_device_manager_name
            
            settings['extended_address'] = device_mac
            
            if Driver_map[device_type].get('settings').find('sample_rate_ms') != -1:
                if(device_sample_rate == None):
                    device_sample_rate = 30.0
                settings['sample_rate_ms'] = int(float(device_sample_rate) * 1000)
            
            elif Driver_map[device_type].get('settings').find('sample_rate_sec') != -1:
                if(device_sample_rate == None):
                    device_sample_rate = 1.0
                settings['sample_rate_sec'] = float(device_sample_rate)
            
            if Driver_map[device_type].get('settings').find('channel_settings') != -1:
                settings['channel_settings'] = Driver_map[device_type].get('channel_settings')  
            
            self.driver_add(instance_name, driver_path, settings)
            
        ## itty Rest functions for get, post, put, delete requests:
        ## CNDEP functions:
        cndep_path = "/cndep/"
        
        @get(cndep_path + 'help')
        @get(cndep_path + 'description')
        def Description(request):
            url = 'http://dsnet.tu-plovdiv.bg/cndep/rest/CNDEP_REST_wadl'
            data = urllib.urlopen(url)
            return Response(data.read(), content_type='text/xml')
        
        @get(cndep_path + 'device/list')
        def GetList(request):
            if('full' in request.GET): 
                full = True
            else: 
                full = False
            xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_response += '<response rows="%d" status="200">\n' % len(device_list)
            for i in device_list:
                xml_response += self.xml_creator(i, full, True)
            xml_response += '</response>'
            return Response(xml_response, content_type='text/xml')
        
        @get(cndep_path + 'device/all')   
        def GetAll(request):
            if('full' in request.GET): 
                full = True
            else: 
                full = False
            xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_response += '<response rows="%d"  status="200">\n' % len(device_list)
            for i in device_list:
                xml_response += self.xml_creator(i, full)
            xml_response += '</response>'
            return Response(xml_response, content_type='text/xml')
        
        @get(cndep_path + 'device/id_from_name/(?P<device_name>\w+)')
        def GetId(request, device_name=None):
            for i in device_list:
                if(device_list[i].get('name') == device_name):
                    xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                    xml_response += '<response status="200">\n'
                    xml_response += '<device id="%s"/>\n' % i
                    xml_response += '</response>'
                    return Response(xml_response, content_type='text/xml')
            raise NotFound('Device Name not found!')
        
        @get(cndep_path + 'device/(?P<device_id>\w+)')
        def GetDevice(request, device_id=None):
            if(device_id == None):
                raise NotFound('Device not found!')
            if('full' in request.GET): 
                full = True
            else: 
                full = False
            
            if(device_id in device_list):
                xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_response += '<response status="200">\n'
                xml_response += self.xml_creator(device_id, full)
                xml_response += '</response>'
                return Response(xml_response, content_type='text/xml')
            else:
                raise NotFound('Device not found!')
            
        @get(cndep_path + 'device/(?P<device_id>\w+)/(?P<channel_name>\w+)')
        def GetSensor(request, device_id, channel_name=None):
            if(device_id in device_list): 
                #device found in device_list
                device = device_list.get(device_id)
                xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_response += '<response status="200">\n'
                if(device.get('type') in Device_types):
                    instance_name = device.get('name')
                    data = self.driver_channel_get(instance_name, channel_name)
                    xml_response += '<device id="%s">' % device_id
                    value = data.value
                    unit = data.unit
                    xml_response += '\n<sensor name="%s" value="%s" unit="%s"/>' % (channel_name, value, unit)
                xml_response += '\n</device>'
                xml_response += '\n</response>'
                return Response(xml_response, content_type='text/xml')
            else: 
                raise NotFound('Device not found!')
           
        @put(cndep_path + 'device')
        def AddDevice(request):
            xml_request = request.body
            
            root = ET.fromstring(xml_request)
            device = root.find('device')
            device_id = device.get('id')
            if(device_id == None):
                device_id = 1
            elif(not device_id.isdigit()):
                raise Conflict('Device Id is not integer!')
            else:    
                device_id = int(device_id)
            
            device_type = device.get('type')
            if(device_type == None or device_type == ''):
                raise Conflict('Device Type is empty!')
            device_type = device_type.lower()
            if(device_type not in Device_types):
                raise Conflict('Device Type not found!')
            
            device_name = device.get('name')
            if(device_name == None):
                raise Conflict('Device Name is empty!')
            
            flag = 0
            for i in device_list:
                if(device_list[i].get('name') == device_name):
                    flag = 1
                    break
            if(flag):
                raise Conflict('Device Name already exist!')
            
            device_mac = device.get('mac')
            if(device_mac == None):
                raise Conflict('Device Mac is empty!')
            
            device_sample_rate = device.get('sample_rate')
            if(device_sample_rate == None):
                 device_sample_rate = 2.0
            else:
                try:
                    device_sample_rate = float(device_sample_rate)
                except:
                    raise Conflict('Device Sample Rate is not integer or float!')
            
            while(str(device_id) in device_list): #if device_id exist -> device_id++ and try again
                device_id += 1
                
            device_id = str(device_id)
            
            device_list[device_id] = {'type': device_type, 'name': device_name, 'mac': device_mac, 'sample_rate': device_sample_rate}
            
            instance_name = device_name
            driver_path = Driver_map[device_type].get('path')
            
            settings = {}
            if Driver_map[device_type].get('settings').find('xbee_device_manager') != -1:
                if(self.xbee_device_manager_name == None):
                    self.xbee_device_manager_name = 'xbee_device_manager'
                    self.driver_add('xbee_device_manager', 'devices.xbee.xbee_device_manager.xbee_device_manager:XBeeDeviceManager', settings={'worker_threads':2})
                    time.sleep(1)
                
                settings['xbee_device_manager'] = self.xbee_device_manager_name
            
            settings['extended_address'] = device_mac
            
            if Driver_map[device_type].get('settings').find('sample_rate_ms') != -1:
                if(device_sample_rate == None):
                    device_sample_rate = 30
                settings['sample_rate_ms'] = int(float(device_sample_rate) * 1000)
            
            elif Driver_map[device_type].get('settings').find('sample_rate_sec') != -1:
                if(device_sample_rate == None):
                    device_sample_rate = 1.0
                settings['sample_rate_sec'] = float(device_sample_rate)
                
            if Driver_map[device_type].get('settings').find('channel_settings') != -1:
                settings['channel_settings'] = Driver_map[device_type].get('channel_settings')  
            
            self.driver_add(instance_name, driver_path, settings)
            
            try:
                self.device_list_update()
            except:
                traceback.print_exc()
            
            xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml_response += '<response status="201">\n'
            xml_response += '<device id="%s" message="Device Created!"/>\n' % device_id
            xml_response += '</response>'
            return Response(xml_response, status=201, content_type='text/xml')
        
        @put(cndep_path + 'device/(?P<device_id>\w+)/(?P<channel_name>\w+)')
        def AddChannel(request, device_id=None, channel_name=None):
            if(device_id in device_list):
                xml_request = request.body
                
                root = ET.fromstring(xml_request)
                sensor = root.find('sensor')
                
                ch_unit = sensor.get('unit')
                
                instance_name = device_list[device_id].get('name')
                if(ch_unit == None):    
                    type = device_list[device_id].get('type')
                    try:
                        ch_unit = Driver_map[type].get('channel_settings').split(',')[1]
                    except: ch_unit = 'no unit'
                self.driver_channel_add(instance_name, channel_name, ch_unit)
                
                xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_response += '<response status="201">\n'
                xml_response += '<device id="%s" message="Channel Created!"/>\n' % device_id
                xml_response += '</response>'
                return Response(xml_response, status=201, content_type='text/xml')
            else:
                raise NotFound('device not found!')
        
        @post(cndep_path + 'device')
        def EditDevice(request):
            xml_request = request.body
            
            root = ET.fromstring(xml_request)
            device = root.find('device')
            
            device_id = device.get('id')
            if(device_id == None or not device_id.isdigit()):
                raise Conflict('Device Id is empty or not integer!')
            
            device_id_new = device.get('id_new')
            if(device_id_new != None and not device_id_new.isdigit()):
                raise Conflict('New Device Id is not integer!')
            
            device_type = device.get('type')
            if(device_type != None and device_type != ''):
                device_type = device_type.lower()
                if(device_type not in Device_types):
                    raise Conflict('Device Type not found!')
            
            device_name = device.get('name')
            if(device_name != None and device_name != device_list[device_id].get('name')):
                flag = 0
                for i in device_list:
                    if(device_list[i].get('name') == device_name):
                        flag = 1
                        break
                if(flag):
                    raise Conflict('Device Name already exist!')
                
            device_mac = device.get('mac')
            
            device_sample_rate = device.get('sample_rate')
            if(device_sample_rate != None):
                try:
                    device_sample_rate = float(device_sample_rate)
                except:
                    raise Conflict('Device Sample Rate not integer or float!')
            if(device_id in device_list):
                if(device_type == None or device_type == ''):
                    device_type = device_list[device_id].get('type').lower()
                if(device_name == None):
                    device_name = device_list[device_id].get('name')
                if(device_mac == None):
                    device_mac = device_list[device_id].get('mac')
                if(device_sample_rate == None):
                    device_sample_rate = device_list[device_id].get('sample_rate')
                
                instance_name = device_name
                self.driver_remove(instance_name)
                
                del device_list[device_id]
                
                if(device_id_new != None):
                    device_id_new = int(device_id_new)
                    while(str(device_id_new) in device_list): #if device_id_new exist -> device_id++ and try again
                        device_id_new += 1
                    device_id = str(device_id_new)
                
                device_list[device_id] = {'type': device_type, 'name': device_name, 'mac': device_mac, 'sample_rate': device_sample_rate}
                    
                instance_name = device_name
                driver_path = Driver_map[device_type].get('path')
                
                settings = {}
                if Driver_map[device_type].get('settings').find('xbee_device_manager') != -1:
                    if(self.xbee_device_manager_name == None):
                        self.xbee_device_manager_name = 'xbee_device_manager'
                        self.driver_add('xbee_device_manager', 'devices.xbee.xbee_device_manager.xbee_device_manager:XBeeDeviceManager', settings={'worker_threads':2})
                        time.sleep(1)
                    
                    settings['xbee_device_manager'] = self.xbee_device_manager_name
                
                settings['extended_address'] = device_mac
                
                if Driver_map[device_type].get('settings').find('sample_rate_ms') != -1:
                    if(device_sample_rate == None):
                        device_sample_rate = 30
                    settings['sample_rate_ms'] = int(float(device_sample_rate) * 1000)
                
                elif Driver_map[device_type].get('settings').find('sample_rate_sec') != -1:
                    if(device_sample_rate == None):
                        device_sample_rate = 1.0
                    settings['sample_rate_sec'] = float(device_sample_rate)
                
                if Driver_map[device_type].get('settings').find('channel_settings') != -1:
                    settings['channel_settings'] = Driver_map[device_type].get('channel_settings')      
                
                self.driver_add(instance_name, driver_path, settings)
                   
                try:
                    self.device_list_update()
                except:
                    traceback.print_exc()
                
                xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_response += '<response status="202">\n'
                xml_response += '<device id="%s" message="Device Updated!"/>\n' % device_id
                xml_response += '</response>'
                return Response(xml_response, status=202, content_type='text/xml')
                
            else:
                raise NotFound('Device not found!')
        
        @post(cndep_path + 'device/(?P<device_id>\w+)/(?P<channel_name>\w+)')
        def EditChannel(request, device_id=None, channel_name=None):
            if(device_id in device_list):
                xml_request = request.body
                
                root = ET.fromstring(xml_request)
                sensor = root.find('sensor')
                
                ch_value = sensor.get('value')
                ch_unit = sensor.get('unit')
                
                instance_name = device_list[device_id].get('name')
                
                data = self.driver_channel_get(instance_name, channel_name)
                value = data.value
                unit = data.unit
                
                if(ch_value == None):
                    ch_value = value
                if(ch_unit == None):
                    ch_unit = unit
                
                self.driver_channel_set(instance_name, channel_name, ch_value, ch_unit)
                
                xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_response += '<response status="202">\n'
                xml_response += '<device id="%s" message="Channel Updated!"/>\n' % device_id
                xml_response += '</response>'
                return Response(xml_response, status=202, content_type='text/xml')
            else:
                raise NotFound('device not found!')
        
        @delete(cndep_path + 'device/(?P<device_id>\w+)')
        def DeleteDevice(request, device_id=None):
            if(device_id in device_list):
                instance_name = device_list[device_id].get('name')
                
                self.driver_remove(instance_name)
                
                del device_list[device_id]
               
                try:
                    self.device_list_update()
                except:
                    traceback.print_exc()
                
                xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_response += '<response status="200">\n'
                xml_response += '<device id="%s" message="Device Deleted!"/>\n' % device_id
                xml_response += '</response>'
                return Response(xml_response, status=200, content_type='text/xml')
            else: 
                raise NotFound('Device not found!')
        
        @delete(cndep_path + 'device/(?P<device_id>\w+)/(?P<channel_name>\w+)')
        def DeleteChannel(request, device_id=None, channel_name=None):
            if(device_id in device_list):
                instance_name = device_list[device_id].get('name')
                
                dm = self.__core.get_service("device_driver_manager")
                dm_self, asm = dm.get_ASM()
                
                new_device = asm.instance_get(dm_self, instance_name)
                if new_device.property_exists(channel_name):
                    self.driver_channel_remove(instance_name, channel_name)
                
                    xml_response = '<?xml version="1.0" encoding="UTF-8"?>\n'
                    xml_response += '<response status="200">\n'
                    xml_response += '<device id="%s" message="Device Channel Deleted!"/>\n' % device_id
                    xml_response += '</response>'
                    return Response(xml_response, status=200, content_type='text/xml')
                else: 
                    raise NotFound('Channel not found!')
            else: 
                raise NotFound('Device not found!')
        
    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:
    def driver_add(self, instance_name, driver_path, settings):
        dm = self.__core.get_service("device_driver_manager")
        
        dm_self, asm = dm.get_ASM()
        
        asm.service_load(dm_self, driver_path)
        asm.instance_new(dm_self, driver_path, instance_name)
        
        for i in settings.keys():
            asm.instance_setting_set(dm_self, instance_name, i, settings[i])
        
        asm.instance_settings_apply(dm_self, instance_name)
        asm.instance_start(dm_self, instance_name)
        
        return True
    
    def driver_channel_add(self, instance_name, channel_name, unit):
        print 'driver_channel_add'
        dm = self.__core.get_service("device_driver_manager")
        dm_self, asm = dm.get_ASM()
        new_device = asm.instance_get(dm_self, instance_name)
        
        cm = self.__core.get_service("channel_manager")
        cd = cm.channel_database_get()
        
        channel = instance_name + '.' + channel_name
        if(channel not in self.get_properties()):
            new_device.add_property(
                ChannelSourceDeviceProperty(name=channel_name, type=str,
                    initial=Sample(0, '', unit),
                    perms_mask=(DPROP_PERM_GET),
                    options=DPROP_OPT_AUTOTIMESTAMP,
                    )
                )
        else:
            raise Conflict('Channel already exist!')
        
        return True
        
    def driver_channel_get(self, instance_name, channel_name=None):
        dm = self.__core.get_service("device_driver_manager")
        dm_self, asm = dm.get_ASM()
        cm = self.__core.get_service("channel_manager")
        cd = cm.channel_database_get()
        
        if(channel_name == None):
            x = {}
            for i in self.get_properties():
                if(i.startswith(instance_name + '.')): 
                    data = cd.channel_get(i).get()
                    x[i.split('.')[1]] = data
            return x
        else:
            channel = instance_name + '.' + channel_name
            if(channel in self.get_properties()):
                data = cd.channel_get(channel).get()
                return data
            else:
                raise NotFound('Channel not found!')
    
    def driver_channel_set(self, instance_name, channel_name, ch_value, ch_unit=''):
        dm = self.__core.get_service("device_driver_manager")
        dm_self, asm = dm.get_ASM()
        new_device = asm.instance_get(dm_self, instance_name)
        
        cm = self.__core.get_service("channel_manager")
        cd = cm.channel_database_get()
        
        channel = instance_name + '.' + channel_name
        if(channel in self.get_properties()):
            sample = Sample(0, ch_value, ch_unit)
            #cd.channel_get(channel).set(sample)##################################################
            new_device.property_set(channel_name, sample)
            
        else:
            raise NotFound('Channel not found!')
        return True
     
    def driver_channel_remove(self, instance_name, channel_name):
        dm = self.__core.get_service("device_driver_manager")
        dm_self, asm = dm.get_ASM()
        
        new_device = asm.instance_get(dm_self, instance_name)
        if new_device.property_exists(channel_name):
            new_device.remove_property(channel_name)
        return True
    
    def driver_remove(self, instance_name):
        dm = self.__core.get_service("device_driver_manager")
        dm_self, asm = dm.get_ASM()
        
        new_device = asm.instance_get(dm_self, instance_name)
        asm.instance_remove(dm_self, instance_name)
        new_device.remove_all_properties()
        
        return True
    
    def get_properties(self):
        cm = self.__core.get_service("channel_manager")
        cd = cm.channel_database_get()
        return cd.channel_list()
    
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
            print "Settings rejected/not found: %s %s" % (rejected, not_found)

        SettingsBase.commit_settings(self, accepted)

        return (accepted, rejected, not_found)

    def start(self):
        """Start the device driver.  Returns bool."""
        threading.Thread.start(self)
        return True

    def stop(self):
        """Stop the device driver.  Returns bool."""
        self.__stopevent.set()
        return True

    ## Locally defined functions:
    ## Rest help functions: 
    def device_list_update(self):
        fd = open(dev_list_path + "device_list.py", 'w+')
        fd.write('device_list={\n')
        for id in device_list:
            device = device_list[id]
            str = '"%s": {"type": "%s", "name": "%s", "mac": "%s", "sample_rate": "%s"},\n' % (id, device.get('type'), device.get('name'), device.get('mac'), device.get('sample_rate'))
            fd.write(str)
        fd.write('}\n')
        fd.close()
    
    def xml_creator(self , id, full=False, list=False):
        if(device_list.has_key(id) == False): 
            raise NotFound('Device not found!')
        else:
            device = device_list[id]
            xml = '<device id="%s"' % id
            if(full or list): 
                xml += ' type="%s" name="%s" mac="%s" sample_rate="%s">' % (device.get('type'), device.get('name'), device.get('mac'), device.get('sample_rate'))
            else: 
                xml += '>'
            if(list):
                pass
            else:
                if(device.get('type')in Device_types):
                    instance_name = device_list[id].get('name')
                    x = self.driver_channel_get(instance_name)
                    for name in x:
                        value = x[name].value
                        unit = x[name].unit
                        xml += '\n<sensor name="%s" value="%s" unit="%s"/>' % (name, value, unit)
                
                else:
                    raise NotFound("Device type not found!")
            xml += '\n</device>\n'
            return xml
      
    # Property callback functions:
    
    # Threading related functions:
    def run(self):
        """run when our device driver thread is started"""
        
        ip = SettingsBase.get_setting(self, "server_ip")
        port = int(SettingsBase.get_setting(self, "server_port"))
        server = 'wsgiref'
        run_itty(server, ip, port)
             
# internal functions & classes

def main():
    pass

if __name__ == '__main__':
    import sys
    status = main()
    sys.exit(status)
