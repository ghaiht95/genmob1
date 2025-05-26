import os
import requests
from dotenv import load_dotenv

class APIClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Load environment variables
        load_dotenv()
        
        # Initialize base URL from environment variable
        self._base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        self._access_token = None
        self._initialized = True
    
    def set_base_url(self, base_url):
        """Set the base URL for API requests"""
        self._base_url = base_url.rstrip('/')
    
    def set_token(self, token):
        """Set the access token for authenticated requests"""
        self._access_token = token
    
    def _get_headers(self, is_form=False):
        """Get headers for API requests"""
        headers = {
            'Accept': 'application/json'
        }
        if not is_form:
            headers['Content-Type'] = 'application/json'
        if self._access_token:
            headers['Authorization'] = f'Bearer {self._access_token}'
        return headers
    
    def get(self, endpoint, params=None):
        """Make a GET request to the API"""
        url = f"{self._base_url}{endpoint}"
        response = requests.get(url, headers=self._get_headers(), params=params)
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint, json=None, data=None):
        """Make a POST request to the API"""
        url = f"{self._base_url}{endpoint}"
        is_form = data is not None
        response = requests.post(
            url, 
            headers=self._get_headers(is_form=is_form),
            json=json if not is_form else None,
            data=data
        )
        response.raise_for_status()
        return response.json()
    
    def put(self, endpoint, json=None):
        """Make a PUT request to the API"""
        url = f"{self._base_url}{endpoint}"
        response = requests.put(url, headers=self._get_headers(), json=json)
        response.raise_for_status()
        return response.json()
    
    def delete(self, endpoint):
        """Make a DELETE request to the API"""
        url = f"{self._base_url}{endpoint}"
        response = requests.delete(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def patch(self, endpoint, json=None):
        """Make a PATCH request to the API"""
        url = f"{self._base_url}{endpoint}"
        response = requests.patch(url, headers=self._get_headers(), json=json)
        response.raise_for_status()
        return response.json()

# Create singleton instance
api_client = APIClient() 