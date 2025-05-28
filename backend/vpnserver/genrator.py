from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import subprocess
import os
from models import network_config, network_config_user

def generate_wireguard_keys():
    private_key = subprocess.check_output(['wg', 'genkey']).strip()
    public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key).strip()
    return private_key, public_key

def generate_new_network_range(session):
    last_network_config = session.query(network_config).order_by(network_config.id.desc()).first()
    network_config_number = 1 if not last_network_config else last_network_config.id + 1
    return f"Network {network_config_number}"
def get_next_subnet(session):
    """
    توليد أول شبكة متاحة بالشكل 10.0.N.0/24
    """
    used = [int(n.server_ip.split('.')[2]) for n in session.query(network_config).all()]
    for i in range(1, 255):
        if i not in used:
            return f"10.0.{i}.0/24"
    raise Exception("No subnets available.")
def generate_new_port(session):
    used_ports = {row.port for row in session.query(network_config).all()}
    for port in range(51820, 51900):
        if port not in used_ports:
            return port
    raise Exception("No ports available.")
def generate_allowed_ips(session):
    used_ips = [row.allowed_ips for row in session.query(network_config_user).all()]
    used_numbers = [int(ip.split('.')[2]) for ip in used_ips]
    next_number = 2
    while next_number in used_numbers:
        next_number += 1
        if next_number >= 255:
            raise Exception("لا يوجد IP متاح في النطاق 10.0.0.x")
        return f"10.0.0.{next_number}/24"    
