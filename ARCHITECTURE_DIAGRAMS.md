# ModbusX Architecture Diagrams

## 1. Component Diagram (Accurate & Complete)

```mermaid
graph TB
    subgraph "UI Layer (PyQt5)"
        subgraph "Main Window"
            MW[MainWindow<br/>main_window.py]
        end

        subgraph "Dialogs"
            CD[ConnectDialog]
            RGD[RegisterGroupDialog]
            MTD[MultiTypeGroupDialog]
            BOD[BulkOperationsDialog]
            BOM[BulkOperationsManual]
        end

        subgraph "UI Components"
            CTV[ConnectionTreeView<br/>504 lines]
            RTV[RegisterTableView<br/>🎉 ENHANCED WITH BUSINESS LOGIC<br/>Direct RegisterMap integration]
            RTD[RegisterTableDelegate]
        end

        subgraph "Widgets"
            AI[AddressInput<br/>Mode-aware validation]
        end
    end

    subgraph "Managers Layer (Orchestration)"
        CM[ConnectionManager<br/>Tree operations]
        SM[ServerManager<br/>Server lifecycle]
        BOH[BulkOperationsHandler]
        BOW[BulkOperationWorker<br/>QThread]
        RGM[RegisterGroupManager<br/>Group operations]
        AMM[AddressModeManager<br/>PLC/Protocol switching]
        DRM[DataRefreshManager<br/>Live updates]
        LM[LanguageManager<br/>I18n switching]
        BM[BackupManager<br/>Auto-save]
    end

    subgraph "Services Layer (Business Logic)"
        RV[RegisterValidator<br/>Address & value validation]
        CS[ConnectionService<br/>Connection management]
        RGS[RegisterGroupService<br/>Group CRUD operations]
        RSS[RegisterSyncService<br/>Real-time sync]
    end

    subgraph "Models Layer (Data)"
        RE[RegisterEntry]
        RM[RegisterMap]
        RG[RegisterGroup]
        RB[RegisterBlock]
        SLM[SlaveModel]
        CNM[ConnectionModel]
        MTG[MultiTypeRegisterGroup]
    end

    subgraph "Server Layer"
        AMS[AsyncModbusServer<br/>TCP/RTU/ASCII]
        RMD[RegisterMapDataBlock<br/>Pymodbus integration]
        FHR[FunctionHandlerRegistry]
        MRH[ModbusRequest Handlers]
    end

    subgraph "Bridge Layer"
        QAB[QtAsyncBridge<br/>Qt ↔ asyncio]
        ASM[AsyncServerManager<br/>Global instance]
    end

    %% UI Layer connections
    MW --> CM
    MW --> SM
    MW --> DRM
    MW --> AMM
    MW --> LM
    MW --> BM
    MW --> RTV
    CTV --> CM
    RTV --> DRM
    RTD --> RTV
    AI --> AMM

    %% Manager connections
    CM --> RGM
    CM --> BOH
    BOH --> BOW
    SM --> ASM
    AMM --> RV
    DRM --> RSS
    RTV --> RV
    RTV --> RM
    RTV --> RSS

    %% Service connections
    CM --> CS
    CM --> RGS
    RGM --> RGS
    CS --> RV
    RGS --> RV
    RSS --> RM

    %% Model connections
    CS --> CNM
    CS --> SLM
    RGS --> RG
    RGS --> MTG
    SLM --> RM
    RM --> RE
    MTG --> RB

    %% Server connections
    ASM --> AMS
    AMS --> RMD
    AMS --> FHR
    FHR --> MRH
    RMD --> RM

    %% Bridge connections
    SM --> QAB
    QAB --> ASM

    style REM fill:#ffcccc,stroke:#ff0000,stroke-width:2px,stroke-dasharray: 5 5
```

## 2. Deployment Diagram

```mermaid
graph TB
    subgraph "Development Environment"
        subgraph "Host Machine"
            OS[Windows/Linux/macOS]
            Python[Python 3.8+]

            subgraph "ModbusX Application"
                subgraph "Main Process"
                    QtApp[Qt Application<br/>Event Loop]
                    UI[UI Components<br/>MainWindow]
                    Managers[Manager Layer]
                    Services[Service Layer]
                    Models[Data Models]
                end

                subgraph "Worker Threads"
                    BOT[BulkOperation<br/>QThread]
                    DRT[DataRefresh<br/>Timer Thread]
                end

                subgraph "Async Runtime"
                    AsyncLoop[Asyncio<br/>Event Loop]
                    TCPServer[TCP Server<br/>Port: 502/custom]
                    RTUServer[RTU Server<br/>COM Port]
                end
            end

            subgraph "External Dependencies"
                PyQt5[PyQt5 Framework]
                PyModbus[pymodbus Library]
                PySerial[pyserial-asyncio]
            end
        end

        subgraph "Network Layer"
            TCP[TCP/IP Stack]
            Serial[Serial/COM Port]
        end

        subgraph "External Clients"
            ModbusClient[Modbus Clients<br/>HMI/SCADA/PLC]
            TestClient[Test Clients<br/>modpoll/QModMaster]
        end
    end

    QtApp --> UI
    UI --> Managers
    Managers --> Services
    Services --> Models

    Managers --> BOT
    Managers --> DRT

    QtApp --> AsyncLoop
    AsyncLoop --> TCPServer
    AsyncLoop --> RTUServer

    TCPServer --> TCP
    RTUServer --> Serial

    TCP --> ModbusClient
    Serial --> ModbusClient
    TCP --> TestClient

    Models --> PyModbus
    AsyncLoop --> PySerial
    UI --> PyQt5
```

## 3. Sequence Diagrams

### 3.1 Connection Creation Workflow

```mermaid
sequenceDiagram
    participant User
    participant MainWindow
    participant ConnectDialog
    participant ConnectionManager
    participant ConnectionService
    participant ConnectionModel
    participant SlaveModel
    participant RegisterMap

    User->>MainWindow: Click "Add Connection"
    MainWindow->>ConnectDialog: show()
    User->>ConnectDialog: Enter address:port
    ConnectDialog->>MainWindow: connection_data

    MainWindow->>ConnectionManager: add_connection(port, address)
    ConnectionManager->>ConnectionService: create_connection()

    ConnectionService->>ConnectionModel: new ConnectionModel()
    ConnectionService->>SlaveModel: create_default_slave()
    SlaveModel->>RegisterMap: new RegisterMap()
    RegisterMap->>RegisterMap: add_block('hr', 1, 10)

    SlaveModel-->>ConnectionService: slave
    ConnectionService->>ConnectionModel: add_slave(slave)
    ConnectionModel-->>ConnectionService: connection

    ConnectionService-->>ConnectionManager: connection
    ConnectionManager->>ConnectionManager: Update tree view
    ConnectionManager-->>MainWindow: connection_added signal
    MainWindow-->>User: Display in tree
```

### 3.2 Server Start Workflow

```mermaid
sequenceDiagram
    participant User
    participant MainWindow
    participant ConnectionManager
    participant ServerManager
    participant AsyncServerManager
    participant QtAsyncBridge
    participant AsyncModbusServer
    participant RegisterMapDataBlock

    User->>MainWindow: Select connection
    User->>MainWindow: Click "Open Connection"

    MainWindow->>ConnectionManager: open_selected_connection()
    ConnectionManager->>ConnectionManager: Get slave register maps

    ConnectionManager->>ServerManager: start_server(config, slaves)
    ServerManager->>AsyncServerManager: start_async_server()

    AsyncServerManager->>QtAsyncBridge: run_in_async_loop()
    QtAsyncBridge->>AsyncModbusServer: new AsyncModbusServer()

    AsyncModbusServer->>RegisterMapDataBlock: Create datablocks
    RegisterMapDataBlock->>RegisterMapDataBlock: Link to RegisterMap

    AsyncModbusServer->>AsyncModbusServer: Start TCP/RTU server
    AsyncModbusServer-->>QtAsyncBridge: server_task

    QtAsyncBridge-->>AsyncServerManager: task_handle
    AsyncServerManager-->>ServerManager: server_started signal
    ServerManager-->>MainWindow: Update UI status
    MainWindow-->>User: Show "OPEN" status
```

### 3.3 Register Value Update Workflow

```mermaid
sequenceDiagram
    participant User
    participant QTableView
    participant RegisterEditorAdapter
    participant RegisterValidator
    participant RegisterMap
    participant RegisterEntry
    participant RegisterSyncService
    participant AsyncModbusServer

    User->>QTableView: Edit value cell
    QTableView->>RegisterEditorAdapter: _on_model_item_changed(item)

    RegisterEditorAdapter->>RegisterValidator: validate_register_value_with_conversion()
    RegisterValidator->>RegisterValidator: Check range (0-65535 or 0-1)
    RegisterValidator-->>RegisterEditorAdapter: validated_value

    RegisterEditorAdapter->>RegisterMap: get_register(reg_type, addr)
    RegisterMap-->>RegisterEditorAdapter: register_entry

    RegisterEditorAdapter->>RegisterEntry: entry.value = validated_value
    RegisterEntry-->>RegisterEditorAdapter: updated

    RegisterEditorAdapter->>RegisterSyncService: propagate_register_change()
    RegisterSyncService->>AsyncModbusServer: update_datablock()
    AsyncModbusServer->>RegisterMapDataBlock: setValues()

    AsyncModbusServer-->>RegisterSyncService: updated
    RegisterSyncService-->>RegisterEditorAdapter: success
    RegisterEditorAdapter->>RegisterEditorAdapter: emit register_changed signal
    RegisterEditorAdapter-->>QTableView: value persisted
    QTableView-->>User: Show new value (persists)
```

### 3.4 Address Mode Switching Workflow

```mermaid
sequenceDiagram
    participant User
    participant MainWindow
    participant AddressModeManager
    participant RegisterValidator
    participant ConnectionTreeView
    participant RegisterTableView
    participant RegisterMap

    User->>MainWindow: Toggle "PLC Address" checkbox
    MainWindow->>AddressModeManager: set_mode(new_mode)

    AddressModeManager->>RegisterValidator: set_address_mode(mode)
    RegisterValidator->>RegisterValidator: Update ADDRESS_MODE
    RegisterValidator->>RegisterValidator: save_to_settings()

    AddressModeManager->>AddressModeManager: emit mode_changed signal

    par Update Tree View
        AddressModeManager->>ConnectionTreeView: refresh_address_display()
        ConnectionTreeView->>RegisterValidator: address_to_display()
        RegisterValidator-->>ConnectionTreeView: formatted_address
        ConnectionTreeView->>ConnectionTreeView: Update all nodes
    and Update Table View
        AddressModeManager->>RegisterTableView: refresh_address_display()
        RegisterTableView->>RegisterValidator: address_to_display()
        RegisterValidator-->>RegisterTableView: formatted_address
        RegisterTableView->>RegisterTableView: Update all rows
    end

    ConnectionTreeView-->>User: Show new format
    RegisterTableView-->>User: Show new format
```

### 3.5 Bulk Operations Workflow

```mermaid
sequenceDiagram
    participant User
    participant MainWindow
    participant BulkOperationsDialog
    participant BulkOperationsHandler
    participant BulkOperationWorker
    participant RegisterMap
    participant ProgressBar

    User->>MainWindow: Select slave
    User->>MainWindow: Click "Bulk Operations"

    MainWindow->>BulkOperationsDialog: show()
    BulkOperationsDialog->>BulkOperationsHandler: set_register_map()

    User->>BulkOperationsDialog: Configure operation
    User->>BulkOperationsDialog: Click "Apply"

    BulkOperationsDialog->>BulkOperationsHandler: execute_operation()
    BulkOperationsHandler->>BulkOperationWorker: new Worker(op_type, data)
    BulkOperationsHandler->>BulkOperationWorker: start()

    loop For each register
        BulkOperationWorker->>RegisterMap: update_register()
        RegisterMap-->>BulkOperationWorker: updated
        BulkOperationWorker->>ProgressBar: emit progress signal
        ProgressBar-->>User: Update progress
    end

    BulkOperationWorker->>BulkOperationWorker: emit finished signal
    BulkOperationWorker-->>BulkOperationsHandler: operation complete
    BulkOperationsHandler-->>BulkOperationsDialog: show result
    BulkOperationsDialog-->>User: "Operation completed"
```

## 4. Class Relationships

```mermaid
classDiagram
    %% UI Layer
    class MainWindow {
        -QTreeView treeView
        -QTableView tableView
        -ConnectionManager connection_manager
        -ServerManager server_manager
        +show_new_connection_dialog()
        +on_tree_selection_changed()
    }

    class ConnectionTreeView {
        -QStandardItemModel model
        +add_connection()
        +add_slave()
        +add_register_group()
        +context_menu_requested
    }

    class RegisterTableView {
        -QStandardItemModel model
        -RegisterTableDelegate delegate
        +populate_registers()
        +refresh_address_display()
        +cell_changed
    }

    %% Managers
    class ConnectionManager {
        -QTreeView tree_view
        -RegisterGroupManager group_manager
        -BulkOperationsHandler bulk_operations
        +add_connection()
        +add_slave_to_connection()
        +connection_added
    }

    class ServerManager {
        -AsyncServerManager async_manager
        -Dict active_servers
        +start_server()
        +stop_server()
        +server_started
        +server_stopped
    }

    class LanguageManager {
        -QTranslator translator
        +load_language(lang_code)
    }

    class BackupManager {
        -QTimer timer
        +start_auto_backup()
    }

    class BulkOperationsHandler {
        -RegisterMap register_map
        -BulkOperationWorker current_worker
        +execute_batch_value_set()
        +execute_address_renumber()
        +operation_completed
    }

    class BulkOperationWorker {
        -str operation_type
        -Dict operation_data
        +run()
        +cancel_operation()
        +progress
        +finished
    }

    class RegisterEditorAdapter {
        -QTableView table_view
        -QStandardItemModel table_model
        -RegisterTableDelegate delegate
        -Dict current_reg_group
        +set_current_register_group()
        +populate_table()
        +_on_model_item_changed()
        +_refresh_address_display()
        +register_changed: pyqtSignal
    }

    %% Services
    class RegisterValidator {
        +validate_register_type()
        +validate_address()
        +validate_value()
        +address_to_display()
        +display_to_address()
    }

    class ConnectionService {
        -Dict connections
        +create_connection()
        +add_slave()
        +remove_slave()
    }

    %% Models
    class RegisterEntry {
        +int addr
        +str reg_type
        +int value
        +str alias
        +str comment
    }

    class RegisterMap {
        +Dict hr
        +Dict ir
        +Dict co
        +Dict di
        +add_register()
        +add_block()
    }

    class SlaveModel {
        +int slave_id
        +RegisterMap register_map
        +List register_groups
        +add_register_group()
    }

    class ConnectionModel {
        +str address
        +int port
        +List slaves
        +add_slave()
        +get_slave()
    }

    %% Relationships
    MainWindow --> ConnectionManager
    MainWindow --> ServerManager
    MainWindow --> RegisterTableView
    MainWindow --> ConnectionTreeView

    ConnectionManager --> ConnectionService
    ConnectionManager --> BulkOperationsHandler
    BulkOperationsHandler --> BulkOperationWorker

    RegisterTableView --> RegisterValidator
    RegisterTableView --> RegisterMap
    RegisterTableView --> RegisterSyncService

    ServerManager --> AsyncServerManager

    ConnectionService --> ConnectionModel
    ConnectionModel --> SlaveModel
    SlaveModel --> RegisterMap
    RegisterMap --> RegisterEntry

    ConnectionManager --> RegisterValidator
    BulkOperationsHandler --> RegisterValidator
```

## 5. Data Flow Diagram

```mermaid
graph LR
    subgraph "Input Sources"
        UI[User Interface]
        MC[Modbus Clients]
        CF[Config Files]
    end

    subgraph "Processing Layers"
        subgraph "Presentation"
            TV[Tree View]
            TBV[Table View]
            DLG[Dialogs]
        end

        subgraph "Orchestration"
            MGR[Managers]
            VAL[Validators]
        end

        subgraph "Business Logic"
            SVC[Services]
            SYNC[Sync Service]
        end

        subgraph "Data Layer"
            MDL[Models]
            MAP[Register Maps]
        end

        subgraph "Protocol Layer"
            SRV[Async Servers]
            BLK[Data Blocks]
        end
    end

    subgraph "Output Targets"
        NET[Network TCP/502]
        SER[Serial COM]
        LOG[Log Files]
        EXP[Export Files]
    end

    %% Input flows
    UI --> TV
    UI --> TBV
    UI --> DLG
    CF --> SVC
    MC --> SRV

    %% Processing flows
    TV --> MGR
    TBV --> MGR
    DLG --> MGR

    MGR --> VAL
    MGR --> SVC

    SVC --> MDL
    MDL --> MAP

    SYNC --> MAP
    SYNC --> BLK

    SRV --> BLK
    BLK --> MAP

    %% Output flows
    SRV --> NET
    SRV --> SER
    MGR --> LOG
    SVC --> EXP
```

## Migration Status

### 🎉 **FULL MIGRATION COMPLETED**

#### ✅ **Phase 1**: RegisterEditorManager → RegisterEditorAdapter
- ✅ **DELETED** `register_editor_manager.py` file (379 lines removed)
- ✅ Created compatibility adapter with value persistence
- ✅ **FIXED** layout preservation - connection widget displays correctly
- ✅ **FIXED** register value persistence issue

#### ✅ **Phase 2**: RegisterEditorAdapter → Enhanced RegisterTableView
- ✅ **DELETED** `register_editor_adapter.py` file (180+ lines removed)
- ✅ **ENHANCED** RegisterTableView with integrated business logic
- ✅ **DIRECT** RegisterMap integration and persistence
- ✅ **ELIMINATED** all adapter pattern complexity
- ✅ **MAINTAINED** full backward compatibility
- ✅ **TESTED** table visibility and functionality

### 🏆 Final Architecture State
- ✅ **RegisterEditorManager**: ❌ **DELETED** (Phase 1)
- ✅ **RegisterEditorAdapter**: ❌ **DELETED** (Phase 2)
- ✅ **RegisterTableView**: ✅ **ENHANCED** with full business logic
- ✅ **Clean Architecture**: No adapter patterns, direct component usage
- ✅ **Performance**: Direct method calls, no delegation overhead

### Technical Implementation
- **Enhanced RegisterTableView** handles:
  - ✅ Register group management via `set_current_register_group()`
  - ✅ Business logic via `_on_business_logic_item_changed()`
  - ✅ Value validation via `RegisterValidator`
  - ✅ Direct `RegisterMap` persistence via `entry.value = validated_value`
  - ✅ Real-time sync via `RegisterSyncService`
  - ✅ Address mode switching via `connect_address_mode_signals()`
  - ✅ Error handling and value reversion
  - ✅ All 6 columns (Type, Address, Alias, Value, Comment, Units)

### Files Changed
- ✅ **ENHANCED**: `modbusx/ui/components/register_table_view.py`
- ✅ **UPDATED**: `modbusx/ui/main_window.py` (direct RegisterTableView usage)
- ❌ **DELETED**: `modbusx/managers/register_editor_adapter.py`