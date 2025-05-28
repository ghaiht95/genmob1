import os
import subprocess
import asyncio
from config import settings
from sqlalchemy.orm import Session
from models import network_config, User, network_config_user
from vpnserver.genrator import generate_wireguard_keys, generate_new_network_range, get_next_subnet, generate_new_port, generate_allowed_ips
from config import settings
class WiregruadVPN:
    def __init__(self):
        self.config_dir = settings.CONFIG_DIR
        

    async def create_network_config(self, Session: Session,):
        available_network_config = Session.query(network_config).filter(network_config.is_active == False).first()
        if available_network_config:
        # خصص الشبكة الموجودة للغرفة
        network_config = available_network_config
        return network_config.network_name
        print(f"استخدام شبكة متاحة بعنوان {network_config_cidr}")
        
        else:
        
            private_key, public_key = generate_wireguard_keys()    # توليد مفاتيح WireGuard
            # إنشاء شبكة جديدة
            network_config = network_config(
                private_key=private_key,
                public_key=public_key,
                server_ip=get_next_subnet(Session),
                port=generate_new_port(Session),
                is_active=True,
                network_name= generate_new_network_range(Session)
            )
            config_content = f"""[Interface]
            PrivateKey = {network_config.private_key}
            Address = {network_config.server_ip}
            ListenPort = {network_config.port}
            SaveConfig = {'true'}
            """
            config_path = os.path.join(self.config_dir, f"{network_config.network_name}.conf")
            os.makedirs(self.config_dir, exist_ok=True)
            with open(config_path, "w") as f:
                f.write(config_content)
                
            Session.add(network_config)
            await Session.commit()
            await Session.refresh(network_config)
            print(f"تم إنشاء شبكة جديدة بعنوان {network_config.network_name}")
            subprocess.run(['wg-quick', 'up', config_path])
            return network_config.network_name
        

    async def down_network_config(self, Session: Session, network_name):
        config_path = os.path.join(self.config_dir, f"{network_name}.conf")
        subprocess.run(['wg-quick', 'down', config_path])
        Session.query(network_config).filter(network_config.network_name == network_name).update({"is_active": False})
        await Session.commit()
        return True

    async def push_user_to_network_config(self, Session: Session, network_name, username,):
        network_config = Session.query(network_config).filter(network_config.network_name == network_name).first()
        private_key = Session.query(User).filter(User.username == username).first().private_key
        public_key = Session.query(User).filter(User.username == username).first().public_key
        allowed_ips = generate_allowed_ips(Session)
        network_config_user = network_config_user(
            network_config_id=network_config.id,
            user_id=Session.query(User).filter(User.username == username).first().id,
            allowed_ips=allowed_ips
        )
        Session.add(network_config_user)
        await Session.commit()
        config_path = os.path.join(self.config_dir, f"{network_name}.conf")
        subprocess.run([
            'sudo', 'wg', 'set', config_path,
            'peer', public_key,
            'allowed-ips', allowed_ips
        ], check=True)
        return True

    async def check_user_in_network_config(self, Session: Session, network_name, username):
        network_config = Session.query(network_config).filter(network_config.network_name == network_name).first()
        network_config_user = Session.query(network_config_user).filter(network_config_user.network_config_id == network_config.id, network_config_user.user_id == Session.query(User).filter(User.username == username).first().id).first()
        if network_config_user:
            config_path = os.path.join(self.config_dir, f"{network_name}.conf")
            public_key = Session.query(User).filter(User.username == username).first().public_key
            subprocess.run([
                'sudo', 'wg', 'set', config_path,
                'peer', public_key,
                'remove'
            ], check=True)
            result = await Session.execute(select(network_config_user).filter(network_config_user.network_config_id == network_config.id, network_config_user.user_id == Session.query(User).filter(User.username == username).first().id))
            network_config_user = result.scalars().first()
            await Session.delete(network_config_user)
            await Session.commit()
            return True
        return False
    
