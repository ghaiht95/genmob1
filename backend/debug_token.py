from jose import jwt
from datetime import datetime, timedelta
from config import settings

# Simulate the test user
class TestUser:
    def __init__(self):
        self.username = "testuser"
        self.email = "test@example.com"

test_user = TestUser()

# Create JWT token with email in sub claim
token_data = {
    "sub": test_user.email,  # Using email
    "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
}

print(f"Token data: {token_data}")
print(f"Using SECRET_KEY: {settings.SECRET_KEY}")
print(f"Using ALGORITHM: {settings.ALGORITHM}")

token = jwt.encode(token_data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
print(f"Generated token: {token}")

# Decode to verify
try:
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    print(f"Decoded token: {decoded}")
except Exception as e:
    print(f"Error decoding token: {e}") 