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
    Helper functions to parse XBee addresses.
"""

# imports
from socket import *

from devices.xbee.common.ddo import retry_ddo_get_param

# globals 
cached_gw_address_tuple = None

# interface functions

def gw_extended_address_tuple():
    """\
        Retrieves the 64-bit address of the gateway.

        Returns a tuple of two byte strings, most significant word first.

    """

    global cached_gw_address_tuple

    if not cached_gw_address_tuple:
        sh = retry_ddo_get_param(3, None, 'SH')
        sl = retry_ddo_get_param(3, None, 'SL')
        cached_gw_address_tuple = (sh, sl)

    return cached_gw_address_tuple


def gw_extended_address():
    """\
        Retrieves the 64-bit address of the gateway.

        Returns a string.

    """

    s = ':'.join(["%02x"%ord(b) for b in ''.join(my_extended_address_tuple())])
    s = '[' + s + ']!'

    return s


def normalize_address(addr):
    """\
        Normalizes an extended address string.

        Returns a string, adding brackets if needed.

    """

    # self-addressed special case:
    if addr is None:
        return addr

    if not validate_address(addr):
        raise ValueError, "XBee address '%s' invalid" % addr
    if '[' not in addr:
        addr = "[" + addr[0:len(addr)-1].lower() + "]!"
        
    return addr


def addresses_equal(addr1, addr2):
    """\
        Checks to see if two addresses are equal to each other.

        Returns True if they are equal, False if they are not.

    """

    try:
        addr1, addr2 = normalize_address(addr1), normalize_address(addr2)
        return addr1 == addr2
    except:
        pass
    return False


def validate_address(addr):
    """
       Checks the validity of a given address string.

       Returns True if the given address is a valid address, False if it is not.

    """

    # self-addressed special case:
    if addr is None:
        return True

    try:
        addrinfo = getaddrinfo(addr, None)
        # Check the address family of the parsed address:
        if addrinfo[0][0] == AF_ZIGBEE:
            return True
    except:
        pass

    return False


