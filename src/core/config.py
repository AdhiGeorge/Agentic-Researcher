import yaml
import os
from pathlib import Path
from dotenv import load_dotenv

class Config:
    def __init__(self, config_path: str = "config.yaml", env_path: str = ".env"):
        self.config_path = config_path
        self.env_path = env_path
        load_dotenv(self.env_path)
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from config.yaml file"""
        if not os.path.exists(self.config_path):
            self._create_default_config()
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _create_default_config(self):
        """Create a default configuration file (no private keys)"""
        default_config = {
            "azure_openai": {
                "endpoint": "https://your-resource.openai.azure.com/",
                "api_version": "2024-02-15-preview",
                "deployment_name": "gpt-4o",
                "embedding_deployment": "text-embedding-3-small",
                "api_version_embeddings": "2023-05-15"
            },
            "qdrant": {
                "host": "localhost",
                "port": 6333,
                "collection_name": "research_knowledge",
                "binary_path": "./qdrant/qdrant.exe"
            },
            "database": {
                "path": "data/research.db"
            },
            "web_search": {
                "max_results": 5,
                "timeout": 30
            }
        }
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f)
    
    def get(self, key: str, default=None):
        """Get a configuration value using dot notation, loading secrets from .env if needed"""
        # For private keys, always load from environment
        env_map = {
            'azure_openai.api_key': 'AZURE_OPENAI_API_KEY',
            'azure_openai.endpoint': 'AZURE_OPENAI_ENDPOINT',
            'azure_openai.deployment_name': 'AZURE_OPENAI_DEPLOYMENT',
            'azure_openai.embedding_deployment': 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT',
            'azure_openai.api_version': 'AZURE_API_VERSION_CHAT',
            'azure_openai.api_version_embeddings': 'AZURE_API_VERSION_EMBEDDINGS',
            'qdrant.binary_path': 'QDRANT_BINARY_PATH',
        }
        if key in env_map:
            return os.getenv(env_map[key], default)
        # Otherwise, load from config.yaml
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    @property
    def azure_openai(self):
        return {
            'api_key': os.getenv('AZURE_OPENAI_API_KEY'),
            'endpoint': os.getenv('AZURE_OPENAI_ENDPOINT', self.config['azure_openai'].get('endpoint')),
            'api_version': os.getenv('AZURE_API_VERSION_CHAT', self.config['azure_openai'].get('api_version')),
            'deployment_name': os.getenv('AZURE_OPENAI_DEPLOYMENT', self.config['azure_openai'].get('deployment_name')),
            'embedding_deployment': os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', self.config['azure_openai'].get('embedding_deployment')),
            'api_version_embeddings': os.getenv('AZURE_API_VERSION_EMBEDDINGS', self.config['azure_openai'].get('api_version_embeddings')),
        }
    
    @property
    def qdrant(self):
        q = self.config.get('qdrant', {})
        q['binary_path'] = os.getenv('QDRANT_BINARY_PATH', q.get('binary_path'))
        return q
    
    @property
    def database(self):
        return self.config.get('database', {}) 