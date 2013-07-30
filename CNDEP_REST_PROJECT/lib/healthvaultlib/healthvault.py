#The MIT License
#Copyright (c) 2008 Applied Informatics, Inc.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.
import time, datetime
import wsgiref.handlers
import base64
try:
    import digi_httplib as httplib
except:
    import httplib
import urllib
from xml.dom import minidom
import hmac
from settings import *
try:
    from hashlib import sha1
except:
    from sha import sha as sha1

class HealthVaultConn(object):
    def __init__(self, path='', id=None, secret=None, token=None):
        if(id == None and secret == None and token == None):
            header = '<header><method>NewApplicationCreationInfo</method><method-version>1</method-version><app-id>' + HV_APPID + '</app-id><language>en</language><country>US</country><msg-time>' + self.time_gen() + '</msg-time><msg-ttl>36000</msg-ttl><version>0.0.0.1</version></header>'
            info = '<info/>'
            payload = '<wc-request:request xmlns:wc-request="urn:com.microsoft.wc.request">' + header + info + '</wc-request:request>'
            
            response = self.sendRequest(payload) 
            if response.status == 200:
                response_str = response.read()
                print response_str
                
                dom = minidom.parseString(response_str)
                for node in dom.getElementsByTagName("code"):
                    code = node.firstChild.nodeValue
                
                if code == '0': 
                    for node in dom.getElementsByTagName("app-id"):
                        self.instance_app_id = node.firstChild.nodeValue
                    for node in dom.getElementsByTagName("shared-secret"):
                        instance_shared_secret = node.firstChild.nodeValue
                        self.instance_shared_secret = base64.decodestring(instance_shared_secret)
                    for node in dom.getElementsByTagName("app-token"):
                        self.instance_creation_token = node.firstChild.nodeValue
                    fd = open(path + 'id_secret_token.txt', 'w+')
                    fd.write(self.instance_app_id + '\n')
                    fd.write(instance_shared_secret + '\n')
                    fd.write(self.instance_creation_token + '\n')
                    fd.close()
                else: return 'error in creating new app instance - error code: %s' % code
            else:
                return "error occured at some point"
            
        else:
            self.instance_app_id = id
            self.instance_shared_secret = base64.decodestring(secret)
            self.instance_creation_token = token
            self.createAuthenticatedSessionToken()
            self.getAuthorizedPeople()
                
    def createAuthenticatedSessionToken(self):
        #2. create header 
        header = '<header><method>CreateAuthenticatedSessionToken</method><method-version>2</method-version><app-id>' + self.instance_app_id + '</app-id><language>en</language><country>US</country><msg-time>' + self.time_gen() + '</msg-time><msg-ttl>36000</msg-ttl><version>0.0.0.1</version></header>'

        #3. create info with signed content 
        content = '<content><app-id>' + self.instance_app_id + '</app-id><hmac>HMACSHA1</hmac><signing-time>' + self.time_gen() + '</signing-time></content>'
        
        hashedcontent = hmac.new(self.instance_shared_secret, content, 'sha1')
        hashedcontent64 = base64.encodestring(hashedcontent.digest())
        
        info = '<info><auth-info><app-id>' + self.instance_app_id + '</app-id><credential><appserver2><hmacSig algName="HMACSHA1">' + hashedcontent64.strip() + '</hmacSig>' + content + '</appserver2></credential></auth-info></info>'
        payload = '<wc-request:request xmlns:wc-request="urn:com.microsoft.wc.request">' + header + info + '</wc-request:request>'
        extra_headers = {'Content-type':'text/xml'}       
        response = self.sendRequest(payload) 
        if response.status == 200:
            auth_response = response.read()
            #print auth_response
            dom = minidom.parseString(auth_response)
            for node in dom.getElementsByTagName("code"):
                code = node.firstChild.nodeValue
            if code!='0': print 'Error, code key: ', code
            else:
                for node in dom.getElementsByTagName("token"):
                    self.auth_token = node.firstChild.nodeValue.strip()
                for node in dom.getElementsByTagName("shared-secret"):
                    shared_secret = node.firstChild.nodeValue.strip()
                    self.sharedsec = base64.decodestring(shared_secret)
        else:
            return "error occured at get auth token"
    
    def getAuthorizedPeople(self):
        #set record-id in the hearder
        header = '<header><method>GetAuthorizedPeople</method><method-version>1</method-version><auth-session><auth-token>' + self.auth_token + '</auth-token></auth-session><language>en</language><country>US</country><msg-time>' + self.time_gen() + '</msg-time><msg-ttl>36000</msg-ttl><version>0.0.0.1</version>'
                            
        #QUERY INFO 
        info = '<info><parameters/></info>'
        
        infodigest = base64.encodestring(sha1(info).digest()) 
        headerinfo = '<info-hash><hash-data algName="SHA1">' + infodigest.strip() + '</hash-data></info-hash>'
        header = header + headerinfo + '</header>'
        
        hashedheader = hmac.new(self.sharedsec, header, 'sha1')
        hashedheader64 = base64.encodestring(hashedheader.digest())
        
        hauthxml = '<auth><hmac-data algName="HMACSHA1">' + hashedheader64.strip() + '</hmac-data></auth>'
        payload = '<wc-request:request xmlns:wc-request="urn:com.microsoft.wc.request">' + hauthxml + header + info + '</wc-request:request>'
        self.user_dict = {}
        response = self.sendRequest(payload)
        if response.status == 200:
            response_str = response.read()
            dom = minidom.parseString(response_str)
            for node in dom.getElementsByTagName("code"):
                code = node.firstChild.nodeValue
            if code == '0': 
                i = 0
                for outer_node in dom.getElementsByTagName("person-info"):
                    for node in outer_node.getElementsByTagName("person-id"):
                        self.person_id = node.firstChild.nodeValue
                    for node in outer_node.getElementsByTagName("record"):
                        self.record_id = node.getAttribute("id")
                        self.selected_user = node.firstChild.nodeValue
                        
                        self.user_dict[i] = {}
                        self.user_dict[i]["name"] = self.selected_user
                        self.user_dict[i]["person_id"] = self.person_id
                        self.user_dict[i]["record_id"] = self.record_id
                        i += 1
            elif code == '65':#session token expired -error 65-
                print "Session token expired, getting a new one..." 
                self.createAuthenticatedSessionToken()
                self.getAuthorizedPeople()
            else: return 'error in getting authorized people - error code: %s' % code
    
    def userSelect(self, name):
        for i in self.user_dict:
            if name.replace('_', ' ') == self.user_dict[i]["name"]:
                self.selected_user = self.user_dict[i]["name"]
                self.person_id = self.user_dict[i]["person_id"]
                self.record_id = self.user_dict[i]["record_id"]
                break
    
    def sendRequest(self, payload):
        conn = httplib.HTTPSConnection(HV_SERVICE_SERVER, 443)
        conn.putrequest('POST', '/platform/wildcat.ashx')
        conn.putheader('Content-Type', 'text/xml')
        conn.putheader('Content-Length', '%d' % len(payload))
        conn.endheaders()
        try:
            conn.send(payload)
        except socket.error, v:
            if v[0] == 32:      # Broken pipe
                conn.close()
            raise
        return conn.getresponse()
    
    def getThings(self, hv_datatype):
        header = '<header>\
                        <method>GetThings</method>\
                        <method-version>1</method-version>\
                        <record-id>' + self.record_id + '</record-id>\
                        <auth-session>\
                            <auth-token>' + self.auth_token + '</auth-token>\
                            <offline-person-info>\
                                <offline-person-id>' + self.person_id + '</offline-person-id>\
                            </offline-person-info>\
                        </auth-session>\
                        <language>en</language>\
                        <country>US</country>\
                        <msg-time>' + self.time_gen() + '</msg-time>\
                        <msg-ttl>36000</msg-ttl>\
                        <version>0.0.0.1</version>'
        
        #QUERY INFO 
        info = '<info><group><filter><type-id>' + hv_datatype + '</type-id></filter><format><section>core</section><xml/></format></group></info>'
        
        # INFO TO ADD WEIGHT.. change METHOD in header to PutThings
        #info = '<info><thing><type-id>3d34d87e-7fc1-4153-800f-f56592cb0d17</type-id><data-xml><weight><when><date><y>2008</y><m>6</m><d>15</d></date><time><h>10</h><m>23</m><s>10</s></time></when><value><kg>60</kg><display units="lb" units-code="lb">120</display></value></weight><common/> </data-xml> </thing> </info>'
        
        infodigest = base64.encodestring(sha1(info).digest()) 
        headerinfo = '<info-hash><hash-data algName="SHA1">' + infodigest.strip() + '</hash-data></info-hash>'
        header = header + headerinfo + '</header>'
        
        hashedheader = hmac.new(self.sharedsec, header, 'sha1')
        hashedheader64 = base64.encodestring(hashedheader.digest())
        
        hauthxml = '<auth><hmac-data algName="HMACSHA1">' + hashedheader64.strip() + '</hmac-data></auth>'
        payload = '<wc-request:request xmlns:wc-request="urn:com.microsoft.wc.request">' + hauthxml + header + info + '</wc-request:request>'
        response = self.sendRequest(payload)
        return response
    
    def getBasicThing(self, hv_datatype):
        response = self.getThings(hv_datatype)
        response_str = response.read()
        
        if response.status == 200:
            dom = minidom.parseString(response_str)
            for node in dom.getElementsByTagName("code"):
                code = node.firstChild.nodeValue
            if code == '0': 
                return response_str
            elif code == '65':#session token expired -error 65-
                print "Session token expired, getting a new one..." 
                self.createAuthenticatedSessionToken()
                self.getBasicThing(hv_datatype)
            else: return 'error in getting thing - error code: %s' % code
        else:
            return 'error in getting thing'
    
    def putThings(self, hv_datatype, data_xml):
        header = '<header>\
                        <method>PutThings</method>\
                        <method-version>1</method-version>\
                        <record-id>' + self.record_id + '</record-id>\
                        <auth-session>\
                            <auth-token>' + self.auth_token + '</auth-token>\
                            <offline-person-info>\
                                <offline-person-id>' + self.person_id + '</offline-person-id>\
                            </offline-person-info>\
                        </auth-session>\
                        <language>en</language>\
                        <country>US</country>\
                        <msg-time>' + self.time_gen() + '</msg-time>\
                        <msg-ttl>36000</msg-ttl>\
                        <version>0.0.0.1</version>'
        
        #QUERY INFO
        info = '<info><thing><type-id>' + hv_datatype + '</type-id><data-xml>' + data_xml + '</data-xml></thing></info>'
        
        infodigest = base64.encodestring(sha1(info).digest()) 
        headerinfo = '<info-hash><hash-data algName="SHA1">' + infodigest.strip() + '</hash-data></info-hash>'
        header = header + headerinfo + '</header>'
        
        hashedheader = hmac.new(self.sharedsec, header, 'sha1')
        hashedheader64 = base64.encodestring(hashedheader.digest())
        
        hauthxml = '<auth><hmac-data algName="HMACSHA1">' + hashedheader64.strip() + '</hmac-data></auth>'
        payload = '<wc-request:request xmlns:wc-request="urn:com.microsoft.wc.request">' + hauthxml + header + info + '</wc-request:request>'
        response = self.sendRequest(payload)
        return response
    
    def putBasicThing(self, hv_datatype, data_xml):
        response = self.putThings(hv_datatype, data_xml)
        response_str = response.read()
      
        if response.status == 200:
            dom = minidom.parseString(response_str)
            for node in dom.getElementsByTagName("code"):
                code = node.firstChild.nodeValue
            if code == '0': 
                return response_str
            elif code == '65':#session token expired -error 65-
                print "Session token expired, getting a new one..."
                self.createAuthenticatedSessionToken()
                self.putBasicThing(hv_datatype, data_xml)
            else: return 'error in puting thing - error code: %s' % code
        else:
            return 'error in puting thing'
        
    def time_gen(self):
        time_stamp = datetime.datetime.utcnow()
        result = time_stamp.strftime('%Y-%m-%dT%H:%M:%S.')
        result_add = str(time_stamp.microsecond)
        if len(result_add) < 7: result_add += '0' * (7 - len(result_add)) + 'Z'
        result += result_add
        return result
