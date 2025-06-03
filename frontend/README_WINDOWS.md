# Windows Setup Guide

## Prerequisites

### 1. WireGuard Installation
The application requires WireGuard for VPN functionality.

**Download and Install:**
1. Visit: https://www.wireguard.com/install/
2. Download "WireGuard for Windows"
3. Install using default settings
4. Restart your computer (recommended)

### 2. Administrator Privileges
The application must run with administrator privileges to manage VPN connections.

**How to run as administrator:**
1. Right-click on the application executable
2. Select "Run as administrator"
3. Click "Yes" when prompted

## Automatic Features

- **Admin Check**: The application automatically requests administrator privileges when started
- **WireGuard Detection**: Automatically detects if WireGuard is installed
- **Error Messages**: Provides helpful error messages if setup is incomplete

## Troubleshooting

### "WireGuard Required" Error
- Install WireGuard from the official website
- Restart the application after installation

### "Administrator Rights Required" Error
- Close the application
- Right-click the application icon
- Select "Run as administrator"

### VPN Connection Fails
- Ensure you have internet connectivity
- Check Windows Firewall settings
- Verify WireGuard service is running in Windows Services

## Technical Details

### WireGuard Config Location
- Temporary configs are stored in: `%TEMP%\`
- Configs are automatically cleaned up on disconnect

### Network Configuration
- **Split Tunneling**: Only game server traffic goes through VPN
- **AllowedIPs**: Set to server's network (e.g., `10.23.0.0/24`)
- **Internet Traffic**: Continues through your normal connection
- **Client IP**: Assigned within server's network (e.g., `10.23.0.2/32`)

### Supported WireGuard Versions
- WireGuard for Windows (official client)
- Installed in default locations:
  - `C:\Program Files\WireGuard\wireguard.exe`
  - `C:\Program Files (x86)\WireGuard\wireguard.exe`

### Network Requirements
- Internet connection for initial setup
- UDP port access for WireGuard connections
- Windows Firewall may prompt for permissions

### Example Configuration
```ini
[Interface]
PrivateKey = {your_private_key}
Address = 10.23.0.2/32
DNS = 8.8.8.8

[Peer] 
PublicKey = {server_public_key}
Endpoint = 10.23.0.1:51847
AllowedIPs = 10.23.0.0/24
PersistentKeepalive = 25
```

**Note**: Only traffic to the game server network (10.23.0.0/24) goes through the VPN. Your regular internet browsing continues through your normal connection.

## Features

✅ **Automatic WireGuard Detection**  
✅ **Admin Privilege Checking**  
✅ **User-Friendly Error Messages**  
✅ **Automatic Config Management**  
✅ **Clean Disconnection**  
✅ **Windows-Native Integration** 