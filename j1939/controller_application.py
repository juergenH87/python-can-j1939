from __future__ import annotations

import logging

import j1939

from .message_id import FrameFormat

logger = logging.getLogger(__name__)

class ControllerApplication:
    """ControllerApplication (CA) identified by a Name and an Address."""

    class State:
        NONE = 0
        WAIT_VETO = 1
        NORMAL = 2
        CANNOT_CLAIM = 3

    class ClaimTimeout:
        VETO = 0.250
        REQUEST_FOR_CLAIM = 1.250

    class FieldValue:
        # The following values are in "Little Endian First" Byteorder

        # indicates, that the parameter is "not available"
        NOT_AVAILABLE_8 = 0xFF
        NOT_AVAILABLE_16 = 0xFF00
        NOT_AVAILABLE_16_ARR = [0xFF, 0x00]
        # indicates, that the parameter is "not valid" or "in error"
        NOT_VALID_8 = 0xFE
        NOT_VALID_16 = 0xFE00
        NOT_VALID_16_ARR = [0xFE, 0x00]
        # raw parameter values must not exceed the following values
        MAX_8 = 0xFA
        MAX_16 = 0xFAFF
        MAX_16_ARR = [0xFA, 0xFF]

    def __init__(self, name, device_address_preferred=None, bypass_address_claim=False):
        """
        :param name:
            A j1939 :class:`j1939.Name` instance
        :param device_address_preferred:
            The device_address this CA should claim on the bus.
        :param bypass_address_claim:
            Flag to bypass address claim procedure
        """
        self._name = name
        self._device_address_preferred = device_address_preferred
        if bypass_address_claim and (device_address_preferred is not None):
            self._device_address_announced = device_address_preferred
            self._device_address = device_address_preferred
            self._device_address_state = ControllerApplication.State.NORMAL
        else:
            self._device_address_announced = j1939.ParameterGroupNumber.Address.NULL
            self._device_address = j1939.ParameterGroupNumber.Address.NULL
            self._device_address_state = ControllerApplication.State.NONE
        self._ecu: j1939.ElectronicControlUnit | None = None
        self._subscribers_request = []
        self._subscribers_acknowledge = []
        self._started = False

    @property
    def _ecu_ref(self) -> j1939.ElectronicControlUnit:
        if self._ecu is None:
            raise RuntimeError("CA is not associated with an ECU")
        return self._ecu

    def associate_ecu(self, ecu):
        """Binds this CA to the ECU given
        :param ecu:
            The ECU this CA should be bound to.
            A j1939 :class:`j1939.ElectronicControlUnit` instance
        """
        self._ecu = ecu

    def remove_ecu(self):

        self._ecu = None

    def subscribe(self, callback):
        """Add the given callback to the message notification stream.
        :param callback:
            Function to call when message is received.
        """
        self._ecu_ref.subscribe(callback, self.message_acceptable)

    def unsubscribe(self, callback):
        """Stop listening for message.
        :param callback:
            Function to call when message is received.
        """
        self._ecu_ref.unsubscribe(callback)

    def subscribe_request(self, callback):
        """Add the given callback to the request notification stream.
        :param callback: Function to call when a request is received.
        """
        self._subscribers_request.append(callback)

    def unsubscribe_request(self, callback):
        """Remove the given callback to the request notification stream.
        :param callback: Function to call when a request is received.
        """
        self._subscribers_request.remove(callback)

    def subscribe_acknowledge(self, callback):
        """Add the given callback from the acknowledge notification stream
        :param callback: Function to call when an acknowledge is received.
        """
        self._subscribers_acknowledge.append(callback)

    def unsubscribe_acknowledge(self, callback):
        """Remove the given callback from the request notification stream.
        :param callback: Function to call when an acknowledge is received.
        """

    def add_timer(self, delta_time, callback, cookie=None):
        """Adds a callback to the list of timer events
        :param delta_time:
            The time in seconds after which the event is to be triggered.
        :param callback:
            The callback function to call
        """
        self._ecu_ref.add_timer(delta_time, callback, cookie)

    def remove_timer(self, callback):
        """Removes ALL entries from the timer event list for the given callback
        :param callback:
            The callback to be removed from the timer event list
        """
        self._ecu_ref.remove_timer(callback)

    def register_dependent(self, dependent):
        """Register a helper whose ``stop()`` should be called on ECU shutdown.

        Convenience forwarder to :meth:`ElectronicControlUnit.register_dependent`
        for helpers that only hold a reference to a CA.

        :param dependent:
            Any object exposing a no-arg ``stop()`` method.
        """
        self._ecu_ref.register_dependent(dependent)

    def unregister_dependent(self, dependent):
        """Remove a previously-registered dependent.

        Convenience forwarder to
        :meth:`ElectronicControlUnit.unregister_dependent`.

        :param dependent:
            The object previously passed to :meth:`register_dependent`.
        """
        self._ecu_ref.unregister_dependent(dependent)

    def start(self, claim_delay=0.5):
        """Starts the CA
        :param claim_delay:
            The time in seconds to wait before starting the address claim procedure.
        """
        # TODO raise RuntimeError("Can't start CA. Seems to be already running.")? or just ignore?
        # check if we are not already started and there is an ecu connected
        if self._ecu and not self.started:
            self._started = True
            self._ecu_ref.add_timer(claim_delay, self._process_claim_async)

    def stop(self):
        """Stops the CA
        """
        # check if we are already started and there is an ecu connected
        if self._ecu and self.started:
            self._started = False
            self._ecu_ref.remove_timer(self._process_claim_async)

    def _process_claim_async(self, cookie):
        time_to_sleep = 0.500
        if self._device_address_state == ControllerApplication.State.NONE:
            if self._device_address_preferred is not None:
                self._device_address_announced = self._device_address_preferred
                self._send_address_claimed(self._device_address_announced)
                if self._device_address_announced > 127 and self._device_address_announced < 248:
                    self._device_address_state = ControllerApplication.State.WAIT_VETO
                    time_to_sleep = ControllerApplication.ClaimTimeout.VETO
                else:
                    # addresses from 0..127 and 248..253 should start immediately
                    self._device_address = self._device_address_announced
                    self._device_address_state = ControllerApplication.State.NORMAL
        elif self._device_address_state == ControllerApplication.State.WAIT_VETO:
            # if we reach this phase, there was no VETO to our address claimed message so far
            self._device_address = self._device_address_announced
            self._device_address_state = ControllerApplication.State.NORMAL
        elif self._device_address_state == ControllerApplication.State.NORMAL:
            # do nothing
            pass
        elif self._device_address_state == ControllerApplication.State.CANNOT_CLAIM:
            # do nothing
            pass
        # add new event with (possibly) new timeout value
        self._ecu_ref.add_timer(time_to_sleep, self._process_claim_async)
        # returning false deletes the event from the list
        return False

    def _process_addressclaim(self, mid, data, timestamp):
        """Processes an address claim message
        :param j1939.MessageId mid:
            A MessageId object holding the information extracted from the can_id.
        :param bytearray data:
            The data contained in the can-message.
        :param float timestamp:
            The timestamp the message was received (mostly) in fractions of Epoch-Seconds.
        """
        src_address = mid.source_address
        logger.debug("Received ADDRESS CLAIMED message from source '%d'", src_address)

        # are we awaiting this address claimed message?
        if (0
            or (self._device_address_state == ControllerApplication.State.NORMAL and src_address == self._device_address)
            or (self._device_address_state == ControllerApplication.State.WAIT_VETO and src_address == self._device_address_announced)
            ):

            logger.info("Received ADDRESS CLAIMED message with conflicting address '%d'", src_address)

            contenders_name = j1939.Name(bytes = data)

            if self._name.value == contenders_name.value:
                # both have the same name - this could mean that we are the device or there is a duplicate
                return
            
            if self._name.value > contenders_name.value:
                # we have to release our address and claim another one
                logger.info("We have to release our address '%d' because the contenders name is less than ours", src_address)
                # TODO: are there any state variables we have to care about?
                self._device_address = j1939.ParameterGroupNumber.Address.NULL
                # TODO: maybe we should call an overloadable function here
                if not self._name.arbitrary_address_capable:
                    # bad luck
                    logger.error("After releasing our address we are configured to stop operation (CANNOT CLAIM)")
                    self._device_address_state = ControllerApplication.State.CANNOT_CLAIM
                    self._device_address = None
                    self._send_address_claimed(j1939.ParameterGroupNumber.Address.NULL) # send CANNOT CLAIM
                else:
                    # TODO: we should check the address range here
                    self._device_address_announced += 1
                    logger.info("Try the next address '%d'", self._device_address_announced)
                    self._send_address_claimed(self._device_address_announced)
                    # TODO: it's not possible to set the VETO-Timeout from here
                    self._device_address_state = ControllerApplication.State.WAIT_VETO

            else:
                # we have higher prio - repeat our claim message
                logger.info("Contender lost the competition - we can keep our address")
                if self._device_address_state == ControllerApplication.State.NORMAL:
                    # we own our address already
                    self._send_address_claimed(self._device_address)
                else:
                    # we are in the middle of the claim-process
                    self._send_address_claimed(self._device_address_announced)

    def accepts_commanded_address(self):
        """Whether this CA honors a Commanded Address (J1939-81).

        Defaults to the NAME's Arbitrary Address Capable bit; override to
        support other address-configurable device classes that the NAME alone
        cannot represent (e.g. Command Configurable).
        """
        return bool(self._name.arbitrary_address_capable)

    def _process_commanded_address(self, src_address, data, timestamp):
        """Processes a Commanded Address message (J1939-81, PGN 65240).

        The Commanded Address assigns a specific source address to the device
        identified by the embedded 64-bit NAME. If the NAME matches ours and we
        accept the command, run the address-claim procedure at the commanded
        address.

        :param int src_address:
            The source address the Commanded Address was sent from.
        :param bytearray data:
            The reassembled 9-byte payload (bytes 0-7: NAME, byte 8: new SA).
        :param float timestamp:
            The timestamp the message was received in fractions of Epoch-Seconds.
        """
        if len(data) < 9:
            return
        commanded_name = j1939.Name(bytes=bytes(data[0:8]))
        new_address = data[8]
        if commanded_name.value != self._name.value:
            # not addressed to this CA
            return
        if not self.accepts_commanded_address():
            logger.info("Ignoring Commanded Address for SA '%d': not accepted by policy", new_address)
            return
        logger.info("Received Commanded Address: claiming new address '%d'", new_address)
        self._begin_address_claim(new_address)

    def _begin_address_claim(self, new_address):
        """Initiate the J1939-81 address-claim procedure at the given address.

        Reuses the existing claim state machine: an Address Claimed message is
        transmitted immediately at the new source address. Addresses in the
        128..247 range enter WAIT_VETO (resolved to NORMAL by the
        :meth:`_process_claim_async` timer, contention by
        :meth:`_process_addressclaim`); all other addresses claim immediately.

        :param int new_address:
            The source address to claim. Must be a valid (claimable) source
            address in the range 0..253; NULL (254) and GLOBAL (255) are
            rejected.

        :return:
            True if the claim procedure was started, otherwise False.
        """
        # Only 0..253 are valid (claimable) source addresses. NULL (254) and
        # GLOBAL (255) must never be claimed - doing so would put the CA into an
        # invalid state.
        if new_address < 0 or new_address > 253:
            logger.warning("Ignoring address claim for invalid source address '%d'", new_address)
            return False

        self._device_address_preferred = new_address
        self._device_address_announced = new_address
        self._send_address_claimed(new_address)
        if new_address > 127 and new_address < 248:
            self._device_address_state = ControllerApplication.State.WAIT_VETO
            # Re-arm the veto timeout so the WAIT_VETO -> NORMAL transition
            # happens after the veto window rather than waiting for the next
            # periodic claim tick. Only relevant when the periodic claim timer
            # is already running (i.e. the CA has been started).
            if self.started:
                self._ecu_ref.remove_timer(self._process_claim_async)
                self._ecu_ref.add_timer(ControllerApplication.ClaimTimeout.VETO, self._process_claim_async)
        else:
            # addresses from 0..127 and 248..253 claim immediately
            self._device_address = new_address
            self._device_address_state = ControllerApplication.State.NORMAL
        return True

    def _process_request(self, mid, dest_address, data, timestamp):
        """Processes a REQUEST message
        :param j1939.MessageId mid:
            A MessageId object holding the information extracted from the can_id.
        :param int dest_address:
            The destination address of the message
        :param bytearray data:
            The data contained in the can-message.
        :param float timestamp:
            The timestamp the message was received (mostly) in fractions of Epoch-Seconds.
        """
        pgn = data[0] | (data[1] << 8) | (data[2] << 16)
        src_address = mid.source_address

        if (self.state != ControllerApplication.State.NORMAL) or ((self._device_address != dest_address) and (dest_address != j1939.ParameterGroupNumber.Address.GLOBAL)):
            # only answer if
            # - we have a valid address and
            # - the destination_addr is ours OR the destination_addr is the GLOBAL one
            return

        # special case j1939.ParameterGroupNumber.PGN.ADDRESSCLAIM
        if pgn==j1939.ParameterGroupNumber.PGN.ADDRESSCLAIM:
            # answer the request with our name...
            self._send_address_claimed(self._device_address)
        else:
            for subscriber in self._subscribers_request:
                subscriber(src_address, dest_address, pgn)

    def send_message(self, priority, parameter_group_number, data):
        if self.state != ControllerApplication.State.NORMAL:
            raise RuntimeError("Could not send message unless address claiming has finished")

        mid = j1939.MessageId(priority=priority, parameter_group_number=parameter_group_number, source_address=self._device_address)
        self._ecu_ref.send_message(mid.can_id, True, data)

    def send_pgn(self, data_page, pdu_format, pdu_specific, priority, data, time_limit=0, frame_format=FrameFormat.FEFF):
        """send a pgn
        :param int data_page: data page
        :param int pdu_format: pdu format
        :param int pdu_specific: pdu specific
        :param int priority: message priority
        :param list data: payload, each list index represents one payload byte
        :param time_limit: option j1939-22 multi-pg: specify a time limit in s (e.g. 0.1 == 100ms),
        after this time, the multi-pg will be sent. several pgs can thus be combined in one multi-pg.
        0 or no time-limit means immediate sending.
        """
        if self.state != ControllerApplication.State.NORMAL:
            raise RuntimeError("Could not send message unless address claiming has finished")

        return self._ecu_ref.send_pgn(data_page, pdu_format, pdu_specific, priority, self._device_address, data, time_limit, frame_format)

    def send_request(self, data_page, pgn, destination):
        """send a request message
        :param int data_page: data page
        :param int pgn: pgn to be requested
        :param list data: destination address
        """
        if self.state != ControllerApplication.State.NORMAL:
            if pgn != j1939.ParameterGroupNumber.PGN.ADDRESSCLAIM:
                raise RuntimeError("Could not send request message unless address claiming has finished")
            source_address = j1939.ParameterGroupNumber.Address.NULL
        else:
            source_address = self._device_address

        data = [(pgn & 0xFF), ((pgn >> 8) & 0xFF), ((pgn >> 16) & 0xFF)]
        self._ecu_ref.send_pgn(data_page, (j1939.ParameterGroupNumber.PGN.REQUEST >> 8) & 0xFF, destination & 0xFF, 6, source_address, data)

    def _send_address_claimed(self, address):
        # TODO: Normally the (initial) address claimed message must not be an auto repeat message.
        #       We have to use a single-shot message instead!
        #       After a (send-)error occurs we have to wait 0..153 msec before repeating.
        pgn = j1939.ParameterGroupNumber(0, 238, j1939.ParameterGroupNumber.Address.GLOBAL)
        mid = j1939.MessageId(priority=6, parameter_group_number=pgn.value, source_address=address)
        data = self._name.bytes
        self._ecu_ref.send_message(mid.can_id, True, data)

    def on_request(self, src_address, dest_address, pgn):
        """Callback for PGN requests
        :param int src_address:
            The address the request comes from
        :param int dest_address:
            The address the request was sent to; normally ours, but can also be GLOBAL
        :param int pgn:
            Parameter Group Number requested
        """
        pass

    def message_acceptable(self, dest_address):
        """Indicates if this CA would accept a message
        This function indicates the acceptance of this CA for the given dest_address.
        """
        if self.state != j1939.ControllerApplication.State.NORMAL:
            return False
        if dest_address == j1939.ParameterGroupNumber.Address.GLOBAL:
            return True
        return (self.device_address == dest_address)

    @property
    def state(self):
        return self._device_address_state

    @property
    def device_address(self):
        if self.state != j1939.ControllerApplication.State.NORMAL:
            return j1939.ParameterGroupNumber.Address.NULL
        return self._device_address
    
    @property
    def started(self) -> bool:
        """
        Getter for the started property
        """
        return self._started
