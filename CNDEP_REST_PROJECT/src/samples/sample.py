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
try:
    from common.helpers.format_channels import iso_date
except:
    pass

# constants

# exception classes

# interface functions

# classes

class Sample(object):
    """
    Core object for the representation of data in Dia.  Typically
    produced by :class:`device drivers
    <devices.device_base.DeviceBase>`, stored in the :class:`channel
    database <channels.channel_database.ChannelDatabase>`, logged by
    :class:`loggers <channels.logging.logger_base.LoggerBase>` and
    communicated outside the system by :class:`presentations
    <presentations.presentation_base.PresentationBase>`

    Contains the following public attributes:

    .. py:attribute:: timestamp

       Time value at which the sample was acquired

    .. py:attribute:: value

       Object representing the sampled data

    .. py:attribute:: unit

       A string that annotates any possible units that may apply to
       the `value`
       
    """

    # Using slots saves memory by keeping __dict__ undefined.
    __slots__ = ["timestamp", "value", "unit"]

    def __init__(self, timestamp=0, value=0, unit=""):
        self.timestamp = timestamp
        self.value = value
        self.unit = unit
        
    def __repr__(self):
        try:
            return '<Sample: "%s" "%s" at "%s">' % (self.value, self.unit, 
                                              iso_date(self.timestamp))
        except:
            return '<Sample: "%s" "%s" at "%s">' % (self.value, self.unit, 
                                                      self.timestamp)

# internal functions & classes
