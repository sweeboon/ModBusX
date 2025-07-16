# ModBusX

ModbusX is a powerful, user-friendly, and extensible simulator for multiple independent Modbus slave devices, supporting all common Modbus protocols (TCP, RTU, ASCII).

It is designed to accelerate R&D, testing, and integration in solar data logging and industrial IoT workflows, offering advanced configuration, scripting, logging, and automation.

Features
--------

- Multi-instance Modbus slave servers:
Simulate any number of independent slave devices, each configurable with its own protocol (TCP, RTU, ASCII), address, and register map.
- Rich configuration:
Flexible device setup, register mapping, and scenario management directly from a modern GUI.
- Scriptable behavior:
Modules and templates for scripting dynamic register changes, event/fault simulation, and automated test cycles.
- Detailed logging and diagnostics:
Capture and analyze complete protocol conversations, inject errors, and trace interactions for troubleshooting.
- Data insights & visualization:
Monitor register values, statistics, and activity live within the app.
- User-friendly interface:
PyQt-based, designed for accessibility and rapid workflow, with consistent, iterative usability improvements.
- Comprehensive documentation:
Includes setup guides, use cases, test cases, and tailored instructions for solar/energy data logging environments.

Install
--------------------

Pre-built packages:
[Releases](TBD) page.

Install from source
-------------------

### Requirements

- Python 3.9+
- PyQt5
- pymodbus
- (Optional) Additional libraries listed in requirements.txt

To install to a non-default location:

    git clone https://github.com/sweeboon/modbusx.git
    cd modbusx
    pip install -r requirements.txt
    python main.py

Getting Started
--------------------

Launch ModbusX from the command line or desktop shortcut.

Create new simulated slave “connections” via the Add Connection button.

Project layout
--------------

      ├─ main.py                 # Run application entry point
      ├─ modbusx/
      │  ├─ __init__.py
      │  ├─ core.py              # Device, data, and logic core
      │  ├─ slave_server.py      # Modbus protocol backend (multi-unit, TCP/RTU/ASCII)
      │  ├─ register_map.py      # Register models and templates
      │  ├─ logger.py            # Protocol/event logging
      │  ├─ config.py            # Configuration management (YAML/JSON, CLI)
      │  ├─ script_engine.py     # (Planned) scripting for automation, events, faults
      │  ├─ ui/                  # User interface components
      │  │   ├─ __init__.py
      │  │   ├─ main_window.py   # Main PyQt GUI window
      │  │   ├─ controls.py      # Dialogs, advanced widgets
      │  │   ├─ Connect_Dialog.ui
      │  │   ├─ main_window.ui
      │  │   └─ ...              # Other .ui forms
      │  └─ assets/              # Icons, images, and resources
      │      ├─ icons/
      │      └─ resources.qrc
      ├─ scripts/
      │  └─ demo_client.py       # Example/test clients/configs
      ├─ test/                   # Unit and integration tests
      │  └─ README.md
      ├─ docs/
      │  ├─ ARCHITECTURE.md      # Software/system architectural reference
      │  ├─ USER_MANUAL.md       # End-user guide and how-tos
      │  └─ TEST_CASES.md        # Sample scenario scripts and validations
      ├─ requirements.txt
      ├─ README.md
      └─ LICENSE
