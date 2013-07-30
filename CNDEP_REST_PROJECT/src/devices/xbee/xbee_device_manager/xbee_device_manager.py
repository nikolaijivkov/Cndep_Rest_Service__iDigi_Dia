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
XBee Device Manager

The XBee Device Manager class and related classes.

This class will manage all XBee devices seen and controlled by the Dia.

"""

# constants
MAX_RECVFROM_LEN = 128

# states:
STATE_NOT_READY = 0x0
STATE_READY     = 0x1

# behavior flags:
BEHAVIOR_NONE                      = 0x0
BEHAVIOR_HAS_ATOMIC_DDO            = 0x1


# imports
import sys, traceback

import errno
from random import randint
import socket
from select import *
import threading
import time

try:
    import xbee
except:
    import zigbee as xbee

from devices.device_base import DeviceBase
from settings.settings_base import SettingsBase, Setting
from core.tracing import get_tracer
from channels.channel_source_device_property import *

from common.digi_device_info import device_firmware_gte_to, get_platform_name

from common.types.boolean import Boolean
from devices.xbee.xbee_device_manager.xbee_device_manager_configurator \
    import XBeeDeviceManagerConfigurator
from devices.xbee.xbee_device_manager.xbee_device_state import XBeeDeviceState
from devices.xbee.xbee_device_manager.xbee_ddo_param_cache \
    import XBeeDDOParamCache
from devices.xbee.xbee_device_manager.xbee_device_manager_event_specs import *
from devices.xbee.xbee_config_blocks.xbee_config_block import XBeeConfigBlock
from devices.xbee.xbee_config_blocks.xbee_config_block_final_write import \
    XBeeConfigBlockFinalWrite
from devices.xbee.xbee_config_blocks.xbee_config_block_wakeup import \
      XBeeConfigBlockWakeup
from devices.xbee.xbee_config_blocks.xbee_config_block_ddo import \
    AbstractXBeeConfigBlockDDO
from devices.xbee.xbee_config_blocks.xbee_config_block_sleep import \
    XBeeConfigBlockSleep
from devices.xbee.common.addressing import addresses_equal, normalize_address
from devices.xbee.common.prodid import \
    MOD_XB_802154, MOD_XB_ZNET25, MOD_XB_ZB, MOD_XB_S2C_ZB, parse_dd
from devices.xbee.common.ddo import \
    GLOBAL_DDO_TIMEOUT, GLOBAL_DDO_RETRY_ATTEMPTS, DDOTimeoutException

# exceptions
class XBeeDeviceManagerEndpointNotFound(KeyError):
    pass

class XBeeDeviceManagerInstanceExists(Exception):
    pass

class XBeeDeviceManagerInstanceNotFound(KeyError):
    pass

class XBeeDeviceManagerUnknownEventType(ValueError):
    pass

class XBeeDeviceManagerEventSpecNotFound(ValueError):
    pass

class XBeeDeviceManagerStateException(Exception):
    pass

# classes

class XBeeEndpoint(object):
    """\
        This class stores the data for a given XBee endpoint.
        This includes the file description of our socket,
        the receive queue and a use reference count.

    """
    __slots__ = [ 'reference_count', 'sd', 'xmit_q' ]
    def __init__(self, sd):
        self.reference_count = 0
        self.sd = sd
        self.xmit_q = [ ]


class XBeeDeviceManager(DeviceBase, threading.Thread):
    """\
        This class implements the XBee Device Manager.

        Keyword arguments:

        * **name:** the name of the device instance.
        * **core_services:** the core services instance.

        Advanced Settings:

        * **skip_config_addr_list:** XBee addresses appearing in this list will
          skip directly from the INIT state to the RUNNING state, by-passing
          the application of any configuration blocks.
          Not required, it is empty by default.

            .. Warning::
                Be careful when using this setting. By specifing nodes in this
                list, they will not be configured by the Dia framework,
                potentially leaving the node in an unusable state.

        * **addr_dd_map:** A map of XBee addresses to DD device type values.
          By configuring this mapping dictionary, a node's DD value will not
          have to be queried from the network before a node is configured.
          Not required, it is empty by default.

            .. Warning::
                Be careful when using this setting. It asserts a node to be of 
                a particular module and product type. Using the wrong value 
                could cause a node to be configured incorrectly.
                                
        * **worker_threads:** Number of handles to manage background tasks in
          the Dia framework. Not required, 1 by default.

    """
    MINIMUM_RESCHEDULE_TIME = 10

    def __init__(self, name, core_services):
        self.__name = name
        self.__core = core_services
        
        from core.tracing import get_tracer
        self.__tracer = get_tracer(name)

        ## Local state variables and resources:
        self.__state = STATE_NOT_READY
        self.__behavior_flags = BEHAVIOR_NONE
        self.__lock = threading.RLock()
        self.__sched = self.__core.get_service("scheduler")
        self.__xbee_device_states = { }
        self.__xbee_ddo_param_cache = XBeeDDOParamCache()
        self.__xbee_node_list = [ ]
        # Event specs are stored as tuples (spec, device_state):
        self.__rx_event_spec_state_map = {False:[]}
        self.__xbee_endpoints = { }
        self.__xbee_module_type = None
        self.__behavior_flags = 0

        # Setup internal socket which can be used for unblocking the
        # internal event loop asynchronously:
        self.__outer_sd, self.__inner_sd = socket.socketpair()
        for sd in [ self.__outer_sd, self.__inner_sd ]:
            sd.setblocking(0)

        ## Settings table Definition:
        settings_list = [
            Setting(
                name='skip_config_addr_list', type=list, required=False,
                default_value=[]),
            Setting(
                name='addr_dd_map', type=dict, required=False,
                default_value={}),
            Setting(
                name='worker_threads', type=int, required=False,
                default_value=1,
                verify_function=lambda x: x >= 1),
            Setting(
                name="update_skiplist", type=Boolean, required=False,
                default_value=Boolean(False))
        ]

        ## Add driver property channels:
        # gettable properties
        property_list = [
        ]

        ## Initialize the Devicebase interface:
        DeviceBase.__init__(self, self.__name, self.__core,
                                settings_list, property_list)

        ## Thread initialization:
        self.__stopevent = threading.Event()
        threading.Thread.__init__(self, name=name)
        threading.Thread.setDaemon(self, True)


    ## Internal functions:
    def __unblock_inner_select(self):
        self.__outer_sd.send('a')


    def __endpoint_add(self, endpoint):
#        print "__endpoint_add(): enter"
#        print "__endpoint_add(): endpoint = %d" % (endpoint)
        self.__lock.acquire()
        try:
            if endpoint not in self.__xbee_endpoints:
                sd = socket.socket(socket.AF_ZIGBEE, socket.SOCK_DGRAM,
                                self.__xbee_endpoint_protocol)
                try:
                    sd.bind(('', endpoint, 0, 0))
                except:
                    raise Exception(("Unable to bind endpoint 0x%02x!"
                                    " Check that no other programs are running"
                                    " or are set to run on the device. ") % (
                                        endpoint))
                            
                self.__xbee_endpoints[endpoint] = XBeeEndpoint(sd)

            self.__xbee_endpoints[endpoint].reference_count += 1
#            print "__endpoint_add(): reference_count now = %d" % \
#                (self.__xbee_endpoints[endpoint].reference_count)
        finally:
            self.__lock.release()

        self.__unblock_inner_select()
#        print "__endpoint_add(): exit"
            

    def __endpoint_remove(self, endpoint):
        self.__lock.acquire()
        try:
            if endpoint not in self.__xbee_endpoints:
                raise XBeeDeviceManagerEndpointNotFound, \
                    "endpoint 0x%02x has no active references." % (endpoint)
            self.__xbee_endpoints[endpoint].reference_count -= 1
            if not self.__xbee_endpoints[endpoint].reference_count:
                self.__xbee_endpoints[endpoint].sd.close()
                del(self.__xbee_endpoints[endpoint])
        finally:
            self.__lock.release()


    def __select_config_now_chk(self, buf, addr):
#        self.__tracer.debug("__select_config_now_chk enter")
        self.__lock.acquire()
        try:
            matching_xbee_states = \
                filter(lambda s: s.is_config_scheduled() and \
                           addresses_equal(s.ext_addr_get(), addr[0]),
                       self.__xbee_device_states.values())

            for xbee_state in matching_xbee_states:
#                self.__tracer.debug("__select_config_now_chk():" +  
#                                    "found matching node %s", 
#                                    xbee_state.ext_addr_get())
                
                if xbee_state.configuration_sched_handle_get():
                    # If the node had a scheduled configuration retry, cancel it.
                    try:
#                        self.__tracer.debug("__select_config_now_chk():" + 
#                                            " un-scheduling event")
                        self.xbee_device_schedule_cancel(
                            xbee_state.configuration_sched_handle_get())
#                        self.__tracer.debug("__select_config_now_chk():" + 
#                                            " event unscheduled")
                    except Exception, e:
                        # ignore any failure to cancel scheduled action
                        self.__tracer.warning(('__select_config_now_chk(): ' +
                                              'Error in canceling scheduled ' +
                                              'configuration event: %s') %
                                              (str(e)))

                # (Re-)schedule the configuration attempt ASAP:
                xbee_state.goto_config_immediate()
                xbee_state.configuration_sched_handle_set(
                    self.xbee_device_schedule_after(0,
                        self.__xbee_configurator.configure, xbee_state))

        finally:
            self.__lock.release()

#        self.__tracer.debug("__select_config_now_chk(): exit")


    def __select_rx_cbs_for(self, buf, addr):
#        self.__tracer.debug("__select_rx_cbs_for(): enter")        

        self.__lock.acquire()
        
        #We create a one time use list that contains all rx_events that 
        #at least match the mac address element.  This reduces the testing
        #set drastically.  
        
        #All entries after hash comparison match the mac address element, 
        #So additional address checks are not performed.
         
        proc_list = []        
        if self.__rx_event_spec_state_map.has_key(addr[0]):
          proc_list = proc_list + self.__rx_event_spec_state_map[addr[0]]
        proc_list += self.__rx_event_spec_state_map[False]
        
        for rx_event, state in proc_list:          
            # Update the time we last heard from the node:            
            state.last_heard_from_set(time.time())
            if not state.is_running():
#                self.__tracer.debug("__select_rx_cbs_for(): cb not made, " +
#                                    "device %s not running.",
#                                    (str(rx_event.match_spec_get()[0])))
#                
#                self.__tracer.debug("__select_rx_cbs_for(): device is in " + 
#                                    "state: %d", state._get_state())
                continue
            
            if isinstance(rx_event, XBeeDeviceManagerRxConfigEventSpec):
                if not state.is_config_active():
                   
#                    self.__tracer.debug("__select_rx_cbs_for(): cb not made," +
#                                        " device %s not configuring.",
#                                        (str(rx_event.match_spec_get()[0])))
#                    self.__tracer.debug("__select_rx_cbs_for(): device is in "+ 
#                                        "state: %d", (state._get_state()))
                    continue
            
            #Contains check to see if remaining elements match the event spec
            if not rx_event.match_spec_test(addr, mac_prematch=True):
#                print "__select_rx_cbs_for(): cb not made, test failed."
#                print "__select_rx_cbs_for():  spec: %s" % \
#                    (str(rx_event.match_spec_get()))
                continue
        
            try:
                rx_event.cb_get()(buf, addr)
            except Exception, e:
                # exceptions in driver callbacks are non-fatal to us
                self.__tracer.error('Exception during rx callback for ' +
                                    'addr = %s',  str(addr))
                self.__tracer.debug(traceback.format_exc())
                pass
              
        self.__lock.release()
        return

    def __convert_to_lower(self, a):
        if a == None:
            return a
        else:
            return a.lower()


    ## Functions which must be implemented to conform to the DeviceBase
    ## interface:

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
            self.__tracer.error('Settings rejected/not found: %s %s',
                                self.__name, rejected, not_found)

        # convert all skip_config addresses to lower case:
        accepted["skip_config_addr_list"] = map(
             self.__convert_to_lower, accepted["skip_config_addr_list"])
        
        SettingsBase.commit_settings(self, accepted)
        
        return (accepted, rejected, not_found)


    def start(self):
        """Start the device driver.  Returns bool."""
        threading.Thread.start(self)
        
        return True


    def stop(self):
        """Stop the device driver.  Returns bool."""
        self.__xbee_configurator.stop()

        self.__stopevent.set()
        self.__unblock_inner_select()

        return True


    ## Thread execution begins here:
    def run(self):
        # TODO: dynamically determine how many parallel DDO requests may take
        #       place and give that number to the configurator.        
        self.__xbee_configurator = \
            XBeeDeviceManagerConfigurator(self,
                SettingsBase.get_setting(self, "worker_threads"))
        
        # Determine the appropriate protocol for setting up new sockets:
        self.__xbee_endpoint_protocol = socket.ZBS_PROT_TRANSPORT
        try:
            gw_dd = self.__xbee_configurator.ddo_get_param(None, 'DD',
                                                                use_cache=True)
        except Exception, e:
            # TODO: This exception may be raised when using SE XB FW here (31xx)
            # TODO: determine the appropriate DD value to use here.
            gw_dd = 0
        module_id, product_id = parse_dd(gw_dd)
        self.__xbee_module_type = module_id
        if module_id == MOD_XB_802154:
            self.__xbee_endpoint_protocol = socket.ZBS_PROT_802154
        elif module_id == MOD_XB_ZNET25:
            self.__xbee_endpoint_protocol = socket.ZBS_PROT_TRANSPORT
        elif module_id == MOD_XB_ZB:
            self.__xbee_endpoint_protocol = socket.ZBS_PROT_APS
        elif module_id == MOD_XB_S2C_ZB:
            self.__xbee_endpoint_protocol = socket.ZBS_PROT_APS
        else:
            self.__xbee_endpoint_protocol = socket.ZBS_PROT_TRANSPORT

        # Determine XBee behaviors based on the Digi platform and version.
        if get_platform_name() == 'digix3':
            self.__behavior_flags |= BEHAVIOR_HAS_ATOMIC_DDO
        elif get_platform_name() == 'digiconnect':
            if not device_firmware_gte_to((2, 8, 3)):
                self.__behavior_flags |= BEHAVIOR_NEED_DISCOVER_WORK_AROUND
            else:
                self.__behavior_flags |= BEHAVIOR_HAS_ATOMIC_DDO

        self.__tracer.debug("retrieving node list")
        self.xbee_get_node_list(refresh=True, clear=True)
        
        sd_to_endpoint_map = { }

        addr_dd_dict = SettingsBase.get_setting(self, "addr_dd_map")
        for addr in addr_dd_dict:
            self._xbee_device_ddo_param_cache_set(addr,
                'DD', addr_dd_dict[addr])

        self.__state = STATE_READY

        while True:
            # Check to see if our thread's stop flag is set:
            if self.__stopevent.isSet():
                self.__stopevent.clear()
                break

            self.__lock.acquire()
            # Build wait lists for select()
            rl, wl, xl = [self.__inner_sd], [], []
            rl += [self.__xbee_endpoints[ep].sd for ep in self.__xbee_endpoints]
            # While building wl, build the sd_to_endpoint map:
            sd_to_endpoint_map.clear()
            for ep in filter(lambda ep: len(self.__xbee_endpoints[ep].xmit_q),
                        self.__xbee_endpoints):
                sd = self.__xbee_endpoints[ep].sd
                wl.append(sd)
                sd_to_endpoint_map[sd] = ep
            self.__lock.release()

#            print "XBeeDeviceManager.run(): pre-select (rl, wl) = (%s, %s)" % \
#                (str(rl), str(wl))

            # Wait for there is work for us to perform:
            rl, wl, xl = select(rl, wl, xl)

#            print "XBeeDeviceManager.run(): post-select (rl, wl) = (%s, %s)" % \
#                (str(rl), str(wl))

            # Process reads:
            for sd in rl:
                # Check to see if we were told to unblock internally:
                if sd is self.__inner_sd:
                    sd.recv(1)
                    # Loop around again, rebuilding select wait lists:
                    continue

                # Process endpoint messages and perform callbacks:
                try:
                    buf, addr = sd.recvfrom(MAX_RECVFROM_LEN)
#                    print "XBeeDeviceManager.run(): rx addr = %s, len = %d." % \
#                        (addr, len(buf))
                    # Check to see if this node needs to be configured,
                    # and if so, configure it now:
                    self.__select_config_now_chk(buf, addr)
                    # Check to see if this node has any RX callbacks to perform:
                    self.__select_rx_cbs_for(buf, addr)
                except Exception, e:
                    self.__critical_die(e)
            # Process writes:
            for sd in wl:
                if sd not in sd_to_endpoint_map:
                    continue

                # N.B: the entire xmit queue is not drained here
                # for better interleaving of reads with writes.
                self.__lock.acquire()
                try:
                    ep = sd_to_endpoint_map[sd]
                    buf, addr = self.__xbee_endpoints[ep].xmit_q[0]
                    try:
                        num_bytes = sd.sendto(buf, 0, addr)
#                        print "XBeeDeviceManager: xmit wrote %d bytes" % \
#                            (num_bytes)
                    except socket.error:
                        # xmit of message failed, will retry in select() loop
                        continue
                    # xmit succeeded, de-queue message:
                    self.__xbee_endpoints[ep].xmit_q.pop(0)
                finally:
                    self.__lock.release()
            


    ## XBee Device Driver Interface function definitions:
    def xbee_device_register(self, instance):
        """\
        Register a device instance with the XBee Driver Manager.
        Returns True.

        This call needs to be made before any other requests of the
        XBee driver stack may be made.

        """
        if instance in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceExists, \
                    "instance already exists."

        # Ensure that we are ready to accept devices before allowing this call
        # to complete.
        while self.__state != STATE_READY:
            time.sleep(1)

        self.__lock.acquire()
        try:
            self.__xbee_device_states[instance] = XBeeDeviceState()
        finally:
            self.__lock.release()

        return True

    def xbee_device_unregister(self, instance):
        """\
        Unregister a device instance with the XBee Driver Manager.
        Returns True.

        This call will remove any Event Specifications which have been
        registered xbee_device_event_spec_add() and will de-allocate
        any resources which have been associated with this device.

        """
        if instance not in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceNotFound, \
                    "instance not found."

        self.__lock.acquire()
        try:
            # Remove any event specs this instance may have registered:
            for spec in self.__xbee_device_states[instance].event_spec_list():
                self.xbee_device_event_spec_remove(instance, spec)
            del(self.__xbee_device_states[instance])
        finally:
            self.__lock.release()

        return True

    def xbee_get_module_type(self):
        """\
        Returns the XBee module type installed in the gateway.
        
        See :py:mod:`~devices.xbee.common.prodid` for information on how to
        interpret this value.

        """
        return self.__xbee_module_type


    def xbee_device_event_spec_add(self, instance, event_spec):
        """\
        Add a new event spec to our list of events we should react to.

        See: 
        :py:mod:`~devices.xbee.xbee_device_manager.xbee_device_manager_event_specs`
        for the definition and structure of the event spec.

        """
        if instance not in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceNotFound, \
                    "instance not found."

        self.__lock.acquire()
        try:
            # Add the event spec, processed by spec type:
            if isinstance(event_spec, XBeeDeviceManagerRxEventSpec):
                # RxEventSpecs get added to a special list in the manager:
                spec = event_spec.match_spec_get()
                norm_address = normalize_address(spec[0][0])                
                
                if spec[1][0] == False:
                  self.__rx_event_spec_state_map[False].append(
                            (event_spec, self.__xbee_device_states[instance]))
                else:
                  if not self.__rx_event_spec_state_map.has_key(norm_address):
                    self.__rx_event_spec_state_map[norm_address] = []
                  self.__rx_event_spec_state_map[norm_address].append(
                            (event_spec, self.__xbee_device_states[instance]))
                
#                self.__rx_event_spec_state_map.append(
#                    (event_spec, self.__xbee_device_states[instance]))
                # The endpoint is registered and the ext_addr is added to the
                # device state:
                
                self.__endpoint_add(endpoint=spec[0][1])
                self.__xbee_device_states[instance].ext_addr_set(spec[0][0])
            elif isinstance(event_spec, XBeeDeviceManagerRunningEventSpec):
                pass
            else:
                raise XBeeDeviceManagerUnknownEventType, \
                    "unknown event spec type: %s" % (str(type(event_spec)))

            # Keep track of which instances own which specs in the device state:
            self.__xbee_device_states[instance].event_spec_add(event_spec)
        finally:
            self.__lock.release()

    def xbee_device_event_spec_remove(self, instance, event_spec):
        """\
        Remove an existing event spec from our list of events we should
        react to.

        See:
        :py:mod:`~devices.xbee.xbee_device_manager.xbee_device_manager_event_specs`
        for the definition and structure of the event spec.

        """
        if instance not in self.__xbee_device_states:
            raise XBeeDeviceManagerInstanceNotFound, \
                    "instance not found."

        self.__lock.acquire()
        try:
            # Remove the spec from the device state:
            state = self.__xbee_device_states[instance]

            # Remove the event spec from the appropriate manager list:
            if isinstance(event_spec, XBeeDeviceManagerRxEventSpec):
                try:
                    spec = event_spec.match_spec_get()
                    if spec[1][0] == False:
                      self.__rx_event_spec_state_map[False].remove(
                                              (event_spec, state))
                    else:
                      norm_addr = normalize_address(spec[0][0])
                      rmobj = (event_spec, state)
                      self.__rx_event_spec_state_map[norm_addr].remove(rmobj)
                except:
                    raise XBeeDeviceManagerEventSpecNotFound, \
                        "event specification not found"
            elif isinstance(event_spec, XBeeDeviceManagerRunningEventSpec):
                pass
            else:
                raise XBeeDeviceManagerUnknownEventType, \
                    "unknown event spec type: %s" % (str(type(event_spec)))

            # Remove event spec from instance:
            state.event_spec_remove(event_spec)
        finally:
            self.__lock.release()


    def xbee_device_config_block_add(self, instance, config_block):
        """Add a configuration block to a device instance."""
        config_block.configurator_set(self.__xbee_configurator)
        self.__xbee_device_states[instance].config_block_add(config_block)

    def xbee_device_config_block_remove(self, instance, config_block):
        """Remove a configuration block from a device instance."""
        self.__xbee_device_states[instance].config_block_remove(config_block)

    def xbee_device_configure(self, instance):
        """\
        Configure a device with configuration blocks that were added with
        the xbee_device_config_block_add() method.

        Once xbee_device_configure() is called, a device may not have any
        more configuration blocks added to it.  Configuration of this
        device will be handled by the XBee Device Manager as quickly
        as it can be scheduled.

        """

        device_state = self.__xbee_device_states[instance]
        ext_addr = self.__xbee_device_states[instance].ext_addr_get()

        if not device_state.is_initializing():
            raise XBeeDeviceManagerStateException, \
                "device already configuring or is already running."

        # Add initial attempt to extend wakeup of sleeping nodes
        # TODO: add an automatic prioritization to the config_blocks and
        #       ensure that this class would always be added to the end
        #       of the chain.
        if False: # ext_addr: # CB doesn't work, don't do this until it does
            # TODO, FIXME: Find another wakeup mechanism
            initial_config_block = XBeeConfigBlockWakeup(ext_addr)
            initial_config_block.configurator_set(self.__xbee_configurator)
            self.__xbee_device_states[instance].config_block_list().insert(
                0, initial_config_block)
            # FIXME: Once this is a priority queue, this must change,
            # performing an insert will break the invarient if we use
            # a heapq

        if True in [isinstance(cb, AbstractXBeeConfigBlockDDO) for cb in \
            self.__xbee_device_states[instance].config_block_list()]:
            # Add final write:
            # TODO: add an automatic prioritization to the config_blocks and
            #       ensure that this class would always be added to the end
            #       of the chain.
            final_config_block = XBeeConfigBlockFinalWrite(ext_addr)
            final_config_block.configurator_set(self.__xbee_configurator)
            self.__xbee_device_states[instance].config_block_add(
                final_config_block)

        # Determine whether or not the node is in the "skip_config_addr_list"
        # setting.  If so, transition it to the running state
        # immediately, bypassing the configuration state:
        skip_config_addr_list = \
            SettingsBase.get_setting(self, "skip_config_addr_list")

        if ext_addr in skip_config_addr_list:
            self.__tracer.info("node '%s' " +
                               "in skip config address list, promoting " +
                               "to RUNNING state.", ext_addr)
            device_state.goto_running()
            return

        self.__tracer.info("node '%s' moved to CONFIGURE state.", ext_addr)
                    
        device_state.goto_config_scheduled()

        self._xbee_device_configuration_heuristic(device_state)


    def xbee_device_ddo_get_param(self, dest, param,
                                    timeout=GLOBAL_DDO_TIMEOUT,
                                    use_cache=False):
        """\
        Works together with the XBee configurator thread to process
        a blocking DDO get request.

        If use_cache is True, the parameter will first be sought in the
        DDO parameter cache.  If the parameter is not found in the cache
        it will be set from a successful network request.

        It is necessary to channel DDO requests through this path
        (rather than with xbee.ddo_get_param()) in order to
        schedule an optimal number of pending DDO requests at one
        time.

        """

        return self.__xbee_configurator.ddo_get_param(dest, param, timeout)


    def xbee_device_ddo_set_param(self, dest, param, value,
                                    timeout=GLOBAL_DDO_TIMEOUT,
                                    order=False, apply=False):
        """\
        Works together with the XBee configurator thread to process
        a blocking DDO set request.

        It is necessary to channel DDO requests through this path
        (rather than with xbee.ddo_set_param()) in order to
        schedule an optimal number of pending DDO requests at one
        time.

        A side-effect of calling this function is that the internal DDO
        paramter cache will be updated if setting the parameter was
        successful.

        """

        return self.__xbee_configurator.ddo_set_param(
                    dest, param, value, timeout,
                    order, apply)


    def xbee_device_schedule_after(self, delay, action, *args):
        """\
        Schedule an action (a method) to be called with ``*args``
        after a delay of delay seconds.  Delay may be less than a second.

        If the scheduler gets behind it will simply get behind.

        All tasks will be executed from a seperate thread context than
        other event callbacks from the XBee Device Manager.  This means
        that if your driver receives callbacks from the scheduler and
        processes events from the XBee Device Manager (e.g a receive
        packet event), the called driver will have to have its vital
        state data protected by a lock or other synchronization device.

        """
        return self.__sched.schedule_after(delay, action, *args)

    def xbee_device_schedule_cancel(self, event_handle):
        """\
        Try and cancel a schedule event.

        The event_handle is parameter is the return value from a previous
        call to xbee_device_schedule_after.

        Calling this function on a non-existant event will cause an
        exception to be raised.

        """
        self.__sched.cancel(event_handle)

    def xbee_device_xmit(self, src_ep, buf, addr):
        """\
        Transmit buf to addr using endpoint number src_ep.  Returns None.

        If the transmit can not complete immediately, the transmit
        will be scheduled.

        """

        if src_ep not in self.__xbee_endpoints:
            raise XBeeDeviceManagerEndpointNotFound, \
                "error during xmit, source endpoint 0x%02x not found." % \
                    (src_ep)

        sd = self.__xbee_endpoints[src_ep].sd
        try:
            num_bytes = sd.sendto(buf, 0, addr)            
            #print "XBeeDeviceManager: xmit wrote %d bytes" % (num_bytes)
            return
        except socket.error, e:            
            if e[0] == errno.EWOULDBLOCK:
                pass
            raise e

        # Buffer transmission:
        self.__xbee_endpoints[src_ep].xmit_q.append((buf, addr))
        # Indicate to I/O handling thread we have a new event:
        self.__unblock_inner_select()

    def xbee_get_node_list(self, refresh=False, clear=False):
        """\
        Returns the XBeeDeviceManager's internal copy of the network
        node list.
        
        If refresh is True, a network discovery will be performed.
        
        If clear is True, the node list will be cleared before
        a discovery is performed (only if refresh is True).  Be careful
        with the clear command.  Executing this function may disrupt internal
        network management logic.

        """
        if clear:
            self.__xbee_node_list = [ ]
        new_node_candidates = xbee.get_node_list(refresh=refresh)
        for node in new_node_candidates:
            is_new_node = True
            for old_node in self.__xbee_node_list:
                if addresses_equal(node.addr_extended,
                                   old_node.addr_extended):
                    is_new_node = False
            if not is_new_node:               
                continue
            # new node, add it to local list:
            self.__xbee_node_list.append(node)
            
        return self.__xbee_node_list
            
    
    def _xbee_remove_node_from_list(self, addr_extended):
        """\
        Removes a node from the internal copy of the XBee network
        node list.
        
        This function is called when the XBeeDeviceManager has
        reason to believe that a node no longer exists on a given
        network.  Do not execute this function unless you know what you
        are doing.

        """
        target_nodes = filter(lambda n: addresses_equal(
                                n.addr_extended, addr_extended),
                            self.__xbee_node_list)

        if not len(target_nodes):
            raise ValueError, (
                "XBeeDeviceManager: cannot remove node, '%s' not found" % (
                    addr_extended))

        for node in target_nodes:
            self.__xbee_node_list.remove(node)         
                
        
    ## XBeeDeviceManagerConfigurator interface and callbacks:
    def _get_behavior_flags(self):
        """\
        Returns the current set of XBee behavior flags.

        The behaviors defined by these flags are internal to the XBeeDeviceManager
        and are not intended for general usage.

        """
        return self.__behavior_flags

    def _state_lock(self):
        """Lock internal state, used by configator helper class."""
        self.__lock.acquire()

    def _state_unlock(self):
        """Unlock internal state, used by configator helper class."""
        self.__lock.release()

    def _xbee_device_configuration_heuristic(self, xbee_state):
        """\
        Internal method to determine if an XBee node is ready for
        configuration.

        """

        # If we aren't ready, defer:
        if self.__state != STATE_READY:
            #print "XDMH: Not ready, defering configuration for %s" % xbee_state.ext_addr_get()
            self._xbee_device_configuration_defer(xbee_state)
            return

        configuration_attempts = xbee_state.config_attempts_get()
        xbee_state.config_attempts_set(configuration_attempts + 1)
        current_time = time.time()

        if not xbee_state.xbee_sleep_period_sec():
            # If a device is not configured to sleep, attempt to configure
            # the node immediately.
            #print "XDMH: No sleep configuration, configuring immediately %s" % xbee_state.ext_addr_get()
            self.__xbee_configurator.configure(xbee_state)
            return
        
#        if xbee_state.last_heard_from_get() is None:
#            print """\
#                NODE: %s
#                ATTEMPTS: %s
#                HEARD AGO: UNDEFINED
#                SLEEP CYCLE: %s""" % (
#                    xbee_state.ext_addr_get(),
#                    xbee_state.last_heard_from_get(),
#                    xbee_state.xbee_sleep_period_sec())
#        else:
#            print """\
#                NODE: %s
#                ATTEMPTS: %s
#                HEARD AGO: %s
#                SLEEP CYCLE: %s""" % (
#                    xbee_state.ext_addr_get(),
#                    xbee_state.config_attempts_get(),
#                    (time.time() - xbee_state.last_heard_from_get()),
#                    xbee_state.xbee_sleep_period_sec())

        # Checks to see if we should defer configuration:
        
        if xbee_state.config_attempts_get() <= 1:
            # We haven't waited long enough for the node to report in, scan
            # the config block list for sleep blocks, prepare the network
            # as needed:
#             print "XDMH: Insufficient config attempts(%d) for %s, attempting network prep" %(
#                         xbee_state.config_attempts_get(),
#                         xbee_state.ext_addr_get())
            for sleep_block in \
                filter(lambda cb: isinstance(cb, XBeeConfigBlockSleep),
                         xbee_state.config_block_list()):
                preparation_successful = False
                try:
                    preparation_successful = sleep_block.prepare_network()
#                     print "XDMH: Prep result for %s: %s" % (xbee_state.ext_addr_get(),
#                                                             preparation_successful)
                except DDOTimeoutException, e:
                    self.__tracer.warning("Timeout while preparing " +
                                          "for sleep: %s. Will try again " +
                                          "later...", str(e))
                except Exception, e:
                    self.__tracer.error('Exception while preparing' +
                                        ' network for sleep support: %s',
                                        str(e))
                    self.__tracer.debug(traceback.format_exc())

                if not preparation_successful:
                    # Ensure that we will try to prepare the network again:
                    xbee_state.config_attempts_set(0)              

#             print "XDMH: Deferring configuration after net prep attempt for %s" % (
#                         xbee_state.ext_addr_get())
            self._xbee_device_configuration_defer(xbee_state, multiple=2)
            return
                        
        # We may elect to configure this node now.  However, we must
        # must check to see if this node's configuration attempt could
        # possibily interrupt any node configuration we've heard from in
        # the past, including the candidate node itself:
        
        # Build a list of all nodes which are scheduled to be configured
        # and which we have heard from in the past:
        tbc_l = filter(lambda xbs: xbs.is_config_scheduled() and
                             xbs.last_heard_from_get() is not None,
                           self.__xbee_device_states.values())
        # Map this list to the amount of seconds remaining before we
        # expect to hear from these nodes again:
        tbc_l = map(lambda xbs: xbs.xbee_sleep_period_sec() -
                                  (current_time - 
                                     xbs.last_heard_from_get()),
                    tbc_l)
        
        # Filter out any negative values or any values outside of the
        # current DDO remote-command timeout period:
        ddo_worst_cast_t = GLOBAL_DDO_TIMEOUT * GLOBAL_DDO_RETRY_ATTEMPTS + 1
        tbc_l = filter(lambda t: t >= 0 and t <= ddo_worst_cast_t, tbc_l)
        
        # If there are values in the list, we should elect to defer
        # configuration for this node now:
        if len(tbc_l):
#             print "XDMH: Deferring configuration for %s, expecting other nodes soon" % (
#                         xbee_state.ext_addr_get())
#             print "XDMH: Expected nodes:"
#             print tbc_l
#             print "XDMH: End expected nodes"
            self._xbee_device_configuration_defer(xbee_state)
            return
        
#         print "XDMH: Continuing configuration attempt for %s" % xbee_state.ext_addr_get()
        # There is no other recourse than to try and to reach out to the
        # node now:
        self.__xbee_configurator.configure(xbee_state)
             

    def _xbee_device_configuration_defer(self, xbee_state, multiple=1):
        self.__lock.acquire()
        try:
            # Set state to configuration scheduled and reschedule:
            try:
                prev_sched_handle = xbee_state.configuration_sched_handle_get()
                try:
                    if prev_sched_handle:
                        self.xbee_device_schedule_cancel(prev_sched_handle)
                except:
                    pass
    
                xbee_state.goto_config_scheduled()
                wait_time = max(xbee_state.xbee_sleep_period_sec() * multiple,
                                self.MINIMUM_RESCHEDULE_TIME)
                xbee_state.configuration_sched_handle_set(
                    self.xbee_device_schedule_after(
                        wait_time,
                        self._xbee_device_configuration_heuristic,
                        xbee_state))
            except Exception, e:
                self.__tracer.error("Configuration defer " +
                                    "unexpected failure: %s", str(e))

        finally:
            self.__lock.release()


    def _xbee_device_configuration_done(self, xbee_state):
        """\
        This method is called by the XBee Device Manager's Configurator
        once a configuration attempt has been completed.

        """

        if not xbee_state.is_config_active():
            self.__tracer.error("XBee device state for node %s " + 
                                "is invalid post configuration.", 
                                xbee_state.ext_addr_get())
            return


        # Advance the state of this XBee if all of the configuration
        # blocks have been applied successfully:
#        print "_xbee_device_configuration_done(): check ready"
        xbee_ready = reduce(lambda rdy, blk: rdy and blk.is_complete(),
                                xbee_state.config_block_list(), True)

        if not xbee_ready:
            #        print "_xbee_device_configuration_done(): device not ready"
            # Device is not ready and still needs to be initialized:
            self._xbee_device_configuration_defer(xbee_state)
            return

        ext_addr = xbee_state.ext_addr_get()
        self.__tracer.info("Configuration done for node '%s'" +
                           " promoting to RUNNING state.", ext_addr)
        self.__lock.acquire()
        try:
            xbee_state.goto_running()
        finally:
            self.__lock.release()

        # Add this node to the skip_config_addr_list
        if self.get_setting("update_skiplist"):
            try:
                skiplist = self.get_setting("skip_config_addr_list")
                skiplist.append(ext_addr)

                self.set_pending_setting("skip_config_addr_list", skiplist)
                self.apply_settings()
                self.__core.save_settings()
            except Exception, e:
                self.__tracer.error("Failed to update " +
                                    "configuration file: %s", str(e))


    def _xbee_device_ddo_param_cache_get(self, dest, param):
        """Fetch a cached DDO value for a given destination."""
        return self.__xbee_ddo_param_cache.cache_get(dest, param)

    def _xbee_device_ddo_param_cache_set(self, dest, param, value):
        """\
        Cache a DDO parameter value in all matching state objects.

        Setting value to None invalidates the parameter.

        """
        return self.__xbee_ddo_param_cache.cache_set(dest, param, value)

    def __critical_die(self, e):
        """\
        Trace and handle critical exceptions that need a shutdown.

        The argument 'e' is the exception.
        """
        self.__tracer.critical('The XBeeDeviceManager ' +
                               'caught an exception: %s' +
                               '\n\trequesting dia shutdown...', str(e))
        self.__tracer.debug(traceback.format_exc())
        self.__core.request_shutdown()

        
