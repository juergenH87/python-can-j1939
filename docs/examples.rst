Examples
========

This section contains example scripts demonstrating how to use the python-can-j1939 library.

Basic Examples
--------------

Simple Receive Global
~~~~~~~~~~~~~~~~~~~~~

Receive J1939 messages globally on the CAN bus.

.. literalinclude:: ../examples/simple_receive_global.py
   :language: python
   :caption: simple_receive_global.py

Simple Receive Peer-to-Peer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Receive J1939 messages in peer-to-peer mode.

.. literalinclude:: ../examples/simple_receive_peer_to_peer.py
   :language: python
   :caption: simple_receive_peer_to_peer.py

Own CA Producer
~~~~~~~~~~~~~~~

Create a Controller Application (CA) that produces messages.

.. literalinclude:: ../examples/own_ca_producer.py
   :language: python
   :caption: own_ca_producer.py

Diagnostic Messages
-------------------

Example of using J1939 diagnostic messages (DM1, DM11, etc.).

.. literalinclude:: ../examples/diagnostic_message.py
   :language: python
   :caption: diagnostic_message.py

Transport Protocols (J1939-21 / J1939-22)
-----------------------------------------

J1939-22 Multi PG
~~~~~~~~~~~~~~~~~

Multi Parameter Group example using J1939-22 transport protocol.

.. literalinclude:: ../examples/j1939_22_multi_pg.py
   :language: python
   :caption: j1939_22_multi_pg.py

J1939-22 Transport Protocols
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Transport protocol example with J1939-22.

.. literalinclude:: ../examples/j1939_22_transport_protocols.py
   :language: python
   :caption: j1939_22_transport_protocols.py

J1939-21 CMDT Send/Receive
~~~~~~~~~~~~~~~~~~~~~~~~~~

Connection Mode Data Transfer examples.

**Sender:**

.. literalinclude:: ../examples/j1939_21_cmdt_send_receive/j1939_send.py
   :language: python
   :caption: j1939_send.py

**Receiver:**

.. literalinclude:: ../examples/j1939_21_cmdt_send_receive/j1939_receive.py
   :language: python
   :caption: j1939_receive.py
