import time, datetime, random

def ObjectId_gen():
    ObjectId = ''
    for i in range(0, 16):
        ObjectId += hex(random.randint(0, 255))[2:]
    return ObjectId

def Body_Results_gen(name, value, units, time_stamp, type=None):
    time_stamp = datetime.datetime.fromtimestamp(float(time_stamp))
    long_time = time_stamp.strftime('%Y-%m-%dT%H:%M:%S.') + str(time_stamp.microsecond)
    #short_time = time_stamp.strftime('%Y-%m-%d')
    result = '''
        <Result>
            <CCRDataObjectID>''' + ObjectId_gen() + '''</CCRDataObjectID>
            <DateTime>
                <Type>
                    <Text>Collection start date</Text>
                </Type>
                <ExactDateTime>''' + long_time + '''</ExactDateTime>
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
                <CCRDataObjectID>''' + ObjectId_gen() + '''</CCRDataObjectID>
                <Type>
                    <Text>Observation</Text>
                </Type>
                <Description>
                    <Text>''' + name + '''</Text>
                </Description>
                <Source>
                    <Description>
                        <Text>Unknown</Text>
                    </Description>
                </Source>
                <TestResult>
                    <Value>''' + str(value) + '''</Value>
                    <Units>
                        <Unit>''' + units + '''</Unit>
                    </Units>
                </TestResult>
            </Test>
        </Result>'''
    return result

def Body_gen(channel_array):
    body = ''
    for i in channel_array:
        sample, name = channel_array[i]
        body += Body_Results_gen(name, sample.value, sample.unit, sample.timestamp)
    return body
    
def CCR_gen(name, date_of_birth, channel_array):
    first_name, family_name = name.split(' ')
    body = Body_gen(channel_array)
    time_stamp = datetime.datetime.now()
    long_time = time_stamp.strftime('%Y-%m-%dT%H:%M:%S.') + str(time_stamp.microsecond)
    CCR_ObjectId = ObjectId_gen()
    ccr = '''
<ContinuityOfCareRecord xmlns="urn:astm-org:CCR" xmlns:msxsl="urn:schemas-microsoft-com:xslt" xmlns:ccr="urn:astm-org:CCR" xmlns:h="urn:com.microsoft.wc.thing" xmlns:v="urn:com.microsoft.wc.ccrVocab">
<CCRDocumentObjectID>''' + CCR_ObjectId + '''</CCRDocumentObjectID>
<Language>
    <Text>English</Text>
</Language>
<Version>V1.0</Version>
<DateTime>
    <ExactDateTime>''' + long_time + '''</ExactDateTime>
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
    <VitalSigns>''' + body + '''
    </VitalSigns>
</Body>
<Actors>
    <Actor>
        <ActorObjectID>PatientActor</ActorObjectID>
        <Person>
            <Name>
                <CurrentName>
                    <Given>''' + first_name + '''</Given>
                    <Family>''' + family_name + '''</Family>
                </CurrentName>
                <DisplayName>''' + name + '''</DisplayName>
            </Name>
            <DateOfBirth>
                <ExactDateTime>''' + date_of_birth + '''</ExactDateTime>
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
            <Name>iDigi_Dia MS_HV presentation</Name>
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
</ContinuityOfCareRecord>'''
    return ccr, CCR_ObjectId