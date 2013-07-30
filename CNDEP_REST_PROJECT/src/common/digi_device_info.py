#!/usr/bin/python

############################################################################
#                                                                          #
# Copyright (c)2008, 2009 Digi International (Digi). All Rights Reserved.  #
#                                                                          #
# Permission to use, copy, modify, and distribute this software and its	   #
# documentation, without fee and without a signed licensing agreement, is  #
# hereby granted, provided that the software is used on Digi products only #
# and that the software contain this copyright notice,	and the following  #
# two paragraphs appear in all copies, modifications, and distributions as #
# well. Contact Product Management, Digi International, Inc., 11001 Bren   #
# Road East, Minnetonka, MN, +1 952-912-3444, for commercial licensing	   #
# opportunities for non-Digi products.                                     #
#                                                                          #
# DIGI SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED   #
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A          #
# PARTICULAR PURPOSE. THE SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, #
# PROVIDED HEREUNDER IS PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND. #
# DIGI HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,         #
# ENHANCEMENTS, OR MODIFICATIONS.                                          #
#                                                                          #
# IN NO EVENT SHALL DIGI BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT,	   #
# SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS,   #
# ARISING OUT OF THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF   #
# DIGI HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.                #
#                                                                          #
############################################################################

# imports
import sys
import time
from digi_ElementTree import ElementTree
from core.tracing import get_tracer

# optional imports
try:
    from rci import process_request as process_rci_request
except:
    pass

# local variables
_tracer = get_tracer("digi_device_info")

def rci_available():
    """\
    Returns True or False if RCI is available on this device.
    """
    return ('process_rci_request' in globals())


def simple_rci_query(query_string):
    """\
    Perform an RCI query and return raw RCI response.

    This query uses only socket operations to POST the HTTP request,
    it does not rely on any other external libraries.
    """

    return process_rci_request(query_string)


def _query_state_rci(state):
    """\
    Parse an RCI response via ElementTree.
    
    Present limitations:
    
        o Only returns tags in the first level below "state".

        o Appends any tag attributes to the tag name, but the order may
            change since ElementTree sorts them.  Best to use only one
            attribute per tag.
    """

    query_string = """\
<rci_request version="1.1">
    <query_state>
        <%s/>
    </query_state>
</rci_request>""" % state


    state_tree = ElementTree().parsestring("<"+state+" />")
    
    state_xml = simple_rci_query(query_string)
    tree = ElementTree().parsestring(state_xml)    
    root_list = tree.findall(state_tree.tag)
    return root_list


def query_state(state):

    if rci_available():
        return _query_state_rci(state)

    return None


def get_platform_name():
    """\
        Returns the name of the underlying platform
    """
    return sys.platform


def get_firmware_version():
    """\
Returns a tuple of the iDigi Device firmware version using RCI.

The tuple is an n-tuple of the form (p, q, r, ..) where the original
version string was p.q.r..

For example the version string "2.8.1" will return (2, 8, 1).

This call is often required to determine future system behavior,
therefore it will retry until it completes successfully.
"""

    i = 3
    
    while i > 0:
        try:
            device_info = query_state("device_info")
            i = -1
        except Exception, e:
            i -= 1
            _tracer.error("get_firmware_version(): WARNING, query_state() failed: %s",
                str(e))
            time.sleep(1)
        if i == 0:
            _tracer.critical("get_firmware_version(): fatal exception caught!  Halting execution.")

    for item in device_info:
        firmwaresoftrevstr = item.find('firmwaresoftrevstr')
        if firmwaresoftrevstr != None:
            firmwaresoftrevstr = firmwaresoftrevstr.text
            break
    else:
        firmwaresoftrevstr = ""

    fw_version = firmwaresoftrevstr.split('.')
    fw_version = map(lambda d: int(d), fw_version)

    return tuple(fw_version)


def device_firmware_gte_to(version_tuple):
    """\
Returns Boolean value if firmware version is greater than the version
supplied within version_tuple.
    """

    device_version = get_firmware_version()

    return device_version >= version_tuple


def get_device_id():
    """\
        Retrieves the Device ID from the Digi device.
    """
    value = ""
    try:
        query = '<rci_request version="1.1"><query_setting><mgmtglobal/>' \
                '</query_setting></rci_request>'
        raw_data = process_rci_request(query)
        setting_tree = ElementTree().parsestring(raw_data)
        device_id = setting_tree.find("deviceId")
        value = device_id.text
    except:
        _tracer.error("get_device_id(): Unable to retrieve Device ID")
        raise

    return value
