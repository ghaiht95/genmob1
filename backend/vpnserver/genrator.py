from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import subprocess
import os
from models import network_config, network_config_user

def generate_wireguard_keys():
    private_key = subprocess.check_output(['wg', 'genkey']).strip()
    public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key).strip()
    return private_key, public_key

async def generate_new_network_range(session: AsyncSession):
    # Get the last network config by ID
    result = await session.execute(
        select(network_config).order_by(network_config.id.desc())
    )
    last_network_config = result.scalars().first()
    
    network_config_number = 1 if not last_network_config else last_network_config.id + 1
    # Use a valid interface name format (no spaces, lowercase)
    return f"wg-room-{network_config_number}"

async def get_next_subnet(session: AsyncSession):
    """
    توليد أول شبكة متاحة بالشكل 10.0.N.0/24
    """
    result = await session.execute(select(network_config))
    network_configs = result.scalars().all()
    used = [int(n.server_ip.split('.')[1]) for n in network_configs if n.server_ip and '.' in n.server_ip]
    
    for i in range(1, 255):
        if i not in used:
            # Return the server IP, not the network address
            return f"10.{i}.0.1/24"
    raise Exception("No subnets available.")

async def generate_new_port(session: AsyncSession):
    result = await session.execute(select(network_config))
    network_configs = result.scalars().all()
    used_ports = {row.port for row in network_configs if row.port}
    
    for port in range(51820, 51900):
        if port not in used_ports:
            return port
    raise Exception("No ports available.")

async def generate_allowed_ips(session: AsyncSession, server_network: str):
    """
    Generate client IP within the server's network range
    For example, if server is 10.20.0.1/24, generate 10.20.0.2/32, 10.20.0.3/32, etc.
    """
    # Extract the network base from server IP (e.g., "10.20.0.1/24" -> "10.20.0")
    server_ip_parts = server_network.split('/')
    if len(server_ip_parts) != 2:
        raise Exception("Invalid server network format")
    
    server_ip = server_ip_parts[0]
    network_base = '.'.join(server_ip.split('.')[:-1])  # "10.20.0"
    
    # Get all used IPs in this network
    result = await session.execute(select(network_config_user))
    network_config_users = result.scalars().all()
    used_ips = [row.allowed_ips for row in network_config_users if row.allowed_ips]
    used_numbers = []
    
    for ip in used_ips:
        try:
            # Extract the last octet from IP addresses like "10.20.0.x/32"
            parts = ip.split('.')
            if len(parts) >= 4 and parts[0] == network_base.split('.')[0] and parts[1] == network_base.split('.')[1] and parts[2] == network_base.split('.')[2]:
                used_numbers.append(int(parts[3].split('/')[0]))
        except (ValueError, IndexError):
            continue
    
    # Start from 2 (1 is usually the server)
    next_number = 2
    while next_number in used_numbers or next_number == int(server_ip.split('.')[-1]):
        next_number += 1
        if next_number >= 255:
            raise Exception(f"No available IP in network {network_base}.x")
    
    # Return client IP as /32 (single host)
    return f"{network_base}.{next_number}/32"    
