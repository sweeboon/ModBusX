"""
ModBusX Main Application

Entry point for the ModBusX application with SOA architecture.
"""

import sys
from typing import Optional
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QFont

from .ui.main_window import MainWindow  # Use original main window
from .logger import initialize_global_logger, get_logger

class ModBusXApplication(QObject):
    """Main application class."""
    
    # Application-level signals
    application_starting = pyqtSignal()
    application_ready = pyqtSignal()
    application_closing = pyqtSignal()
    
    def __init__(self, qt_app: QApplication, parent=None):
        super().__init__(parent)
        self.qt_app = qt_app
        self.main_window: Optional[MainWindow] = None
        self.logger = get_logger("ModBusXApplication")
        self._shutdown_called = False
        
    def initialize(self):
        """Initialize the application."""
        self.logger.info("Starting ModBusX application initialization")
        self.application_starting.emit()
        
        # Create main window 
        self.logger.debug("Creating main window")
        self.main_window = MainWindow()
        
        # Connect application-level signals
        self._connect_signals()
        
        self.logger.info("ModBusX application initialization complete")
        self.application_ready.emit()
        
    def run(self) -> int:
        """Run the application."""
        if not self.main_window:
            self.logger.error("Application not initialized. Call initialize() first.")
            raise RuntimeError("Application not initialized. Call initialize() first.")
        
        # Show main window
        self.logger.info("Showing main window and starting Qt event loop")
        self.main_window.show()
        
        # Start Qt event loop
        return self.qt_app.exec_()
    
    def shutdown(self):
        """Shutdown the application gracefully."""
        if self._shutdown_called:
            self.logger.debug("Shutdown already called, skipping duplicate shutdown")
            return
            
        self._shutdown_called = True
        self.logger.info("Shutting down ModBusX application")
        self.application_closing.emit()
        
        if self.main_window:
            self.logger.debug("Closing main window")
            self.main_window.close()
        
        self.logger.info("ModBusX application shutdown complete")
    
    def _connect_signals(self):
        """Connect application-level signals."""
        # No signals to connect in simplified version
        pass

def create_application(argv: list = None):
    """Create and configure the ModBusX application."""
    if argv is None:
        argv = sys.argv
    
    # Initialize logging first
    logger = initialize_global_logger()
    logger.info("Creating ModBusX application")
    
    
    # Create Qt application
    qt_app = QApplication(argv)
    qt_app.setApplicationName("ModBusX")
    qt_app.setApplicationVersion("2.0.0")
    qt_app.setOrganizationName("ModBusX Development Project")
    
    logger.debug("Qt application created with name: %s, version: %s", 
                qt_app.applicationName(), qt_app.applicationVersion())
    
    # Set consistent Yu Gothic UI font across the application
    default_font = QFont("Yu Gothic UI", 9)
    qt_app.setFont(default_font)
    logger.debug("Set default font to Yu Gothic UI, size 9")
    
    # Create ModBusX application
    app = ModBusXApplication(qt_app)
    logger.info("ModBusX application instance created")
    
    return qt_app, app

def main(argv: list = None) -> int:
    """Main entry point for the application."""
    logger = get_logger("main")
    
    try:
        qt_app, app = create_application(argv)
        
        # Initialize with MVC architecture
        logger.info("Starting application initialization")
        app.initialize()
        
        # Run the application
        logger.info("Running application main loop")
        return app.run()
        
    except Exception as e:
        logger.exception("Critical application error: %s", str(e))
        return 1
    
    finally:
        # Ensure cleanup
        logger.info("Performing application cleanup")
        try:
            app.shutdown()
        except Exception as e:
            logger.exception("Error during application shutdown: %s", str(e))

if __name__ == "__main__":
    sys.exit(main())