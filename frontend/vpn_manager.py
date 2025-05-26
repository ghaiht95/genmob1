import os
import logging
import subprocess
import time
import platform # Added for potential future use, though not in current selection
import json # Added for potential future use, though not in current selection

logger = logging.getLogger(__name__)

class VPNManager:
    def __init__(self, room_data):
        print("[DEBUG] VPNManager.__init__ called")
        self.room_data = room_data
        self.tools_path = os.path.join(os.getcwd(), "tools")
        self.vpncmd_path = os.path.join(self.tools_path, "vpncmd.exe")
        self.vpnclient_path = os.path.join(self.tools_path, "vpnclient.exe")
        self.nicname = "VPN"
        # Ensure 'vpn_info' key exists before accessing sub-keys
        vpn_info = self.room_data.get('vpn_info', {})
        self.account = f"room_{vpn_info.get('hub', 'default_hub')}" # Provide default if hub is missing
        self.server_ip = vpn_info.get('server_ip', '127.0.0.1') # Provide default
        self.port = vpn_info.get('port', 443)
        self.vpncmd_server = "localhost"

    def _run_silent(self, cmd):
        print("[DEBUG] VPNManager._run_silent called")
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        CREATE_NO_WINDOW = 0x08000000

        return subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            startupinfo=startupinfo,
            shell=False
        )

    def _check_service_exists(self):
        result = subprocess.run(["sc", "query", "SEVPNCLIENT"], capture_output=True, text=True)
        return "SERVICE_NAME: SEVPNCLIENT" in result.stdout

    def _account_exists(self):
        print("[DEBUG] VPNManager._account_exists called")

        result = subprocess.run([
            self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountList"
        ], capture_output=True, text=True)
        return self.account in result.stdout

    def connect(self):
        print("[DEBUG] VPNManager.connect called")
        try:
            # 1. Register service (once)
            if not self._check_service_exists():
                logger.info("Registering VPN Client service...")
                self._run_silent([self.vpnclient_path, "/install"])

            # 2. Start service using sc (no GUI ever)
            logger.info("Starting VPN Client service silently...")
            self._run_silent(["sc", "start", "SEVPNCLIENT"])

            # 3. Delete existing account if it exists
            if self._account_exists():
                logger.info(f"Deleting existing VPN account: {self.account}")
                self._run_silent([
                    self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDelete", self.account
                ])

            # 4. Create new account
            logger.info(f"Creating VPN account: {self.account}")
            # Ensure 'vpn_info' and its sub-keys exist before use
            vpn_info = self.room_data.get('vpn_info', {})
            hub = vpn_info.get('hub', 'default_hub')
            username = vpn_info.get('username', 'default_user')
            password = vpn_info.get('password', 'default_pass')

            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountCreate", self.account,
                f"/SERVER:{self.server_ip}:{self.port}",
                f"/HUB:{hub}",
                f"/USERNAME:{username}",
                f"/NICNAME:{self.nicname}"
            ])
            logger.info("Setting VPN password...")
            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountPasswordSet", self.account,
                f"/PASSWORD:{password}", "/TYPE:standard"
            ])

            # 5. Connect
            logger.info("Connecting to VPN...")
            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountConnect", self.account
            ])
            logger.info("VPN connected successfully.")
            return True

        except Exception as e:
            logger.error(f"[VPN] Unexpected error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def disconnect(self, cleanup=False):
        print("[DEBUG] VPNManager.disconnect called")
        try:
            logger.info("Disconnecting from VPN...")
            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDisconnect", self.account
            ])
            self._run_silent([
                self.vpncmd_path, self.vpncmd_server, "/CLIENT", "/CMD", "AccountDelete", self.account
            ])

            logger.info("VPN disconnected successfully.")

            if cleanup:
                logger.info("Cleaning up VPN service...")
                self._run_silent(["sc", "stop", "SEVPNCLIENT"])
                self._run_silent([self.vpnclient_path, "/uninstall"])
                logger.info("VPN client service removed completely.")

        except Exception as e:
            logger.error(f"[VPN] Error during disconnection: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # Added placeholder for potential future methods from the original vpn_manager.py
    def _threaded_connect(self):
        """Connect to VPN in a separate thread"""
        try:
            # Simulate connection time
            time.sleep(2)
            # self.connected = True # Assuming 'connected' is an instance variable
            logger.info("VPN connected successfully")
        except Exception as e:
            # self.error_message = str(e) # Assuming 'error_message' is an instance variable
            logger.error(f"VPN connection failed: {e}")
            # self.connected = False

    def get_status(self):
        """Get the current VPN status"""
        # if self.connected: # Assuming 'connected' is an instance variable
        #     return "Connected"
        # elif self.error_message: # Assuming 'error_message' is an instance variable
        #     return f"Error: {self.error_message}"
        # else:
        return "Disconnected" # Default status
