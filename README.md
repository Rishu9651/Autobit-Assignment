# AutoBit Backend System

A production-ready backend system for server management and billing, 
built with Python FastAPI, MongoDB, Redis, NATS, and Docker.

## What This System Does


- **User Management**: Sign up, login with email or OAuth (Google/GitHub)
- **Server Management**: Create, start, stop Docker containers with CPU/RAM limits
- **Real-time Monitoring**: Track CPU, RAM, and disk usage every 30 seconds
- **Smart Billing**: Calculate costs based on actual resource usage
- **Email Reports**: Weekly summaries of usage and costs
- **Event System**: NATS messaging for real-time updates

## Tech Stack

- **Backend**: Python + FastAPI (modern, fast, auto-documented APIs)
- **Database**: MongoDB (flexible, scalable)
- **Cache**: Redis (fast data storage)
- **Messaging**: NATS (lightweight, reliable messaging)
- **Containers**: Docker (container management)
- **Auth**: JWT + OAuth (secure authentication)

## Quick Start Guide

### Step 1: Get the Code
```bash
git clone <your-repository-url>
cd Autobit-Internal
```

### Step 2: Set Up Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your settings (see Environment Variables section below)
nano .env
```

### Step 3: Start Everything with Docker
```bash
# This starts MongoDB, Redis, NATS, and the API all at once
docker-compose up -d

# Check if everything is running
docker-compose ps
```

### Step 4: Verify It's Working
```bash

# Open the interactive API docs
open http://localhost:8000/docs
```

**That's it!** Your system is now running at `http://localhost:8000`



## NATS Connection Guide

NATS is the messaging system that handles real-time events. Here's how it works:

### What NATS Does
- **Server Events**: When a server is created, started, or stopped
- **Usage Events**: Every 30 seconds, usage data is published
- **Billing Events**: When invoices are generated
- **Email Events**: When weekly emails are triggered

### NATS Subjects (Event Types)
```
server.created     # New server created
server.started     # Server started
server.stopped     # Server stopped
usage.sampled      # Usage data collected
invoice.generated  # New invoice created
```

### Connecting to NATS


### NATS CLI Connection
```bash
# Connect to NATS using the official NATS CLI tool
docker run --rm -it --network host natsio/nats-box

# Once inside the container, you can use NATS CLI commands:
nats sub ">" --server nats://localhost:4222

nats server info
nats sub "server.*"
nats pub "server.created" '{"server_id": "test123"}'
```

### NATS Web UI (Optional)


## Running Tests

The system includes comprehensive tests that don't require external services:

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_billing.py -v      # Billing calculations
pytest tests/test_auth.py -v         # Authentication
pytest tests/test_simple_api.py -v   # API endpoints


```





### Health Checks
```bash
# API health
curl http://localhost:8000/billing/rates

```

## Project Structure

```
Autobit-Internal/
├── app/                          # Main application code
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Configuration management
│   ├── models.py                # Data models (Pydantic)
│   ├── database.py              # MongoDB connection
│   ├── auth.py                  # Authentication logic
│   ├── docker_manager.py        # Docker container management
│   ├── nats_client.py           # NATS messaging
│   ├── routers/                 # API route handlers
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── servers.py          # Server management
│   │   ├── usage.py            # Usage monitoring
│   │   ├── billing.py          # Billing system
│   │   └── emails.py           # Email notifications
│   └── workers/                 # Background workers
│       ├── usage_sampler.py    # Usage data collection
│       └── email_worker.py     # Email processing
├── tests/                       # Test suite
│   ├── test_auth.py            # Authentication tests
│   ├── test_billing.py         # Billing calculation tests
│   └── test_simple_api.py      # API endpoint tests
├── docker-compose.yml          # Multi-service setup
├── Dockerfile                  # API container
├── requirements.txt            # Python dependencies
├── postman_collection.json     # API testing collection
└── README.md                   # This file
```

## Monitoring & Logs

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f mongodb
docker-compose logs -f redis
docker-compose logs -f nats
```

### API Monitoring
- **Interactive Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **Health Check**: http://localhost:8000/billing/rates

## Postman Collection

Import `postman_collection.json` for comprehensive API testing:

1. **Authentication Flow**: Signup → Login → Get User Info
2. **Server Management**: Create → Start → Monitor → Update → Stop → Delete
3. **Usage Monitoring**: View usage data with different intervals
4. **Billing**: Generate invoices and record payments
5. **Email**: Trigger weekly emails

The collection includes automatic JWT token handling and example requests.



### OAuth Setup
1. **Google OAuth**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create OAuth 2.0 credentials
   - Add `http://localhost:8000/auth/oauth/google/callback` as redirect URI

2. **GitHub OAuth**:
   - Go to GitHub Settings → Developer settings → OAuth Apps
   - Create new OAuth App
   - Add `http://localhost:8000/auth/oauth/github/callback` as callback URL



