from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List
from datetime import datetime
import os
import json

class Settings(BaseSettings):
    """Application settings"""
    
    # model_config = {
    #     "env_file": ".env",
    #     "case_sensitive": False
    # }
    
    # Database
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "autobit"
    mongodb_max_connections: int = 100
    mongodb_connection_timeout: int = 5000
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_max_connections: int = 50
    
    # NATS
    nats_url: str = "nats://localhost:4222"
    nats_cluster_id: str = "autobit-cluster"
    nats_client_id: str = "autobit-client"
    
    # JWT
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    
    # OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    
    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_max_requests: int = 1000
    
    # Docker
    docker_host: str = "unix:///var/run/docker.sock"
    docker_api_version: str = "1.41"
    docker_timeout: int = 30
    
    # Billing rates (USD per hour)
    vcpu_rate_per_core_hour: float = 0.0100
    ram_rate_per_gib_hour: float = 0.0015
    disk_rate_per_gib_hour: float = 0.00005
    
    # Usage settings
    usage_sampling_interval: int = 30  # seconds
    usage_retention_days: int = 90
    
    # Server limits
    max_servers_per_user: int = 10
    max_cpu_per_server: float = 8.0  # cores
    max_ram_per_server: int = 32  # GiB
    max_disk_per_server: int = 1000  # GiB
    
    # Security settings
    jwt_expire_minutes: int = 1440  # 24 hours
    password_min_length: int = 8
    max_login_attempts: int = 5
    account_lockout_minutes: int = 30
    
    # Monitoring settings
    health_check_interval: int = 60  # seconds
    log_level: str = "INFO"

    class Config:
        extra = "ignore"  # Ignore extra environment variables

# Global instance
settings = Settings()

# Backward compatibility
static_settings = settings
dynamic_settings = settings
