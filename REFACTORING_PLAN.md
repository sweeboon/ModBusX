# MVC Refactoring Plan for ModBusX

## Current Structure Issues
- Business logic scattered in UI folder
- Dialogs contain both view and controller logic
- Models mixed with UI components
- No clear separation of concerns

## Proposed New Structure

```
modbusx/
├── models/                          # DATA LAYER
│   ├── __init__.py
│   ├── register_entry.py           # RegisterEntry class (moved from register_map.py)
│   ├── register_map.py             # RegisterMap class (refactored)
│   ├── register_group.py           # RegisterGroup model
│   ├── multi_type_group.py         # MultiTypeRegisterGroup model only
│   └── connection_model.py         # Connection data model
├── services/                        # BUSINESS LOGIC LAYER
│   ├── __init__.py
│   ├── register_validator.py       # Validation logic (moved from ui/)
│   ├── register_group_service.py   # Group operations (from register_group_manager.py)
│   ├── bulk_operations_service.py  # Bulk ops logic (from bulk_operations.py)
│   ├── connection_service.py       # Connection management logic
│   └── import_export_service.py    # File I/O operations
├── controllers/                     # CONTROLLER LAYER
│   ├── __init__.py
│   ├── main_controller.py          # Main application controller
│   ├── connection_controller.py    # Connection management controller
│   ├── register_editor_controller.py # Register editing controller
│   ├── bulk_operations_controller.py # Bulk operations controller
│   └── register_group_controller.py  # Register group management controller
├── ui/                             # VIEW LAYER (UI ONLY)
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── register_group_dialog.py     # Pure UI - no business logic
│   │   ├── bulk_operations_dialog.py    # Pure UI - no business logic
│   │   ├── multi_type_group_dialog.py   # Pure UI - no business logic
│   │   └── connect_dialog.py            # Pure UI
│   ├── components/
│   │   ├── __init__.py
│   │   ├── register_table_view.py       # Table display component
│   │   ├── connection_tree_view.py      # Tree display component
│   │   └── main_window.py              # Main window (refactored)
│   ├── *.ui                            # Qt Designer files
│   └── resources_rc.py
├── core.py                         # Main application entry
├── config.py                       # Configuration
└── logger.py                       # Logging
```

## Benefits of This Structure

### 1. **Clear Separation of Concerns**
- **Models**: Pure data structures and domain logic
- **Services**: Business logic and operations
- **Controllers**: Coordinate between models/services and views
- **Views**: Pure UI components with no business logic

### 2. **Improved Testability**
- Business logic can be tested independently of UI
- Controllers can be mocked for UI testing
- Services can be unit tested easily

### 3. **Better Maintainability**
- Changes to business logic don't affect UI
- UI changes don't affect business logic
- Clear responsibility boundaries

### 4. **Loose Coupling**
- Views only know about controllers
- Controllers know about services and models
- Services only know about models

## Migration Strategy

### Phase 1: Extract Models
1. Create `models/` folder
2. Move `RegisterEntry` and `RegisterMap` to models
3. Create pure model classes for groups and connections

### Phase 2: Extract Services
1. Create `services/` folder
2. Move business logic from UI classes to services
3. Remove business logic from dialog classes

### Phase 3: Create Controllers
1. Create `controllers/` folder
2. Extract controller logic from UI classes
3. Make controllers mediate between services and views

### Phase 4: Clean Views
1. Remove all business logic from UI classes
2. Make views pure Qt components
3. Connect views to controllers only

## Example: Before vs After

### Before (Current):
```python
class RegisterGroupDialog(QDialog):
    def __init__(self):
        # UI setup
        # Business logic setup
        # Validation logic
        # Database operations
        
    def create_group(self):
        # UI updates
        # Validation
        # Database operations
        # More UI updates
```

### After (Proposed):
```python
# VIEW (UI Only)
class RegisterGroupDialog(QDialog):
    def __init__(self, controller):
        self.controller = controller
        # UI setup only
        
    def create_group(self):
        data = self.get_form_data()
        self.controller.create_group(data)

# CONTROLLER
class RegisterGroupController:
    def __init__(self, service, view):
        self.service = service
        self.view = view
        
    def create_group(self, data):
        if self.service.validate_group(data):
            group = self.service.create_group(data)
            self.view.show_success(group)
        else:
            self.view.show_error("Validation failed")

# SERVICE (Business Logic)
class RegisterGroupService:
    def __init__(self, validator, repository):
        self.validator = validator
        self.repository = repository
        
    def validate_group(self, data):
        return self.validator.validate(data)
        
    def create_group(self, data):
        return self.repository.save(RegisterGroup(data))
```

## Implementation Priority

1. **High Priority**: Extract business logic from UI (Services)
2. **Medium Priority**: Create controller layer
3. **Low Priority**: Refactor models (already mostly separated)
