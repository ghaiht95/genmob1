from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class WireGuardConfig(Base):
    __tablename__ = "wireguard_configs"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)   # اسم الاتصال
    conf_path = Column(Text, nullable=False)                              # مسار ملف التكوين
    public_key = Column(Text, nullable=False)
    private_key = Column(Text, nullable=False)
    internal_ip = Column(String(50), nullable=False)                      # IP داخلي للعميل
    endpoint = Column(String(100), nullable=True)                         # عنوان Endpoint
    allowed_ips = Column(Text, nullable=True)                             # قائمة الشبكات المسموحة
    persistent_keepalive = Column(Integer, default=25)                    # زمن KeepAlive
    status = Column(String(20), default='Unknown')                        # الحالة (Running / Stopped)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<WireGuardConfig(name='{self.name}', internal_ip='{self.internal_ip}', status='{self.status}')>"
        
        
        
        
        from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class WireGuardServerConfig(Base):
    __tablename__ = "wireguard_server_configs"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)  # اسم السيرفر
    conf_path = Column(Text, nullable=False)                             # مسار ملف التكوين
    private_key = Column(Text, nullable=False)                           # المفتاح الخاص
    public_key = Column(Text, nullable=False)                            # المفتاح العام
    listen_port = Column(Integer, nullable=False)                        # منفذ الاستماع
    network_cidr = Column(String(50), nullable=False)                    # الشبكة الداخلية للسيرفر (مثلا 10.0.0.1/24)
    status = Column(String(20), default='Unknown')                       # Running, Stopped, Unknown
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<WireGuardServerConfig(name='{self.name}', listen_port={self.listen_port}, status='{self.status}')>"
        
        
        
        from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class WireguardConfig(Base):
    __tablename__ = "wireguard_configs"

    id = Column(Integer, primary_key=True)
    interface_name = Column(String(50), unique=True, nullable=False)
    private_key = Column(Text, nullable=False)
    public_key = Column(Text, nullable=False)
    ip_address = Column(String(50), unique=True, nullable=False)
    port = Column(Integer, unique=True, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    
    
    import random
import subprocess
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

def generate_key_pair():
    private_key = x25519.X25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return private_bytes.hex(), public_key.hex()

def find_or_create_wireguard_config(session: Session):
    # 1. البحث عن تكوين غير مشغل
    config = session.query(WireguardConfig).filter_by(is_active=False).first()
    if config:
        return config
    
    # 2. توليد تكوين جديد
    private_key, public_key = generate_key_pair()

    # 3. إيجاد IP غير مستخدم
    used_ips = {row.ip_address for row in session.query(WireguardConfig.ip_address).all()}
    base_ip = "10.0.0."
    for i in range(2, 255):
        candidate_ip = f"{base_ip}{i}/24"
        if candidate_ip not in used_ips:
            break
    else:
        raise Exception("No available IPs!")

    # 4. إيجاد منفذ غير مستخدم
    used_ports = {row.port for row in session.query(WireguardConfig.port).all()}
    for port in range(51820, 51900):
        if port not in used_ports:
            break
    else:
        raise Exception("No available ports!")

    # 5. حفظ التكوين الجديد
    new_config = WireguardConfig(
        interface_name=f"wg{random.randint(1000, 9999)}",
        private_key=private_key,
        public_key=public_key,
        ip_address=candidate_ip,
        port=port,
        is_active=False
    )
    session.add(new_config)
    session.commit()

    return new_config
    
    
    
    
    from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('postgresql://user:password@localhost/dbname')
SessionLocal = sessionmaker(bind=engine)

with SessionLocal() as session:
    config = find_or_create_wireguard_config(session)
    print("Config found/created:", config.interface_name, config.ip_address, config.port)
    
    
    
    def get_next_available_ip(session: Session):
    # جلب كل عناوين الـ IP الحالية
    used_ips = [row.ip_address for row in session.query(WireguardConfig.ip_address).all()]
    
    # تحويل العناوين إلى أرقام
    used_numbers = []
    for ip in used_ips:
        last_octet = int(ip.split(".")[3].split("/")[0])
        used_numbers.append(last_octet)

    # إيجاد أكبر رقم مستخدم ثم زيادته بـ 1
    if used_numbers:
        next_number = max(used_numbers) + 1
    else:
        next_number = 2  # نبدأ من 10.0.0.2

    if next_number >= 255:
        raise Exception("No available IPs in the range 10.
        
        
        
        
        from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound
from models import WireguardConfig
from utils import generate_keypair, generate_config_file, allocate_port

def allocate_next_ip(session: Session):
    # جلب كل عناوين IP الحالية من قاعدة البيانات
    used_ips = [row.ip_address for row in session.query(WireguardConfig.ip_address).all()]
    
    # تحديد الأرقام المستخدمة (استخراج الجزء الأخير من عنوان IP)
    used_numbers = [int(ip.split(".")[3].split("/")[0]) for ip in used_ips]
    
    # العثور على أول رقم متاح
    next_number = 2
    while next_number in used_numbers:
        next
        
        
        
        
        def allocate_next_ip(session: Session):
    # استرجاع جميع عناوين IP الموجودة حالياً
    used_ips = [row.ip_address for row in session.query(WireguardConfig.ip_address).all()]
    
    # تحويل الـ IPs إلى tuples من 4 أرقام
    used_tuples = set()
    for ip in used_ips:
        ip_clean = ip.split('/')[0]  # إزالة الـ CIDR
        octets = tuple(map(int, ip_clean.split('.')))
        used_tuples.add(octets)
    
    # نبدأ من 10.0.0.1
    octets = [10, 0, 0, 1]
    
    while True:
        ip_candidate = tuple(octets)
        if ip_candidate not in used_tuples:
            return f"{'.'.join(map(str, ip_candidate))}/24"
        
        # Increment IP
        octets[3] += 1
        for i in reversed(range(4)):
            if octets[i] > 255:
                octets[i] = 0
                if i > 0:
                    octets[i-1] += 1
                else:
                    raise Exception("نفدت عناوين IP المتاحة")
                    
                    
                    
                    
                    def allocate_new_subnet(session: Session):
    used_subnets = [row.subnet for row in session.query(Network.subnet).all()]
    used_octet = set(int(subnet.split('.')[2]) for subnet in used_subnets)
    
    for octet in range(0, 256):
        if octet not in used_octet:
            subnet = f"10.0.{octet}.0/24"
            return subnet
    raise Exception("نفدت الشبكات المتاحة")
    
    
    def allocate_ip_in_subnet(session: Session, subnet: str):
    base_ip = subnet.split('/')[0]
    parts = base_ip.split('.')
    third_octet = int(parts[2])
    base = f"10.0.{third_octet}"
    
    used_ips = [row.ip_address for row in session.query(Device.ip_address).filter(Device.subnet == subnet).all()]
    used_host_ids = set(int(ip.split('.')[-1]) for ip in used_ips)
    
    for host_id in range(2, 255):  # تبدأ من .2 لأن .1 للسيرفر
        if host_id not in used_host_ids:
            return f"{base}.{host_id}"
    raise Exception("نفدت العناوين في هذه الشبكة")
    
    
    
    from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Network(Base):
    __tablename__ = "networks"
    id = Column(Integer, primary_key=True)
    subnet = Column(String, unique=True)  # مثلاً "10.0.0.0/24"
    is_active = Column(Boolean, default=True)
    devices = relationship("Device", back_populates="network")

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    ip_address = Column(String, unique=True)
    config_file = Column(String)
    is_active = Column(Boolean, default=False)
    network_id = Column(Integer, ForeignKey("networks.id"))
    network = relationship("Network", back_populates="devices")
    
    
    
    
    def get_next_subnet(session):
    used_subnets = session.query(Network.subnet).all()
    used_third_octets = set()

    for (subnet,) in used_subnets:
        # subnet format: "10.0.X.0/24"
        third_octet = int(subnet.split('.')[2])
        used_third_octets.add(third_octet)

    for i in range(256):
        if i not in used_third_octets:
            return f"10.0.{i}.0/24"
    raise Exception("No available subnets")
    
    
    
    def get_next_ip(session, network: Network):
    used_ips = session.query(Device.ip_address).filter(Device.network_id == network.id).all()
    used_last_octets = set()
    base = '.'.join(network.subnet.split('.')[:3])  # "10.0.X"

    for (ip,) in used_ips:
        last_octet = int(ip.split('.')[-1])
        used_last_octets.add(last_octet)

    # نبدأ من 2 لأن 1 غالباً مخصص للسيرفر
    for i in range(2, 255):
        if i not in used_last_octets:
            return f"{base}.{i}"
    raise Exception("No available IPs in this subnet")
    
    
    
    
    from sqlalchemy.orm import sessionmaker

Session = sessionmaker(bind=engine)
session = Session()

# 1. حدد أو أنشئ شبكة جديدة
new_subnet = get_next_subnet(session)
network = Network(subnet=new_subnet)
session.add(network)
session.commit()

# 2. احصل على IP جديد ضمن الشبكة
new_ip = get_next_ip(session, network)

# 3. أنشئ جهاز جديد مرتبط بالشبكة
device = Device(ip_address=new_ip, config_file="clientX.conf", network_id=network.id, is_active=False)
session.add(device)
session.commit()


import os
import subprocess
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

Base = declarative_base()

class Network(Base):
    __tablename__ = "networks"
    id = Column(Integer, primary_key=True)
    subnet = Column(String, unique=True)  # مثلا: "10.0.0.0/24"
    is_active = Column(Boolean, default=True)
    devices = relationship("Device", back_populates="network")

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True)
    ip_address = Column(String, unique=True)
    config_file = Column(String)
    is_active = Column(Boolean, default=False)
    private_key = Column(String)
    public_key = Column(String)
    network_id = Column(Integer, ForeignKey("networks.id"))
    network = relationship("Network", back_populates="devices")

# إنشاء اتصال بقاعدة البيانات
DATABASE_URL = "postgresql://username:password@localhost:5432/yourdb"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def get_next_subnet():
    used_subnets = session.query(Network.subnet).all()
    used_third_octets = set()

    for (subnet,) in used_subnets:
        # subnet مثل "10.0.X.0/24"
        third_octet = int(subnet.split('.')[2])
        used_third_octets.add(third_octet)

    for i in range(256):
        if i not in used_third_octets:
            return f"10.0.{i}.0/24"
    raise Exception("No available subnets")

def get_next_ip(network: Network):
    used_ips = session.query(Device.ip_address).filter(Device.network_id == network.id).all()
    used_last_octets = set()
    base = '.'.join(network.subnet.split('.')[:3])  # "10.0.X"

    for (ip,) in used_ips:
        last_octet = int(ip.split('.')[-1])
        used_last_octets.add(last_octet)

    for i in range(2, 255):
        if i not in used_last_octets:
            return f"{base}.{i}"
    raise Exception("No available IPs in this subnet")

def generate_keys():
    # توليد مفتاح خاص وعام عن طريق الأمر wireguard-tools أو openssl (أو generate عبر subprocess)
    # هنا مثال مبسط جدًا باستخدام wg genkey + wg pubkey
    private_key = subprocess.run(["wg", "genkey"], capture_output=True, text=True).stdout.strip()
    public_key_proc = subprocess.run(["wg", "pubkey"], input=private_key, capture_output=True, text=True)
    public_key = public_key_proc.stdout.strip()
    return private_key, public_key

def generate_config(device: Device, server_public_key: str, endpoint: str):
    config = f"""
[Interface]
PrivateKey = {device.private_key}
Address = {device.ip_address}/24
DNS = 8.8.8.8

[Peer]
PublicKey = {server_public_key}
Endpoint = {endpoint}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""
    filename = f"configs/{device.ip_address.replace('.', '_')}.conf"
    os.makedirs("configs", exist_ok=True)
    with open(filename, "w") as f:
        f.write(config)
    return filename

def create_network_and_device(server_public_key: str, endpoint: str):
    # 1- الحصول على شبكة جديدة أو اختيار شبكة موجودة فيها IP متاح
    networks = session.query(Network).all()
    network = None
    for net in networks:
        try:
            # تحقق إذا توجد IP متاحة في الشبكة
            get_next_ip(net)
            network = net
            break
        except:
            continue
    
    if not network:
        # إنشاء شبكة جديدة
        subnet = get_next_subnet()
        network = Network(subnet=subnet)
        session.add(network)
        session.commit()

    # 2- توليد IP جديد في الشبكة
    ip = get_next_ip(network)

    # 3- توليد المفاتيح
    private_key, public_key = generate_keys()

    # 4- إنشاء جهاز جديد
    device = Device(ip_address=ip, private_key=private_key, public_key=public_key, network_id=network.id, is_active=False)
    session.add(device)
    session.commit()

    # 5- توليد ملف التكوين
    config_path = generate_config(device, server_public_key, endpoint)
    device.config_file = config_path
    session.commit()

    print(f"Created device with IP {ip} in network {network.subnet}, config saved to {config_path}")

if __name__ == "__main__":
    Base.metadata.create_all(engine)

    # أدخل public key الخاص بالسيرفر وعنوان endpoint (IP:Port)
    SERVER_PUBLIC_KEY = "PJwX/7cGmrZ2sIIMh+Iq7P6l0MbDINvtTd9m9J7ENn0="
    ENDPOINT = "31.220.80.192:51820"

    create_network_and_device(SERVER_PUBLIC_KEY, ENDPOINT)
    
    
    
    
    
    def create_room(session, room_name):
    # ابحث عن شبكة شاغرة
    network = session.query(Network).filter_by(is_reserved=False).first()
    if not network:
        # توليد شبكة جديدة
        subnet = get_next_subnet(session)
        network = Network(subnet=subnet, is_reserved=True)
        session.add(network)
        session.commit()
    else:
        network.is_reserved = True

    # إنشاء الغرفة
    room = Room(name=room_name, network=network)
    session.add(room)
    session.commit()
    print(f"Room '{room_name}' created with network {network.subnet}")
    
    
    
    
    def close_room(session, room_name):
    room = session.query(Room).filter_by(name=room_name).first()
    if room:
        room.network.is_reserved = False
        room.is_active = False
        session.commit()
        print(f"Room '{room_name}' closed and network {room.network.subnet} released.")
        
        
        
        def get_next_subnet(session):
    used = [int(n.subnet.split('.')[2]) for n in session.query(Network.subnet).all()]
    for i in range(256):
        if i not in used:
            return f"10.0.{i}.0/24"
    raise Exception("No subnets available")
    
    
    
    def get_next_ip_in_network(session, network):
    used = [int(ip.split('.')[-1]) for (ip,) in session.query(Device.ip_address).filter_by(network_id=network.id).all()]
    base = '.'.join(network.subnet.split('.')[:3])
    for i in range(2, 255):
        if i not in used:
            return f"{base}.{i}"
    raise Exception("No IPs available in network")
    
    
    
    from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
import subprocess
import os

Base = declarative_base()

# =============================
# تعريف الجداول
# =============================

class Network(Base):
    __tablename__ = 'networks'
    id = Column(Integer, primary_key=True)
    subnet = Column(String, unique=True)  # مثال: 10.0.1.0/24
    is_reserved = Column(Boolean, default=False)  # هل الشبكة مشغولة؟
    devices = relationship('Device', back_populates='network')
    room = relationship('Room', uselist=False, back_populates='network')

class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    is_active = Column(Boolean, default=True)
    network_id = Column(Integer, ForeignKey('networks.id'))
    network = relationship('Network', back_populates='room')

class Device(Base):
    __tablename__ = 'devices'
    id = Column(Integer, primary_key=True)
    ip_address = Column(String, unique=True)
    is_active = Column(Boolean, default=False)
    private_key = Column(String)
    public_key = Column(String)
    network_id = Column(Integer, ForeignKey('networks.id'))
    network = relationship('Network', back_populates='devices')

# =============================
# إعداد الاتصال بقاعدة البيانات
# =============================
DATABASE_URL = "postgresql://username:password@localhost/yourdatabase"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

# =============================
# وظائف الشبكة
# =============================

def get_next_subnet(session):
    """
    توليد أول شبكة متاحة بالشكل 10.0.N.0/24
    """
    used = [int(n.subnet.split('.')[2]) for n in session.query(Network.subnet).all()]
    for i in range(1, 255):
        if i not in used:
            return f"10.0.{i}.0/24"
    raise Exception("No subnets available.")

def get_next_ip_in_network(session, network):
    """
    توليد أول IP متاح داخل الشبكة
    """
    used = [int(ip.split('.')[-1]) for (ip,) in session.query(Device.ip_address).filter_by(network_id=network.id).all()]
    base = '.'.join(network.subnet.split('.')[:3])
    for i in range(2, 255):
        if i not in used:
            return f"{base}.{i}"
    raise Exception("No IPs available in network.")

def create_room(session, room_name):
    """
    إنشاء غرفة جديدة وتخصيص شبكة لها
    """
    # ابحث عن شبكة شاغرة
    network = session.query(Network).filter_by(is_reserved=False).first()
    if not network:
        subnet = get_next_subnet(session)
        network = Network(subnet=subnet, is_reserved=True)
        session.add(network)
    else:
        network.is_reserved = True
    
    room = Room(name=room_name, network=network)
    session.add(room)
    session.commit()
    print(f"Room '{room_name}' created with network {network.subnet}")

def close_room(session, room_name):
    """
    إغلاق الغرفة وإعادة الشبكة إلى الحالة الشاغرة
    """
    room = session.query(Room).filter_by(name=room_name).first()
    if room:
        room.network.is_reserved = False
        room.is_active = False
        session.commit()
        print(f"Room '{room_name}' closed and network {room.network.subnet} released.")

def add_device_to_room(session, room_name, private_key, public_key):
    """
    إضافة عميل (جهاز) إلى غرفة معينة مع توليد IP تلقائي
    """
    room = session.query(Room).filter_by(name=room_name, is_active=True).first()
    if not room:
        raise Exception(f"Room '{room_name}' not found or inactive.")
    
    network = room.network
    next_ip = get_next_ip_in_network(session, network)
    device = Device(ip_address=next_ip, private_key=private_key, public_key=public_key, network=network, is_active=True)
    session.add(device)
    session.commit()
    print(f"Added device with IP {next_ip} to room '{room_name}'")

# =============================
# أمثلة الاستخدام
# =============================

if __name__ == "__main__":
    session = SessionLocal()
    
    # إنشاء غرفة جديدة
    create_room(session, "RoomA")
    
    # إضافة جهاز إلى غرفة
    add_device_to_room(session, "RoomA", private_key="PRIVATE_KEY_EXAMPLE", public_key="PUBLIC_KEY_EXAMPLE")
    
    # إغلاق الغرفة
    # close_room(session, "RoomA")
    
    
    
    
    
    add_device_to_room(session, "RoomA", "ghaith_user")
    
    
    
    from sqlalchemy.orm import Session
from models import Room, Network  # افترض أن لديك جدول Room و Network
from utils import generate_new_network_range, generate_wireguard_keys  # دوال مساعدة

def create_room_with_network(session: Session, room_name: str):
    """
    إنشاء غرفة جديدة وتخصيص شبكة غير مستخدمة، أو إنشاء شبكة جديدة إذا لم تتوفر.
    """
    # تحقق من وجود غرفة بنفس الاسم
    existing_room = session.query(Room).filter_by(name=room_name).first()
    if existing_room:
        raise Exception(f"Room '{room_name}' موجود بالفعل.")
    
    # ابحث عن شبكة غير مستخدمة
    available_network = session.query(Network).filter_by(is_active=False).first()
    
    if available_network:
        # خصص الشبكة الموجودة للغرفة
        network = available_network
        print(f"استخدام شبكة متاحة بعنوان {network.network_cidr}")
    else:
        # أنشئ شبكة جديدة
        new_network_cidr = generate_new_network_range(session)  # توليد عنوان شبكة جديد
        private_key, public_key = generate_wireguard_keys()    # توليد مفاتيح WireGuard

        network = Network(
            network_cidr=new_network_cidr,
            private_key=private_key,
            public_key=public_key,
            is_active=True
        )
        session.add(network)
        session.commit()
        print(f"تم إنشاء شبكة جديدة بعنوان {new_network_cidr}")

    # أنشئ الغرفة واربطها بالشبكة
    new_room = Room(
        name=room_name,
        network_id=network.id,
        is_active=True
    )
    session.add(new_room)

    # قم بتحديث الشبكة بأنها أصبحت مستخدمة
    network.is_active = True

    session.commit()
    print(f"تم إنشاء الغرفة '{room_name}' وربطها بالشبكة '{network.network_cidr}'")
    
    
    
    
    from sqlalchemy.orm import Session
from models import Room, Network, Client, GameUser  # يفترض أن لديك هذه الجداول
from utils import generate_client_keys, allocate_client_ip

def client_join_room(session: Session, room_id: int, user_id: int):
    """
    معالجة دخول عميل إلى الغرفة وربطه بالشبكة وتوليد IP.
    """
    # البحث عن الغرفة
    room = session.query(Room).filter_by(id=room_id, is_active=True).first()
    if not room:
        raise Exception("الغرفة غير موجودة أو غير نشطة.")
    
    # البحث عن الشبكة المرتبطة بالغرفة
    network = session.query(Network).filter_by(id=room.network_id).first()
    if not network:
        raise Exception("لم يتم العثور على الشبكة المرتبطة بالغرفة.")
    
    # البحث عن المستخدم
    user = session.query(GameUser).filter_by(id=user_id).first()
    if not user:
        raise Exception("المستخدم غير موجود.")
    
    # توليد أو استخدام المفاتيح
    if not user.public_key or not user.private_key:
        user_private, user_public = generate_client_keys()
        user.private_key = user_private
        user.public_key = user_public
        session.commit()
    else:
        user_private = user.private_key
        user_public = user.public_key
    
    # تخصيص IP للعميل
    client_ip = allocate_client_ip(session, network.network_cidr)
    if not client_ip:
        raise Exception("لا يوجد IP متاح في الشبكة.")

    # عنوان IP للسيرفر (بوابة الشبكة)
    server_ip = network.network_cidr.split('/')[0]  # مثال: أول IP من الشبكة

    # إنشاء سجل عميل
    client = Client(
        user_id=user.id,
        room_id=room.id,
        ip_address=client_ip,
        is_active=True
    )
    session.add(client)
    session.commit()

    # إعداد البيانات للعميل
    data = {
        "client_ip": client_ip,
        "server_ip": server_ip,
        "client_private_key": user_private,
        "server_public_key": network.public_key
    }

    return data
    
    
    
    
    from sqlalchemy.orm import Session
from models import Client

def client_leave_room(session: Session, user_id: int, room_id: int):
    """
    معالجة خروج عميل من الغرفة وفصل IP وتحريره.
    """
    # البحث عن السجل الخاص بالعميل في هذه الغرفة
    client = session.query(Client).filter_by(user_id=user_id, room_id=room_id, is_active=True).first()
    
    if not client:
        raise Exception("المستخدم غير موجود في هذه الغرفة أو قد خرج بالفعل.")
    
    # جعل السجل غير نشط (أو يمكن حذف السطر)
    client.is_active = False
    session.commit()
    
    # IP الخاص بالعميل يصبح متاحاً تلقائياً عند البحث لاحقاً
    print(f"تم فصل العميل {user_id} من الغرفة {room_id} و IP {client.ip_address} متاح للاستخدام.")
    
    
    
    
    
    
    
    from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Network(Base):
    __tablename__ = "networks"
    
    id = Column(Integer, primary_key=True)
    network_cidr = Column(String, unique=True, nullable=False)  # مثال: "10.0.0.0/24"
    is_allocated = Column(Boolean, default=False)               # هل الشبكة مخصصة لغرفة؟
    room_id = Column(Integer, nullable=True)                    # رقم الغرفة
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    clients = relationship("Client", back_populates="network")


class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    room_id = Column(Integer, nullable=False)
    network_id = Column(Integer, ForeignKey('networks.id'), nullable=False)
    ip_address = Column(String, nullable=False)
    public_key = Column(String, nullable=False)
    private_key = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    network = relationship("Network", back_populates="clients")
    
    
    
    
    
    def allocate_network(session, room_id):
    network = session.query(Network).filter_by(is_allocated=False).first()
    if not network:
        raise Exception("لا توجد شبكات متاحة حالياً.")
    
    network.is_allocated = True
    network.room_id = room_id
    session.commit()
    return network
    
    
    
    
    def release_network(session, room_id):
    network = session.query(Network).filter_by(room_id=room_id, is_allocated=True).first()
    if network:
        network.is_allocated = False
        network.room_id = None
        session.commit()
        print(f"تم تحرير الشبكة {network.network_cidr} للغرفة {room_id}")
        
        
        
        import ipaddress

def allocate_client_ip(session, network_id):
    network = session.query(Network).filter_by(id=network_id).first()
    if not network:
        raise Exception("الشبكة غير موجودة.")
    
    # تحويل CIDR إلى شبكة
    net = ipaddress.ip_network(network.network_cidr)
    used_ips = {ipaddress.ip_address(c.ip_address) for c in network.clients if c.is_active}

    # تخطي أول IP (Gateway) وأول IP مستخدم
    for ip in net.hosts():
        if ip not in used_ips:
            return str(ip)
    
    raise Exception("لا توجد IPات متاحة داخل الشبكة.")
    
    
    
    def client_join_room(session, user_id, room_id, public_key, private_key):
    network = session.query(Network).filter_by(room_id=room_id, is_allocated=True).first()
    if not network:
        raise Exception("الغرفة لا تملك شبكة مخصصة.")

    ip_address = allocate_client_ip(session, network.id)
    client = Client(
        user_id=user_id,
        room_id=room_id,
        network_id=network.id,
        ip_address=ip_address,
        public_key=public_key,
        private_key=private_key,
        is_active=True
    )
    session.add(client)
    session.commit()
    print(f"تم تخصيص IP {ip_address} للعميل {user_id} في الغرفة {room_id}")
    return client
    
    
    def client_leave_room(session, user_id, room_id):
    client = session.query(Client).filter_by(user_id=user_id, room_id=room_id, is_active=True).first()
    if client:
        client.is_active = False
        session.commit()
        print(f"تم إخراج العميل {user_id} من الغرفة {room_id} و IP {client.ip_address} متاح.")
    
    
        
        
    
    
    
    
    
                    
                    
        
        
        