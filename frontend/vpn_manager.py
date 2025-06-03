import os
import logging
import subprocess
import tempfile
import platform
import json

logger = logging.getLogger(__name__)

class VPNManager:
    def __init__(self, room_data):
        print("[DEBUG] VPNManager.__init__ called")
        self.room_data = room_data
        self.vpn_info = self.room_data.get('vpn_info', {})
        self.network_name = self.vpn_info.get('network_name', 'wg-client')
        self.config_path = None
        self.connected = False
        
        # Clean service name - WireGuard doesn't like special characters
        safe_network_name = self.network_name.replace('-', '_').replace(' ', '_')
        self.service_name = f"WireGuardTunnel${safe_network_name}"
        
        # Try to find WireGuard executable automatically
        self.wireguard_exe = self._find_wireguard_executable()
        
    def _find_wireguard_executable(self):
        """Find WireGuard executable automatically"""
        # First, check if we have a saved configuration
        try:
            config_file = os.path.join(os.path.dirname(__file__), "wireguard_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    saved_path = config.get('wireguard_path', '')
                    if saved_path and os.path.exists(saved_path) and saved_path.lower().endswith('.exe'):
                        logger.info(f"Using configured WireGuard path: {saved_path}")
                        return saved_path
        except Exception as e:
            logger.warning(f"Failed to load WireGuard config: {e}")
        
        # Default paths to check (in order of preference)
        possible_paths = [
            r"C:\Program Files\WireGuard\wireguard.exe",
            r"C:\Program Files (x86)\WireGuard\wireguard.exe",
            os.path.join(os.path.dirname(__file__), "tools", "WireguardPortable", "App", "x64", "wireguard.exe")
        ]
        
        # Check each possible path first
        for path in possible_paths:
            try:
                if os.path.exists(path) and path.lower().endswith('.exe'):
                    logger.info(f"Found WireGuard at: {path}")
                    return path
            except:
                continue
        
        # Try to find wireguard.exe in PATH
        try:
            result = subprocess.run(['where', 'wireguard.exe'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                found_paths = result.stdout.strip().split('\n')
                for found_path in found_paths:
                    found_path = found_path.strip()
                    if os.path.exists(found_path) and found_path.lower().endswith('.exe'):
                        logger.info(f"Found WireGuard.exe in PATH: {found_path}")
                        return found_path
        except:
            pass
        
        # Also try searching for just 'wireguard' in case it's there without extension (but add .exe)
        try:
            result = subprocess.run(['where', 'wireguard'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                found_paths = result.stdout.strip().split('\n')
                for found_path in found_paths:
                    found_path = found_path.strip()
                    # If found path doesn't have .exe, try adding it
                    if not found_path.lower().endswith('.exe'):
                        exe_path = found_path + '.exe'
                        if os.path.exists(exe_path):
                            logger.info(f"Found WireGuard executable (added .exe): {exe_path}")
                            return exe_path
                    elif os.path.exists(found_path):
                        logger.info(f"Found WireGuard executable: {found_path}")
                        return found_path
        except:
            pass
        
        # If nothing found, use the original portable path as final fallback
        fallback_path = r"C:\Users\GHAIT\Desktop\fort\new\for\tools\WireguardPortable\App\x64\wireguard.exe"
        logger.warning(f"WireGuard not found automatically, using fallback: {fallback_path}")
        logger.warning("💡 Run 'python wireguard_config.py' to configure WireGuard path")
        return fallback_path
        
    def _create_wireguard_config(self):
        """Create WireGuard configuration file for Windows"""
        try:
            # Debug: Log the VPN info being used
            logger.info(f"Creating WireGuard config with VPN info: {self.vpn_info}")
            
            # Create config in temp directory with safe filename
            temp_dir = tempfile.gettempdir()
            safe_network_name = self.network_name.replace('-', '_').replace(' ', '_')
            config_filename = f"{safe_network_name}.conf"
            self.config_path = os.path.join(temp_dir, config_filename)
            
            # Get VPN configuration values with proper None handling
            server_ip = self.vpn_info.get('server_ip', '') or ''
            private_key = self.vpn_info.get('private_key', '') or ''
            server_public_key = self.vpn_info.get('server_public_key', '') or ''
            port = self.vpn_info.get('port', 51820) or 51820
            
            logger.info(f"VPN config values: server_ip='{server_ip}', private_key='{len(private_key) if private_key else 0} chars', server_public_key='{len(server_public_key) if server_public_key else 0} chars', port={port}")
            
            # Check for required values
            if not server_ip:
                logger.error("server_ip is missing or empty")
                return False
            if not private_key:
                logger.error("private_key is missing or empty")
                return False
            if not server_public_key:
                logger.error("server_public_key is missing or empty")
                return False
                
            # Create WireGuard config content
            config_content = f"""[Interface]
PrivateKey = {private_key}
Address = {server_ip}
DNS = 8.8.8.8

[Peer]
PublicKey = {server_public_key}
Endpoint = {server_ip.split('/')[0]}:{port}
AllowedIPs = {server_ip}
PersistentKeepalive = 25
"""
            
            # Write config file
            with open(self.config_path, 'w') as f:
                f.write(config_content)
                
            logger.info(f"WireGuard config created at: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create WireGuard config: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def _check_wireguard_available(self):
        """Check if WireGuard executable is available"""
        if not os.path.exists(self.wireguard_exe):
            logger.error(f"WireGuard executable not found at: {self.wireguard_exe}")
            print(f"❌ WireGuard executable not found at: {self.wireguard_exe}")
            print("💡 Please install WireGuard from: https://www.wireguard.com/install/")
            print("🔍 Or update the path to your WireGuard installation")
            
            # Try to provide helpful suggestions
            self._suggest_wireguard_locations()
            return False
        return True
    
    def _suggest_wireguard_locations(self):
        """Suggest where user might find WireGuard"""
        print("\n🔍 Searching for WireGuard installations...")
        
        search_paths = [
            r"C:\Program Files\WireGuard",
            r"C:\Program Files (x86)\WireGuard",
            r"C:\Users\*\Desktop\*\WireGuard*",
            r"C:\Users\*\Downloads\WireGuard*"
        ]
        
        found_locations = []
        
        for search_path in search_paths[:2]:  # Only check Program Files folders
            try:
                if os.path.exists(search_path):
                    wireguard_exe = os.path.join(search_path, "wireguard.exe")
                    if os.path.exists(wireguard_exe):
                        found_locations.append(wireguard_exe)
                        print(f"✅ Found WireGuard at: {wireguard_exe}")
            except:
                pass
        
        if found_locations:
            print(f"\n💡 Try updating your WireGuard path to one of the above locations")
        else:
            print("❌ No WireGuard installations found in common locations")
            print("📥 Please download and install WireGuard from: https://www.wireguard.com/install/")
            print("🏠 Or use WireGuard Portable version")
        
        print("\n🔧 Current path being used:")
        print(f"   {self.wireguard_exe}")

    def install_tunnel(self, conf_path):
        """Install WireGuard tunnel service"""
        if not self._check_wireguard_available():
            return False
            
        try:
            # Use the correct WireGuard command syntax: /installtunnelservice "config_path"
            cmd = f'"{self.wireguard_exe}" /installtunnelservice "{conf_path}"'
            logger.info(f"Running command: {cmd}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            if result.returncode == 0:
                logger.info("Tunnel installed successfully")
                print("✅ Tunnel installed successfully")
                return True
            else:
                error_msg = stderr or stdout or "No error message"
                logger.error(f"Failed to install tunnel: {error_msg}")
                print(f"❌ Failed to install tunnel: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"Exception during tunnel installation: {e}")
            print(f"❌ Exception during tunnel installation: {e}")
            return False

    def start_tunnel(self, service_name):
        """Start WireGuard tunnel service"""
        try:
            cmd = f'sc start "{service_name}"'
            logger.info(f"Running command: {cmd}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            if "SUCCESS" in stdout or result.returncode == 0:
                logger.info(f"Tunnel {service_name} started")
                print(f"✅ Tunnel {service_name} started")
                return True
            elif "FAILED 1056" in stderr or "already running" in stderr.lower():
                # Service is already running
                logger.info(f"Tunnel {service_name} is already running")
                print(f"ℹ️ Tunnel {service_name} is already running")
                return True
            else:
                logger.error(f"Failed to start tunnel {service_name}: {stdout} {stderr}")
                print(f"❌ Failed to start tunnel {service_name}: {stdout} {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Exception during tunnel start: {e}")
            print(f"❌ Exception during tunnel start: {e}")
            return False

    def stop_tunnel(self, service_name):
        """Stop WireGuard tunnel service"""
        try:
            cmd = f'sc stop "{service_name}"'
            logger.info(f"Running command: {cmd}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            if "SUCCESS" in stdout or result.returncode == 0:
                logger.info(f"Tunnel {service_name} stopped")
                print(f"✅ Tunnel {service_name} stopped")
                return True
            elif "FAILED 1062" in stderr or "not started" in stderr.lower():
                # Service is already stopped
                logger.info(f"Tunnel {service_name} was already stopped")
                print(f"ℹ️ Tunnel {service_name} was already stopped")
                return True
            else:
                logger.warning(f"Failed to stop tunnel {service_name}: {stdout} {stderr}")
                print(f"⚠️ Failed to stop tunnel {service_name}: {stdout} {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Exception during tunnel stop: {e}")
            print(f"❌ Exception during tunnel stop: {e}")
            return False

    def uninstall_tunnel(self, service_name):
        """Uninstall WireGuard tunnel service"""
        if not self._check_wireguard_available():
            return False
            
        try:
            # Use the correct WireGuard command syntax: /uninstalltunnelservice "service_name"
            cmd = f'"{self.wireguard_exe}" /uninstalltunnelservice "{service_name}"'
            logger.info(f"Running command: {cmd}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            
            if result.returncode == 0:
                logger.info(f"Tunnel service {service_name} uninstalled successfully")
                print(f"✅ Tunnel service {service_name} uninstalled successfully")
                return True
            else:
                # Sometimes uninstall "fails" but actually works, or service doesn't exist
                error_msg = stderr or stdout or "No error message"
                if "does not exist" in error_msg.lower() or "not found" in error_msg.lower():
                    logger.info(f"Tunnel service {service_name} was not installed")
                    print(f"ℹ️ Tunnel service {service_name} was not installed")
                    return True
                else:
                    logger.warning(f"Failed to uninstall tunnel service {service_name}: {error_msg}")
                    print(f"⚠️ Failed to uninstall tunnel service {service_name}: {error_msg}")
                    return False
                    
        except Exception as e:
            logger.error(f"Exception during tunnel uninstallation: {e}")
            print(f"❌ Exception during tunnel uninstallation: {e}")
            return False

    def get_all_wireguard_services(self):
        """Get list of all WireGuard tunnel services"""
        try:
            cmd = 'sc query type= service state= all | findstr "WireGuardTunnel"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            services = []
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'SERVICE_NAME:' in line:
                        service_name = line.split('SERVICE_NAME:')[1].strip()
                        if service_name.startswith('WireGuardTunnel'):
                            services.append(service_name)
            
            return services
        except Exception as e:
            logger.error(f"Failed to get WireGuard services: {e}")
            return []

    def cleanup_old_tunnels(self):
        """Clean up old WireGuard tunnel services"""
        print("🧹 Checking for old WireGuard tunnels...")
        logger.info("Checking for old WireGuard tunnels...")
        
        old_services = self.get_all_wireguard_services()
        
        if not old_services:
            print("✅ No old tunnels found")
            logger.info("No old WireGuard tunnels found")
            return True
        
        print(f"🔍 Found {len(old_services)} existing tunnel(s):")
        for service in old_services:
            print(f"   - {service}")
        
        cleanup_success = True
        for service_name in old_services:
            print(f"🗑️ Cleaning up: {service_name}")
            logger.info(f"Cleaning up old tunnel: {service_name}")
            
            # Try to stop first
            if not self.stop_tunnel(service_name):
                logger.warning(f"Failed to stop old tunnel: {service_name}")
            
            # Then uninstall
            if not self.uninstall_tunnel(service_name):
                logger.warning(f"Failed to uninstall old tunnel: {service_name}")
                cleanup_success = False
            else:
                print(f"✅ Cleaned up: {service_name}")
        
        if cleanup_success:
            print("🎉 All old tunnels cleaned up successfully!")
            logger.info("All old tunnels cleaned up successfully")
        else:
            print("⚠️ Some tunnels could not be cleaned up")
            logger.warning("Some old tunnels could not be cleaned up")
        
        return cleanup_success

    def check_tunnel_running(self, service_name=None):
        """Check if a specific tunnel (or current tunnel) is running"""
        if service_name is None:
            service_name = self.service_name
            
        try:
            cmd = f'sc query "{service_name}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                stdout = result.stdout or ""
                if "RUNNING" in stdout:
                    return True
                elif "STOPPED" in stdout:
                    return False
            
            return False
        except Exception as e:
            logger.error(f"Failed to check tunnel status: {e}")
            return False

    def connect(self):
        """Connect to VPN with improved cleanup and checks"""
        print("[DEBUG] VPNManager.connect called")
        try:
            # Check if we have the minimum required VPN info
            if not self.vpn_info:
                logger.warning("No VPN info available - skipping VPN connection")
                print("⚠️ No VPN info available - skipping VPN connection")
                return False
            
            # Check for required VPN configuration values
            required_fields = ['server_ip', 'private_key', 'server_public_key']
            missing_fields = []
            
            for field in required_fields:
                value = self.vpn_info.get(field)
                if not value or value is None:
                    missing_fields.append(field)
            
            if missing_fields:
                logger.warning(f"Missing required VPN fields: {missing_fields}")
                print(f"⚠️ Missing required VPN fields: {missing_fields}")
                print("💡 VPN connection skipped - room will work without VPN")
                return False
            
            # Check if WireGuard is available
            if not self._check_wireguard_available():
                print(f"❌ WireGuard not found at: {self.wireguard_exe}")
                print("💡 Please install WireGuard or update the path")
                return False
            
            # 🆕 STEP 1: Clean up old tunnels first
            print("🧹 Cleaning up old tunnels...")
            self.cleanup_old_tunnels()
            
            # 🆕 STEP 2: Check if current tunnel is already running
            if self.check_tunnel_running():
                print(f"ℹ️ Tunnel {self.service_name} is already running")
                logger.info(f"Tunnel {self.service_name} is already running")
                print("🛑 Stopping existing tunnel...")
                self.stop_tunnel(self.service_name)
                print("🗑️ Uninstalling existing tunnel...")
                self.uninstall_tunnel(self.service_name)
            
            # STEP 3: Create config file
            if not self._create_wireguard_config():
                logger.error("Failed to create WireGuard configuration")
                return False
                
            # STEP 4: Install tunnel service
            logger.info("Installing WireGuard tunnel...")
            print("📦 Installing WireGuard tunnel...")
            if not self.install_tunnel(self.config_path):
                return False
                
            # STEP 5: Start the tunnel service
            logger.info("Starting WireGuard tunnel...")
            print("🚀 Starting WireGuard tunnel...")
            if self.start_tunnel(self.service_name):
                logger.info("WireGuard connected successfully")
                print("🎉 WireGuard connected successfully!")
                self.connected = True
                
                # 🆕 STEP 6: Verify connection
                if self.check_tunnel_running():
                    print("✅ Tunnel is running and ready!")
                    return True
                else:
                    print("⚠️ Tunnel was started but is not running properly")
                    logger.warning("Tunnel was started but is not running properly")
                    return False
            else:
                logger.error("Failed to start WireGuard tunnel")
                print("❌ Failed to start WireGuard tunnel")
                # Try to clean up the installed service
                self.uninstall_tunnel(self.service_name)
                return False
            
        except Exception as e:
            logger.error(f"Unexpected error connecting to VPN: {e}")
            print(f"❌ Unexpected error connecting to VPN: {e}")
            self.connected = False
            return False

    def disconnect(self, cleanup=False):
        """Disconnect from VPN with improved cleanup"""
        print("[DEBUG] VPNManager.disconnect called")
        try:
            # Stop the tunnel service
            logger.info("Stopping WireGuard tunnel...")
            print("🛑 Stopping WireGuard tunnel...")
            self.stop_tunnel(self.service_name)
            
            # Uninstall the tunnel service
            logger.info("Uninstalling WireGuard tunnel...")
            print("🗑️ Uninstalling WireGuard tunnel...")
            self.uninstall_tunnel(self.service_name)
            
            # Clean up config file
            if self.config_path and os.path.exists(self.config_path):
                try:
                    os.remove(self.config_path)
                    logger.info("WireGuard config file removed")
                    print("🧹 WireGuard config file removed")
                except Exception as e:
                    logger.warning(f"Failed to remove config file: {e}")
            
            # 🆕 If cleanup is requested, remove ALL WireGuard tunnels
            if cleanup:
                print("🧹 Performing full cleanup of all tunnels...")
                self.cleanup_old_tunnels()
                    
            self.connected = False
            self.config_path = None
            print("✅ VPN disconnected successfully")
            
        except Exception as e:
            logger.error(f"Error during WireGuard disconnection: {e}")
            print(f"❌ Error during WireGuard disconnection: {e}")

    def get_status(self):
        """Get VPN connection status"""
        return "Connected" if self.connected else "Disconnected"

    def get_tunnel_info(self):
        """Get information about the current tunnel configuration"""
        return {
            'service_name': self.service_name,
            'network_name': self.network_name,
            'config_path': self.config_path,
            'connected': self.connected,
            'wireguard_exe': self.wireguard_exe
        }

    def set_wireguard_path(self, custom_path):
        """Manually set WireGuard executable path"""
        if os.path.exists(custom_path):
            self.wireguard_exe = custom_path
            logger.info(f"WireGuard path updated to: {custom_path}")
            print(f"✅ WireGuard path updated to: {custom_path}")
            return True
        else:
            logger.error(f"Invalid WireGuard path: {custom_path}")
            print(f"❌ Invalid WireGuard path: {custom_path}")
            return False
    
    @staticmethod
    def find_wireguard_installations():
        """Find all WireGuard installations on the system"""
        print("🔍 Searching for WireGuard installations...")
        
        search_locations = [
            (r"C:\Program Files\WireGuard\wireguard.exe", "Official Installation (64-bit)"),
            (r"C:\Program Files (x86)\WireGuard\wireguard.exe", "Official Installation (32-bit)"),
        ]
        
        # Add user-specific locations
        try:
            import os
            user_profile = os.environ.get('USERPROFILE', '')
            if user_profile:
                search_locations.extend([
                    (os.path.join(user_profile, "Desktop", "WireGuard", "wireguard.exe"), "Desktop Installation"),
                    (os.path.join(user_profile, "Downloads", "WireGuard", "wireguard.exe"), "Downloads Folder"),
                    (os.path.join(user_profile, "Desktop", "fort", "new", "for", "tools", "WireguardPortable", "App", "x64", "wireguard.exe"), "Portable Installation"),
                ])
        except:
            pass
        
        found_installations = []
        
        for path, description in search_locations:
            if os.path.exists(path):
                found_installations.append((path, description))
                print(f"✅ {description}: {path}")
        
        if not found_installations:
            print("❌ No WireGuard installations found")
            print("📥 Download WireGuard from: https://www.wireguard.com/install/")
        
        return found_installations
