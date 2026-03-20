# ModBusX: Modbus Multi-Slave Simulation with Functional Integration

ModBusX is a software platform that simulates multiple, configurable Modbus slave devices, thereby accelerating the development and validation of solar communication products. It is designed to address critical challenges in the testing and validation of data communications within solar energy systems, specifically focusing on reliability, efficiency, and scalability of Modbus protocol-based data exchanges.

## Highlights

- **Multi-instance servers** – Stand up any number of Modbus slaves per connection, with independent unit IDs, register maps, and protocol settings.
- **Async backend** – A purpose-built asyncio server (`modbusx/server/async_server.py`) handles Modbus/TCP and serial (RTU and ASCII) without Qt event-loop contention.
- **Rich register editing** – Tree and table widgets allow grouping, aliasing, bulk operations, and address-mode toggling (protocol vs PLC numbering).
- **Real-time telemetry** – A unified logger writes to `~/.modbusx/logs/modbusxLog.txt` by default, mirrors log messages to the GUI, and gracefully downgrades when file output is unavailable.
- **Reproducible diagrams** – PlantUML sources live under `docs/diagrams/`; the new `generate_diagrams.sh` script produces SVG artifacts locally or in CI.
- **Scripting & Automation** – Execute JSON-based scenarios to simulate dynamic behaviors like PV ramp-up curves or fault conditions (implemented via `ScriptingService`).
- **High Performance UI** – Virtualized register tables handle 10,000+ registers with sub-second selection and smooth scrolling (Sprint 7 optimization).
- **Growing test suite** – Pytest cases cover the async architecture, the connect dialog, and bulk operations, providing regression protection as the code evolves.

## Out of Scope

The following areas are explicitly excluded from the project scope:
1.  **Master-side Client Application**: The focus is strictly on slave simulation.
2.  **Low-level Hardware Simulation**: Physical layer emulation is limited to standard serial/TCP interfaces.
3.  **Deep Embedded Systems Emulation**: Emulation does not extend to real-time embedded logic outside of the communication layer.

## Architecture

ModBusX has evolved from a controller-centered prototype to a layered **Service-Oriented Architecture (SOA)** that isolates orchestration, reusable business rules, and protocol infrastructure.

### Key Components

*   **UI (PyQt)**: Presentation layer (MainWindow, Dialogs) that consumes orchestration managers.
*   **Managers (Orchestration)**: "Thin" controllers (e.g., `ConnectionManager`, `ServerManager`) that mediate interactions between the UI and business logic.
*   **Services (Business Logic)**: Stateless, reusable logic (e.g., `RegisterGroupService`, `ScriptingService`, `RegisterValidator`).
*   **Models**: The **Single Source of Truth** (`RegisterMap`), ensuring all register values live in one place per slave, preventing data divergence.
*   **Infrastructure (Server/Bridge)**: 
    *   **AsyncModbusServer**: Handles low-level protocol logic using `asyncio`, decoupled from the UI.
    *   **Async Bridge**: Integrates the blocking Qt event loop with the non-blocking asyncio backend using `AsyncioEventLoop`.

This architecture supports robust concurrency management (avoiding race conditions) and enables features like "live server synchronization," where UI edits propagate instantly to the running server.

## Installation

```bash
git clone https://github.com/sweeboon/modbusx.git
cd modbusx
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Requirements

- Python 3.9 or newer  
- PyQt5 (pulled in by `requirements.txt`)  
- pymodbus 3.x  
- (Optional) PlantUML + Java 11+ if you plan to regenerate diagrams

## Running the App

```bash
python main.py
```

From the main window you can:

1. Create a connection (Modbus/TCP for now).  
2. Add one or more slave devices under that connection.  
3. Define register groups, aliases, and values.  
4. Start the Modbus server and watch live log output in the lower pane.

## Project Structure

```
modbusx/
├── application.py            # Qt application bootstrap
├── logger.py                 # ModBusXLogger, GUI + file handlers
├── bridge/                   # Qt ⇆ asyncio coordination
│   └── async_bridge.py
├── server/                   # Async Modbus backend
│   ├── async_server.py       # Asyncio server orchestration
│   ├── datablock.py          # RegisterMap-backed datastore
│   ├── function_handlers.py  # Function-code handlers
│   └── function_registry.py  # Handler registry
├── models/                   # Core data structures
│   ├── register_map.py
│   ├── register_entry.py
│   ├── register_group.py
│   ├── register_block.py
│   ├── multi_type_group.py
│   └── connection_model.py
├── services/                 # Business logic helpers
│   ├── register_validator.py
│   ├── register_group_service.py
│   ├── connection_service.py
│   ├── register_sync_service.py
│   ├── scripting_service.py  # Service for managing scenario execution
│   └── scripting/            # Scripting runtime engine and parsing
│       ├── actions.py
│       ├── parser.py
│       ├── runtime.py
│       ├── schema.py
│       └── service.py
├── managers/                 # SOA orchestration layer
│   ├── connection_manager.py
│   ├── server_manager.py
│   ├── register_group_manager.py
│   ├── bulk_operations_manager.py
│   ├── data_refresh_manager.py
│   └── address_mode_manager.py
├── ui/                       # PyQt forms & widgets
│   ├── main_window.py / .ui
│   ├── connect_dialog.py / .ui
│   ├── bulk_operations_dialog.py / bulk_operations.ui
│   ├── register_group_dialog.py
│   ├── multi_type_group_dialog.py
│   ├── components/
│   │   ├── connection_tree_view.py
│   │   └── register_table_view.py
│   └── widgets/address_input.py
└── assets/                   # Icons and Qt resource definitions
├── docs/
│   └── diagrams/             # PlantUML sources and generated SVGs
├── tests/                    # Unit and integration tests
├── ARCHITECTURE_DIAGRAMS.md # Architecture reference
├── generate_diagrams.sh      # Shell script for diagram generation
├── generate_diagrams.bat     # Batch script for diagram generation
├── .gitlab-ci.yml            # Manual GitLab job to build and publish diagrams
├── requirements.txt
├── README.md
└── LICENSE
```

## Diagrams

- Edit any `docs/diagrams/*.puml` file, then run:
  ```bash
  ./generate_diagrams.sh          # SVG output under docs/diagrams/generated/
  ./generate_diagrams.sh --validate   # Optional syntax check
  ```
- The script enforces headless rendering (`-Djava.awt.headless=true`) and applies the shared configuration in `docs/diagrams/plantuml.config` (currently enabling the Smetana layout to avoid Graphviz dependencies).

## Testing

```bash
pytest
```

Current coverage includes:

- `tests/test_async_architecture.py` – validates server start/stop and context refresh.
- `tests/test_connect_dialog.py` – ensures the Qt dialog logic behaves under different protocols.
- `tests/validate_bulk_operations.py` – sanity-checks the bulk operations manager.

Additional fixtures live under `tests/fixtures/`, and log output is captured in `tests/logs/modbusx.log` when tests run.

## Roadmap Notes

- **Scripting**: The scripting engine is implemented, supporting JSON scenarios for dynamic register updates (Sprint 6).
- **Serial Support**: RTU and ASCII are supported. Future work includes finer timing controls (turnaround delays, inter-frame gaps).
- **In Progress (Sprint 7+)**:
  - **Internationalisation**: Framework is in place (`LanguageManager`), but full Chinese language package and translation verification are scheduled for Sprint 7.
  - **Status Bar**: Comprehensive real-time server statistics (active clients, total bytes, error rates).
  - **CRC/LRC Checks**: Explicit validation visualizers for physical layer debugging.
- **Future Work**:
  - **Protocol Security**: TLS/DTLS support for secure Modbus variants (IEC 62443 alignment).
  - **HIL Expansion**: External triggers (GPIO/REST) for Hardware-in-the-Loop integration.
  - **Cloud Integration**: Headless containerized mode for CI/CD pipelines.
  - **Benchmarking**: Built-in tools for stress-testing client applications.

## Functional Requirements (Current Coverage)

- **FR01 – Protocols:** Modbus/TCP and Modbus/Serial (RTU, ASCII) are supported via the asyncio server.
- **FR02 – Register Types:** Coil, Discrete Input, Holding, Input registers all exposed in `RegisterMap`.
- **FR03 – Multiple Slaves per Link:** Supported by `ConnectionManager` and the server’s multi-unit context.
- **FR04/FR05 – Register Groups & Entries:** UI dialogs and managers create arbitrary groups and registers.
- **FR06 – Data Formats:** Unsigned integers and strings are supported today; float/64-bit variants are in progress.
- **FR07 – Independent Start/Stop:** Each connection’s server lifecycle is managed independently via `ServerManager`.
- **FR08/FR09 – Copy, Import, Export:** Group duplication, **Slave Duplication**, and JSON import/export are fully supported.
- **FR10/FR11/FR12 – Group Metadata & Navigation:** Address mode toggles, aliasing, and tree navigation are available.
- **FR13 – Dynamic Behaviour:** Implemented via `ScriptingService`. Supports JSON-based scenarios for simulating value changes over time (e.g., ramps, faults).
- **FR14 – Logging/Diagnostics:** Unified console/file logger plus GUI log pane.
- **FR15 – Multi-language UI:** Bilingual support architecture is implemented; language packs are under development (Sprint 7).

## Non-Functional Requirements (Status Snapshot)

- **NFR01 – Concurrent Slaves:** Async server supports multiple unit IDs; tested with simultaneous slaves in HIL setups.
- **NFR02 – Response Time:** Sub-100 ms round-trips observed in informal testing; formal benchmarks pending.
- **NFR03 – UI Update Latency:** GUI updates stay within the 200 ms target.
- **NFR04 – Stability (72 h):** Rigorous interoperability testing performed with EzLogger devices; long-duration soak tests pending.
- **NFR05 – Configuration Safety:** Dialog confirmations in place; auto-save to be revisited with scripting/import flows.
- **NFR06–NFR08 – Usability & Messaging:** Tooltips and dialogs cover key paths; localisation will improve clarity.
- **NFR09/NFR10 – Extensibility:** Modular services/models ease new data types or export fields.
- **NFR11/NFR12 – Language Switching / Packs:** Dynamic switching framework implemented via `LanguageManager`.
- **NFR13 – Code Quality:** Pytest suite and CI linting enforce baseline quality; coverage growth is ongoing.
- **NFR14 – Test Coverage:** Below the 80 % target; expanding suites are planned.
- **NFR15/NFR16 – Architectural Flexibility:** Async backend + SOA managers simplify future protocols/UI refits.
- **NFR17/NFR18 – Backups & Auditing:** Automated background backups (`~/.modbusx/backups/`) and timestamped logs are active.
- **NFR19 – Responsive UI:** 10k+ register groups handled with sub-second selection and smooth editing via table virtualization (Sprint 7).

## License

ModBusX is released under the MIT License. See `LICENSE` for details.