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
import time
import wsgiref.handlers
import base64
try:
    import digi_httplib as httplib
except:
    import httplib
import urllib
from random import randint
from xml.dom import minidom
import hmac
from hvcrypto import HVCrypto
from settings import *
try:
    from hashlib import sha1
except:
    from sha import sha as sha1

class HealthVaultConn(object):
    wctoken = None
    auth_token = None
    sharedsec = None
    signature = None
    crypto = None
    record_id = None
    
    def __init__(self, wctoken):
        self.wctoken = wctoken
        crypto = HVCrypto()
        sharedsec = str(randint(2 ** 64, 2 ** 65 - 1))
        self.sharedsec = sharedsec
        sharedsec64 = base64.encodestring(sharedsec)
        #2. create content with shared sec
        content = '<content><app-id>' + HV_APPID + '</app-id><shared-secret><hmac-alg algName="HMACSHA1">' + sharedsec64 + '</hmac-alg></shared-secret></content>'
        #3. create header 
        header = "<header><method>CreateAuthenticatedSessionToken</method><method-version>1</method-version><app-id>" + HV_APPID + "</app-id><language>en</language><country>US</country><msg-time>2008-06-21T03:13:50.750-04:00</msg-time><msg-ttl>36000</msg-ttl><version>0.0.0.1</version></header>"
        self.signature = crypto.sign(content)
        #4. create info with signed content 
        info = '<info><auth-info><app-id>' + HV_APPID + '</app-id><credential><appserver><sig digestMethod="SHA1" sigMethod="RSA-SHA1" thumbprint="' + APP_THUMBPRINT + '">' + self.signature + '</sig>' + content + '</appserver></credential></auth-info></info>'
        payload = '<wc-request:request xmlns:wc-request="urn:com.microsoft.wc.request">' + header + info + '</wc-request:request>'
        extra_headers = {'Content-type':'text/xml'}       
        response = self.sendRequest(payload) 
        if response.status == 200:
            auth_response = response.read()
            
            dom = minidom.parseString(auth_response)
            for node in dom.getElementsByTagName("token"):
                self.auth_token = node.firstChild.nodeValue.strip()
        else:
            return "error occured at get auth token"
        #5 After you get the auth_token.. get the record id
        header = '<header><method>GetPersonInfo</method><method-version>1</method-version><auth-session><auth-token>' + self.auth_token + '</auth-token><user-auth-token>' + self.wctoken + '</user-auth-token></auth-session><language>en</language><country>US</country><msg-time>2008-06-21T03:13:50.750-04:00</msg-time><msg-ttl>36000</msg-ttl><version>0.0.0.1</version>'
        info = '<info/>' 
        infodigest = base64.encodestring(sha1(info).digest()) 
        headerinfo = '<info-hash><hash-data algName="SHA1">' + infodigest.strip() + '</hash-data></info-hash>'
        header = header + headerinfo + '</header>'
        
        hashedheader = hmac.new(sharedsec, header, 'sha1')
        hashedheader64 = base64.encodestring(hashedheader.digest())
        
        hauthxml = '<auth><hmac-data algName="HMACSHA1">' + hashedheader64.strip() + '</hmac-data></auth>'
        payload = '<wc-request:request xmlns:wc-request="urn:com.microsoft.wc.request">' + hauthxml + header + info + '</wc-request:request>'
        
        response = self.sendRequest(payload) 
        if response.status == 200:
            getpersoninfo_response = response.read()
            
            dom = minidom.parseString(getpersoninfo_response)
            for node in dom.getElementsByTagName("selected-record-id"):
                self.record_id = node.firstChild.nodeValue
        else:
            return "error occured at select record id"
    
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
    
    #HV_DataTypes:
    #basicdemographic = "bf516a61-5252-4c28-a979-27f45f62f78d"
    #personaldemographic = "92ba621e-66b3-4a01-bd73-74844aed4f5b"
    #bloodoxygensaturation = "3a54f95f-03d8-4f62-815f-f691fc94a500"
    #heartrate = "b81eb4a6-6eac-4292-ae93-3872d6870994"
    #ccr = "1e1ccbfc-a55d-4d91-8940-fa2fbf73c195"
    def getThings(self, hv_datatype):
        #set record-id in the hearder
        print 'record_id:', self.record_id
        print 'auth_token:', self.auth_token
        print 'wctoken:', self.wctoken
        header = '<header><method>GetThings</method><method-version>1</method-version><record-id>' + self.record_id + '</record-id><auth-session><auth-token>' + self.auth_token + '</auth-token><user-auth-token>' + self.wctoken + '</user-auth-token></auth-session><language>en</language><country>US</country><msg-time>2008-06-21T03:13:50.750-04:00</msg-time><msg-ttl>36000</msg-ttl><version>0.0.0.1</version>'
        
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
        '''
        basic_demographic_datatype = "bf516a61-5252-4c28-a979-27f45f62f78d"
        response = self.getThings(basic_demographic_datatype)
        gender = ''
        dob = ''
        response_str=response.read()
      
        if response.status == 200:
            dom  = minidom.parseString(response_str)
            for node in dom.getElementsByTagName("gender"):
                gender = node.firstChild.nodeValue
                #print gender
            for node in dom.getElementsByTagName("birthyear"):
                dob = node.firstChild.nodeValue
                #print dob
            result=gender+' '+dob
            return result, response_str
        else:
            return 'error in getting basic demographic info'
        '''
        
        response = self.getThings(hv_datatype)
        response_str = response.read()
      
        if response.status == 200:
            return response_str
        else:
            return - 1#'error in getting data'
    
    def putThings(self, hv_datatype, data_xml):
        #set record-id in the hearder
        header = '<header><method>PutThings</method><method-version>1</method-version><record-id>' + self.record_id + '</record-id><auth-session><auth-token>' + self.auth_token + '</auth-token><user-auth-token>' + self.wctoken + '</user-auth-token></auth-session><language>en</language><country>US</country><msg-time>2008-06-21T03:13:50.750-04:00</msg-time><msg-ttl>36000</msg-ttl><version>0.0.0.1</version>'
        
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
    
    def putBasicThing(self, type=None, data_xml=None):
        
        weight = "3d34d87e-7fc1-4153-800f-f56592cb0d17"
        weight_xml = '''
            <weight>
              <when>
                <date>
                  <y>2012</y>
                  <m>11</m>
                  <d>30</d>
                </date>
                <time>
                  <h>10</h>
                  <m>23</m>
                  <s>10</s>
                </time>
              </when>
              <value>
                <kg>84</kg>
                <display units="kg" units-code="kg">185</display>
              </value>
            </weight>'''
        
        bloodoxygensaturation = "3a54f95f-03d8-4f62-815f-f691fc94a500"
        bloodoxygensaturation_xml = '''
            <blood-oxygen-saturation>
              <when>
                <date>
                  <y>2013</y>
                  <m>1</m>
                  <d>1</d>
                </date>
                <time>
                  <h>6</h>
                  <m>0</m>
                  <s>0</s>
                  <f>0</f>
                </time>
              </when>
              <value>0.95</value>
              <measurement-method>
                <text>Pulse Oximetry</text>
                <code>
                  <value>PulseOx</value>
                  <family>wc</family>
                  <type>blood-oxygen-saturation-measurement-method</type>
                  <version>1</version>
                </code>
              </measurement-method>
              <measurement-flags>
                <text>Pulse Oximetry</text>
                <code>
                <value>PulseOx</value>
                <family>wc</family>
                <type>blood-oxygen-saturation-measurement-method</type>
                <version>1</version>
                </code>
              </measurement-flags>
            </blood-oxygen-saturation>'''
        
        heartrate = "b81eb4a6-6eac-4292-ae93-3872d6870994"
        heartrate_xml = '''
            <heart-rate>
              <when>
                <date>
                  <y>2009</y>
                  <m>1</m>
                  <d>1</d>
                </date>
                <time>
                  <h>6</h>
                  <m>0</m>
                  <s>0</s>
                  <f>0</f>
                </time>
              </when>
              <value>75</value>
              <measurement-method>
                <text>Pulse measured by device</text>
                <code>
                  <value>DevicePulse</value>
                  <family>wc</family>
                  <type>heart-rate-measurement-method</type>
                  <version>1</version>
                </code>
              </measurement-method>
              <measurement-conditions>
                <text>Resting</text>
                <code>
                  <value>Resting</value>
                  <family>wc</family>
                  <type>heart-rate-measurement-conditions</type>
                  <version>1</version>
                </code>
              </measurement-conditions>
            </heart-rate>'''
        
        ccr = "1e1ccbfc-a55d-4d91-8940-fa2fbf73c195"
        ccr_xml = '''
<ContinuityOfCareRecord xmlns="urn:astm-org:CCR" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:ccr="urn:astm-org:CCR" xmlns:h="urn:com.microsoft.wc.thing" xmlns:v="urn:com.microsoft.wc.ccrVocab">
<CCRDocumentObjectID>c64a2e2c38da3d762ee5d743627b596b</CCRDocumentObjectID>
<Language>
<Text>English</Text>
</Language>
<Version>V1.0</Version>
<DateTime>
<ExactDateTime>2013-01-13T13:12:26.631000</ExactDateTime>
</DateTime>
<Patient>
<ActorID>PatientActor</ActorID>
</Patient>
<From>
<ActorLink>
<ActorID>ID0RB</ActorID>
<ActorRole>
<Text>Healthcare Information System</Text>
</ActorRole>
</ActorLink>
</From>
<Body>
<VitalSigns>
<Result>
<CCRDataObjectID>45e7f48944c0b0a06bafde97c01230e7</CCRDataObjectID>
<DateTime>
<Type>
<Text>Collection start date</Text>
</Type>
<ExactDateTime>2013-01-13</ExactDateTime>
</DateTime>
<Description>
<Text>Vital Signs</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<Test>
<CCRDataObjectID>d81fb33b3a9c34cfa9b1ad46f1907935</CCRDataObjectID>
<Type>
<Text>Observation</Text>
</Type>
<Description>
<Text>Systolic Blood Pressure</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<TestResult>
<Value>131</Value>
</TestResult>
</Test>
<Test>
<CCRDataObjectID>a9dbfd94c3222e3169544671718f9658</CCRDataObjectID>
<Type>
<Text>Observation</Text>
</Type>
<Description>
<Text>Diastolic Blood Pressure</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<TestResult>
<Value>43</Value>
</TestResult>
</Test>
<Test>
<CCRDataObjectID>17895872f2786fd1f7cc21872a181193</CCRDataObjectID>
<Type>
<Text>Observation</Text>
</Type>
<Description>
<Text>Pulse Rate</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<TestResult>
<Value>83</Value>
</TestResult>
</Test>
</Result>
<Result>
<CCRDataObjectID>c1aee06c5ed28a9c9f7c4785265c8ccd</CCRDataObjectID>
<DateTime>
<Type>
<Text>Collection start date</Text>
</Type>
<ExactDateTime>2013-01-13</ExactDateTime>
</DateTime>
<Description>
<Text>Vital Signs</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<Test>
<CCRDataObjectID>6a48d98c7caa7a1bbffb3753f48f36</CCRDataObjectID>
<Type>
<Text>Observation</Text>
</Type>
<Description>
<Text>Blood Oxygen Saturation</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<TestResult>
<Value>0.95</Value>
</TestResult>
</Test>
</Result>
<Result>
<CCRDataObjectID>914641ed4acef21b2deb95a5fb2a2c7</CCRDataObjectID>
<DateTime>
<Type>
<Text>Collection start date</Text>
</Type>
<ExactDateTime>2013-01-13</ExactDateTime>
</DateTime>
<Description>
<Text>Vital Signs</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<Test>
<CCRDataObjectID>87bec797c0aeabc09748a66e9bfa666e</CCRDataObjectID>
<Type>
<Text>Observation</Text>
</Type>
<Description>
<Text>Heart Rate</Text>
</Description>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
<TestResult>
<Value>93</Value>
</TestResult>
</Test>
</Result>
</VitalSigns>
</Body>
<Actors>
<Actor>
<ActorObjectID>PatientActor</ActorObjectID>
<Person>
<Name>
<CurrentName>
<Given>Nikolay</Given>
<Family>Jivkov</Family>
</CurrentName>
<DisplayName>Nikolay Jivkov</DisplayName>
</Name>
<DateOfBirth>
<ExactDateTime>1988-07-01</ExactDateTime>
</DateOfBirth>
</Person>
<Source>
<Description>
<Text>Unknown</Text>
</Description>
</Source>
</Actor>
<Actor>
<ActorObjectID>ID0RB</ActorObjectID>
<InformationSystem>
<Name>Microsoft HealthVault</Name>
</InformationSystem>
<Source>
<Actor>
<ActorID>PatientActor</ActorID>
<ActorRole>
<Text>Patient</Text>
</ActorRole>
</Actor>
</Source>
</Actor>
</Actors>
</ContinuityOfCareRecord>
<common>
<note>ccr.xml</note>
</common>'''
        
        if(type == None):
            type = ccr
        if(data_xml == None):
            data_xml = ccr_xml
        response = self.putThings(type, data_xml)
        #response = self.putThings(weight,weight_xml)
        response_str = response.read()
      
        if response.status == 200:
            return response_str
        else:
            return 'error'
    
    
