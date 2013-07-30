############################################################################
#                                                                          #
# Copyright (c)2008-2010, Digi International (Digi). All Rights Reserved.  #
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

"""
Common helper functions for handling sleep/wake tasks

"""

import time

def secs_until_next_minute_period(period, now_tup=None):
    """
    Allows a task to sleep/wake on clean time periods.
    
    For example, if the sleep period were set to 5 (minutes), 
    the device could be made to sleep at 00:05, 00:10, etc...
    This method does not provide the sleep functionality, it 
    only returns the number of seconds remaining in the current 
    interval.

    Note that 'period' must be a factor of 60, so the available periods are: 
    (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)

    'Now_tup' is an optional time tuple, as would be returned by time.gmtime()
    or time.localtime().  If None is passed in, then localtime() is used.
    """    

    if period not in (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60):
        # then is not a factor of 60
        raise ValueError("Minute period of %d is not a factor of 60" % period)

    if now_tup is None:
        # default to local time if none passed in
        now_tup = time.localtime()
        
    # start with seconds until next minute, so want tm_sec = 0
    sec_til = (60 - now_tup[5])

    if(period > 1):
        # then calc the adder for the minutes adjust
        sec_til += ((period - (now_tup[4] % period) - 1) * 60)

    # else, until next minute if fine, we are done
    return sec_til
