# frontend/main.py
import sys
import os
import logging
from PyQt5 import QtWidgets
from auth import AuthApp
from settings_window import SettingsWindow
from translator import Translator, _
from api_client import api_client
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_application():
    """Initialize application settings and environment"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Set application style
        app = QtWidgets.QApplication(sys.argv)
        app.setStyle('Fusion')  # Use Fusion style for consistent look across platforms
        
        # Apply saved settings
        SettingsWindow.apply_settings(app)
        
        # Initialize API client
        api_base_url = os.getenv('API_BASE_URL')
        if not api_base_url:
            logger.error("API_BASE_URL not found in environment variables")
            raise ValueError("API_BASE_URL environment variable is required")
            
        api_client.set_base_url(api_base_url)
        
        return app
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

def main():
    try:
        # Initialize application
        app = initialize_application()
        
        # Create and show main window
        window = AuthApp()
        window.show()
        
        # Start event loop
        sys.exit(app.exec_())
        
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        QtWidgets.QMessageBox.critical(
            None,
            _("ui.messages.error", "Error"),
            _("ui.messages.startup_error", "Failed to start application: {error}", error=str(e))
        )
        sys.exit(1)

if __name__ == "__main__":
    main()
