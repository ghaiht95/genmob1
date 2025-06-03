from vpn_manager import VPNManager

def simple_vpn():
    # Simple VPN config
    config = {
        'vpn_info': {
            'network_name': 'simple-vpn',
            'server_ip': '10.0.0.1/24',
            'private_key': 'your_private_key_here',
            'server_public_key': 'server_public_key_here',
            'port': 51820
        }
    }

    # Create VPN manager
    vpn = VPNManager(config)

    # Connect to VPN
    print("Connecting to VPN...")
    if vpn.connect():
        print("Connected!")
        
        # Wait for user to press Enter
        input("Press Enter to disconnect...")
        
        # Disconnect
        vpn.disconnect()
        print("Disconnected!")
    else:
        print("Connection failed!")

if __name__ == "__main__":
    simple_vpn() 