import os
import subprocess
import asyncio
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import network_config, User, network_config_user
from vpnserver.genrator import generate_wireguard_keys, generate_new_network_range, get_next_subnet, generate_new_port, generate_allowed_ips
from config import settings
import logging

logger = logging.getLogger(__name__)

class WiregruadVPN:
    def __init__(self):
        self.config_dir = settings.CONFIG_DIR
        

    async def create_network_config(self, session: AsyncSession):
        # Find available inactive network config
        result = await session.execute(
            select(network_config).filter(network_config.is_active == False)
        )
        available_network_config = result.scalars().first()
        
        if available_network_config:
            # Use existing network for the room
            available_network_config.is_active = True
            await session.commit()
            return available_network_config.network_name        
        else:
            network_config_cidr = await get_next_subnet(session)
        
            private_key, public_key = generate_wireguard_keys()    # Generate WireGuard keys
            # Create new network
            new_network_config = network_config(
                private_key=private_key,
                public_key=public_key,
                server_ip=await get_next_subnet(session),
                port=await generate_new_port(session),
                is_active=True,
                network_name=await generate_new_network_range(session)
            )
            
            # Create proper WireGuard config format
            config_content = f"""[Interface]
PrivateKey = {new_network_config.private_key.decode() if isinstance(new_network_config.private_key, bytes) else new_network_config.private_key}
Address = {new_network_config.server_ip}
ListenPort = {new_network_config.port}
SaveConfig = true

"""
            config_path = os.path.join(self.config_dir, f"{new_network_config.network_name}.conf")
            os.makedirs(self.config_dir, exist_ok=True)
            
            # Write config file
            with open(config_path, "w") as f:
                f.write(config_content)
            
            # Set proper permissions for WireGuard config
            os.chmod(config_path, 0o600)
                
            session.add(new_network_config)
            await session.commit()
            await session.refresh(new_network_config)
            
            logger.info(f"تم إنشاء شبكة جديدة بعنوان {new_network_config.network_name}")
            
            # Start WireGuard interface with proper error handling
            try:
                result = subprocess.run(['sudo', 'wg-quick', 'up', config_path], 
                                      capture_output=True, text=True, check=True)
                logger.info(f"WireGuard interface started successfully: {result.stdout}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to start WireGuard interface: {e.stderr}")
                # Clean up on failure
                try:
                    os.remove(config_path)
                except:
                    pass
                raise Exception(f"Failed to start VPN interface: {e.stderr}")
            except FileNotFoundError:
                logger.error("wg-quick command not found. Please install WireGuard.")
                raise Exception("WireGuard not installed on system")
                
            return new_network_config.network_name
        

    async def down_network_config(self, session: AsyncSession, network_name):
        config_path = os.path.join(self.config_dir, f"{network_name}.conf")
        
        # Stop WireGuard interface with error handling
        try:
            result = subprocess.run(['sudo', 'wg-quick', 'down', config_path], 
                                  capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.warning(f"Failed to stop WireGuard interface: {result.stderr}")
        except FileNotFoundError:
            logger.error("wg-quick command not found")
        
        # Update network config to inactive
        result = await session.execute(
            select(network_config).filter(network_config.network_name == network_name)
        )
        network_config_obj = result.scalars().first()
        if network_config_obj:
            network_config_obj.is_active = False
            await session.commit()
        return True

    async def delete_network_config(self, session: AsyncSession, network_name):
        """Delete a network config completely from the database"""
        config_path = os.path.join(self.config_dir, f"{network_name}.conf")
        
        # Stop the VPN interface if it's running
        try:
            subprocess.run(['sudo', 'wg-quick', 'down', config_path], 
                         capture_output=True, text=True, check=False)
        except:
            pass
        
        # Remove config file
        try:
            if os.path.exists(config_path):
                os.remove(config_path)
        except:
            pass
        
        # Delete from database
        result = await session.execute(
            select(network_config).filter(network_config.network_name == network_name)
        )
        network_config_obj = result.scalars().first()
        if network_config_obj:
            await session.delete(network_config_obj)
            await session.commit()
        return True

    async def push_user_to_network_config(self, session: AsyncSession, network_name, username):
        # Get network config
        network_result = await session.execute(
            select(network_config).filter(network_config.network_name == network_name)
        )
        network_config_obj = network_result.scalars().first()
        
        if not network_config_obj:
            return False
            
        # Get user
        user_result = await session.execute(
            select(User).filter(User.username == username)
        )
        user = user_result.scalars().first()
        
        if not user:
            return False
            
        private_key = user.private_key
        public_key = user.public_key
        allowed_ips = await generate_allowed_ips(session, network_config_obj.server_ip)
        
        new_network_config_user = network_config_user(
            network_config_id=network_config_obj.id,
            user_id=user.id,
            allowed_ips=allowed_ips
        )
        session.add(new_network_config_user)
        await session.commit()
        
        # Add peer to WireGuard interface
        try:
            public_key_str = public_key.decode() if isinstance(public_key, bytes) else public_key
            result = subprocess.run([
                'sudo', 'wg', 'set', network_name,  # Use interface name, not config path
                'peer', public_key_str,
                'allowed-ips', allowed_ips
            ], capture_output=True, text=True, check=True)
            logger.info(f"Added peer to WireGuard interface: {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to add peer to WireGuard: {e.stderr}")
            return False
            
        return True

    async def check_user_in_network_config(self, session: AsyncSession, network_name, username):
        # Get network config
        network_result = await session.execute(
            select(network_config).filter(network_config.network_name == network_name)
        )
        network_config_obj = network_result.scalars().first()
        
        if not network_config_obj:
            return False
            
        # Get user
        user_result = await session.execute(
            select(User).filter(User.username == username)
        )
        user = user_result.scalars().first()
        
        if not user:
            return False
            
        # Get network config user relation
        network_config_user_result = await session.execute(
            select(network_config_user).filter(
                network_config_user.network_config_id == network_config_obj.id,
                network_config_user.user_id == user.id
            )
        )
        network_config_user_obj = network_config_user_result.scalars().first()
        
        if network_config_user_obj:
            try:
                public_key_str = user.public_key.decode() if isinstance(user.public_key, bytes) else user.public_key
                result = subprocess.run([
                    'sudo', 'wg', 'set', network_name,  # Use interface name, not config path
                    'peer', public_key_str,
                    'remove'
                ], capture_output=True, text=True, check=True)
                logger.info(f"Removed peer from WireGuard interface: {result.stdout}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to remove peer from WireGuard: {e.stderr}")
            
            await session.delete(network_config_user_obj)
            await session.commit()
            return True
        return False
    