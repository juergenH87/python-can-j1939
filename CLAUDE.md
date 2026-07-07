# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`can-j1939` is a Python implementation of the SAE J1939 protocol stack on top of
[python-can](https://python-can.readthedocs.org/). It supports both J1939-21 and J1939-22 (J1939-FD)
data link layers, including transport protocols (BAM, CMDT / RTS-CTS), address claiming, and a
number of diagnostic messages (DM1, DM11, DM14, DM22).

## Common commands

```bash
# Install the package (editable for development)
pip install -e .

# Run the full test suite (matches CI)
pytest . --pyargs

# Run a single test file / test
pytest test/test_ecu.py
pytest test/test_memory_access.py::TestMemoryAccess::test_some_name -v
```

CI runs `pytest . --pyargs` on Python 3.10 across Ubuntu/macOS/Windows
(`.github/workflows/CI.yml`).

## Architecture

The stack is layered: an **ECU** owns a **data-link layer** object and one or more
**ControllerApplications**. Background work runs on a dedicated job thread.

- `j1939/electronic_control_unit.py` — `ElectronicControlUnit` is the entry point. It owns the
  `can.Bus`, a `MessageListener`, a job thread (`_async_job_thread`) that drives timers and
  transport-protocol timeouts, and a list of subscribers. The `data_link_layer` constructor arg
  (`'j1939-21'` or `'j1939-22'`) selects which DLL is instantiated. The ECU passes the DLL a
  small surface of callbacks: `send_message`, `_job_thread_wakeup`, `_notify_subscribers`,
  `_is_message_acceptable`. For tests, `send_message=` can be injected to bypass real CAN I/O.
- `j1939/j1939_21.py` and `j1939/j1939_22.py` — the two DLL implementations. They share the
  callback signature above and implement the transport protocols (TP-BAM, TP-CMDT / RTS-CTS,
  and for J1939-22 the FD multi-session variants and Multi-PG / FEFF). Changes that touch
  protocol behaviour usually need parallel updates in both files.
- `j1939/controller_application.py` — `ControllerApplication` (CA) implements J1939/81 address
  claiming, state machine (`NONE` → `WAITING_VETO` → `NORMAL` / `CANNOT_CLAIM`), per-CA
  subscriptions, and `send_pgn` (which dispatches to the ECU's DLL).
- `j1939/name.py`, `j1939/parameter_group_number.py`, `j1939/message_id.py` — value objects for
  the J1939 NAME, PGN encoding, and 29-bit CAN identifier framing.
- `j1939/diagnostic_messages.py`, `j1939/memory_access.py`, `j1939/Dm14Query.py`,
  `j1939/Dm14Server.py`, `j1939/error_info.py` — diagnostic-message support (DM1/DM11/DM14/DM22),
  including the DM14 memory-access client (`Dm14Query`) and server (`Dm14Server`).
- `j1939/__init__.py` is the public API surface — anything users are expected to import lives
  here.

### Threading model

All I/O and protocol timing flows through the ECU's job thread. The DLL never blocks on I/O
itself — it enqueues work and calls `_job_thread_wakeup` to nudge the thread. Callbacks
registered via `ca.subscribe(...)` or `ca.add_timer(...)` run on that job thread, so they
must not block.

### Tests

- `test/` holds unit tests. `test/helpers/feeder.py` provides the `Feeder` fixture (registered
  in `test/conftest.py`) which is the standard way to drive the stack from tests: it
  replaces `ElectronicControlUnit.send_message` with a simulated bus, lets the test queue
  expected RX/TX messages and PDUs in order, and asserts that the stack produces the expected
  TX sequence. New protocol-level tests should follow that pattern instead of mocking
  `python-can` directly.
- `test/helpers/feeder.AcceptAllCA` is a CA subclass with `message_acceptable` overridden to
  accept everything — use it when a test needs to receive peer-to-peer messages without setting
  up a real claim.

### Examples

`examples/` contains runnable scripts mirroring the README quick-start (simple receive, own CA
producer, transport protocols, multi-PG, diagnostic messages). When adding a new public
feature, prefer extending an existing example over inventing a new pattern in the docs.
