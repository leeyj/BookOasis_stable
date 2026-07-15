---
title: "Installation Guide"
project: "BookOasis"
category: "guide"
date: 2026-06-22
tags: [install, guide, setup]
---

# 📦 BookOasis Installation Guide

This document is a comprehensive guide to installing the BookOasis media server in a local environment or a Linux production server.

---

## 1. System Requirements

* **Operating System**: Windows 10/11, Linux (Ubuntu 20.04+ recommended), macOS
* **Python**: 3.9 or higher recommended
* **Database**: SQLite (Built-in Python library, no separate installation required)
* **Network**: External communication support (for metadata plugins) and reverse proxy support

---

## 2. Installation Steps (Quick Start)

### ① Clone Source Code & Setup Virtual Environment
Prepare the project code and isolate it by creating a Python virtual environment (venv).

**Linux / macOS:**
```bash
git clone https://github.com/your-repo/BookOasis.git
cd BookOasis
python -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/your-repo/BookOasis.git
cd BookOasis
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### ② Install Dependency Packages
Install the core dependencies specified in `requirements.txt`.
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### ③ Environment Variables Setup (Optional)

Complex settings that used to exist in the `.env` file (such as plugin activation, API keys, etc.) have been deprecated. In the latest architecture, you can safely configure and manage them directly in the DB through the Web UI's **[Settings > Plugin Settings]** tab after running the system. Therefore, you can skip creating an environment variables file and proceed directly to execution unless you have a specific reason.

However, to **prevent the web login session from being cleared (maintaining logged-in status)** when Gunicorn worker processes restart due to memory threshold detection or system reboots, you must create a `.env` file at the project root and register a fixed secret key (`SECRET_KEY`).

**.env Configuration Example:**
```env
# Fixed secret key to preserve user login sessions upon Gunicorn restarts
SECRET_KEY=yoursupersecretfixedkey12345!
```

---

## 3. Running the Web Service

### 1) Local Development & Windows One-Click Execution (Windows / macOS / Linux)

#### 🪟 Windows Environment
On Windows, we provide a batch file that automatically creates required directories (`db`, `covers`, `cache`, `logs`), installs dependencies (including `waitress`), and spins up a production-ready server without manual setup.

1. Double-click the **`run_windows.bat`** file in the project root directory.
2. Once launched successfully, the server will start serving at `http://localhost:5930`.

#### 🐧 Linux / macOS Environment
Run the built-in Werkzeug web server for debugging and local testing.
```bash
# Default run (Port 5930)
python core.py

# Run with a custom port (using -p parameter)
python core.py -p 8080
```
* Default running port: `http://localhost:5930` (Can be changed via parameter)

### 2) Production Server Deployment Mode (Linux - Gunicorn)
In Linux server environments, use Gunicorn to run the service stably, preventing lock phenomena and utilizing multi-worker processing.

```bash
# Background run example (using default 5930 port)
gunicorn --workers 4 --bind 0.0.0.0:5930 --timeout 120 api:app --daemon

# If you want to change the port to 8080, modify the bind option:
# gunicorn --workers 4 --bind 0.0.0.0:8080 --timeout 120 api:app --daemon
```

### 3) Easy Run via Docker
If Docker is installed, you can quickly boot up the environment containerized without building from source.

**① Copy configuration template**
Copy the provided override template file for your local environment configuration.
```bash
cp docker-compose.override.example.yml docker-compose.override.yml
```

**② Modify volume binding path**
Open the generated `docker-compose.override.yml` and modify the host path to point to your actual book/comic library directory.
```yaml
services:
  bookoasis:
    volumes:
      - /path/to/your/comics:/data/comics:ro
```

**③ Build and Run Service**
```bash
# Build and run the docker container in the background
docker compose up -d --build
```
* The container's internal port `5930` is bound to the host's `5930` port. If you wish to change the host port, modify the left-side port number in `docker-compose.yml` like `ports: - "8080:5930"`.
* The database (`db/`), cover cache (`covers/`), temp upload folder (`cache/`), and custom plugins (`plugins/`) are automatically mapped as persistent volumes in the project root directory.
* 💡 Thanks to the `plugins/` volume mapping, you can instantly add external metadata plugins simply by dropping a new python file into the host's `plugins/metadata/` folder without needing to rebuild the docker container.
* 💡 Since `docker-compose.override.yml` is listed in `.gitignore`, your local path configuration won't be overwritten or cause conflicts when you pull updates (`git pull`) from the remote repository.

### 3-1) GHCR-Based Updates (Operator)

For community users, GHCR image updates are recommended as the default update path.

> Policy: this project uses a `stable`-only GHCR channel. When a `v*` release tag is pushed, both the version tag image and the `stable` image are updated.

**① Prepare GHCR compose file**
Set the real repository owner in `docker-compose.ghcr.yml`.

```yaml
services:
    bookoasis:
        image: ghcr.io/<github_owner>/bookoasis:stable
```

**② First run**
```bash
docker compose -f docker-compose.ghcr.yml up -d
```

**③ Apply updates**
```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

**④ Pin to a version tag (recommended)**
When needed, pin `stable` to a specific version tag (e.g., `v1.2.3`) for safer rollback.

### 3-2) Release Auto Tagging (Operator)

When pushing through the deployment mirror, `export_stable.py` can auto-create/push a `vX.Y.Z` tag from the `dashboard` value in the `VERSION` file.

```bash
# push main + try VERSION-based auto tagging
python export_stable.py "Version update"

# explicitly set a release tag (overrides auto tagging)
python export_stable.py "Release v1.2.3" --tag v1.2.3

# disable auto tagging (push main only)
python export_stable.py "Hotfix" --no-auto-tag
```

Recommended tag formats: `v1.2.3`, `v1.2.3-rc.1`

---

## 4. Reverse Proxy & Cloudflare Setup

This is the optimized configuration for when you link the service to an external domain, placing Cloudflare (in Proxy mode) in front and using Nginx as a reverse proxy on the origin server.

> [!NOTE]
> It is optimized for Cloudflare's Free plan upload limit of **100MB**, and **Nginx buffering is disabled** to prevent bottlenecks when streaming comic book images.

### Nginx Virtual Host Setup Example (`/etc/nginx/sites-available/book`)

```nginx
server {
    listen 80;
    server_name book.yourdomain.com; # Change to your domain

    # HTTPS Redirect (When protocol is detected in Cloudflare environment)
    if ($http_x_forwarded_proto = "http") {
        return 301 https://$host$request_uri/;
    }

    # 1. Gzip Compression Setup
    gzip on;
    gzip_disable "msie6";
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # 2. Upload Size Limit & Buffer Extension
    client_max_body_size 100M;
    
    # Extend buffer size significantly to handle Cloudflare headers/cookies (Prevents 4XX errors)
    client_header_buffer_size 16k;
    large_client_header_buffers 4 64k;
    proxy_headers_hash_max_size 1024;
    proxy_headers_hash_bucket_size 128;

    # 3. Add Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # 4. Cloudflare Real IP Reflection Setup
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 131.0.72.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 162.254.85.0/24;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 173.245.48.0/25;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 2400:cb00::/32;
    set_real_ip_from 2606:4700::/32;
    set_real_ip_from 2803:f800::/32;
    set_real_ip_from 2405:b500::/32;
    set_real_ip_from 2405:8100::/32;
    set_real_ip_from 2a06:98c0::/29;
    set_real_ip_from 2c0f:f248::/32;

    real_ip_header CF-Connecting-IP;

    # 5. Reverse Proxy Link & Performance Optimization
    location / {
        proxy_pass http://127.0.0.1:5930/;

        # Basic proxy header setup (Changed from $host to $http_host to maintain port and enhance compatibility)
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;

        # Maintain WebSocket Connection (For real-time monitoring/progress updates)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Optimize large comic file transfer (Turn off intermediate buffering and stream immediately)
        proxy_buffering off;

        # Timeout handling for long-running tasks like AI analysis
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

After changing the Nginx configuration, verify it with `sudo nginx -t` and apply the settings using `sudo systemctl reload nginx`.

### Caddy Setup Example (`/etc/caddy/Caddyfile`)

If you adopt Caddy as your reverse proxy, it can be configured concisely as follows. Caddy perfectly handles automatic HTTPS certificate renewal via Let's Encrypt and WebSocket proxying out of the box.

```caddy
your-domain.com { # <== Change this to your own domain
    # Gzip and Zstd text compression settings
    encode gzip zstd

    # Maximum request body size limit (Corresponds to Cloudflare's 100MB upload limit)
    request_body {
        max_size 100mb
    }

    # Backend proxy path mapping
    reverse_proxy 127.0.0.1:5930 {
        # [CRITICAL] Disable intermediate proxy buffering completely for large comic streaming
        flush_interval -1
    }
}
```

After editing Caddyfile, reload the Caddy service by running `sudo systemctl reload caddy`.

---

## 5. Production Environment Security Best Practices

Additional security guidelines to defend against potential threats (bypass intrusions, brute-force logins) when exposing the service to external networks.

### ① Block Direct IP Access (Origin Server Protection)
Block direct traffic that scans the server's public IP rather than the domain. Add a default server block to the Nginx configuration file to drop unauthorized requests that bypassed Cloudflare.

```nginx
# Block unauthorized requests coming directly via IP without a domain
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    
    # Drop the connection immediately without even returning a response header to protect resources
    return 444; 
}
```

### ② Rate Limiting for Login Endpoint
Set a request limit on the login route to block Brute Force hacking attempts on admin accounts.

`nginx.conf` (Inside `http` block):
```nginx
# Limit to 1 request per second per IP and create a 10MB memory zone
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=1r/s;
```

Virtual Host Setup File (Inside `server` block):
```nginx
location /api/auth/login {
    # Apply the specified rate limit (Allow bursts up to 5)
    limit_req zone=login_limit burst=5 nodelay;
    
    proxy_pass http://127.0.0.1:5930;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### ③ Recommended Cloudflare WAF Settings
* **Geoblocking**: If the library is intended for a specific region, use Cloudflare Dashboard's WAF Rules to strictly apply a `Managed Challenge (CAPTCHA)` to all traffic from other countries. This can block over 95% of scanner bot traffic.
* **Super Bot Fight Mode**: It is recommended to turn on the bot mitigation option to block scan tools.
