# BookOasis (북 오아시스)

<p align="center">
  <img src="https://img.shields.io/badge/No_Build_Step-000000?style=for-the-badge&logo=esbuild&logoColor=white" alt="No Build" />
  <img src="https://img.shields.io/badge/Vanilla_JS-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" alt="Vanilla JS" />
  <img src="https://img.shields.io/badge/No_Framework-FF4B4B?style=for-the-badge" alt="No Framework" />
  <img src="https://img.shields.io/badge/Native_Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Native Python" />
  <img src="https://img.shields.io/badge/Zero_Dependencies-4CAF50?style=for-the-badge" alt="Zero Dependencies" />
  <img src="https://img.shields.io/badge/License-AGPL_v3-blue.svg?style=for-the-badge" alt="AGPLv3" />
</p>

An ultra-lightweight, high-performance personal media server designed to let you binge-read books and comics in a web environment without delay, in ZIP/CBZ compressed file formats.

The server provides a light and fast runtime environment by minimizing third-party dependencies and leveraging Python's standard libraries.

---

## Key Features

* **File-Safe Real-Time Streaming**
  * It does not pre-extract large compressed files (ZIP/CBZ) into the server directory.
  * It uses the built-in `zipfile` module to read the physical byte start offset only for the required pages and stream the data, innovatively blocking disk I/O and CPU consumption.

* **Minimal Dependencies**
  * It excludes heavy ORMs and third-party modules beyond Flask.
  * It realizes a ultra-lightweight architecture with performance degradation-free by embedding high-performance connection pooling and precise queries into the built-in SQLite module.

* **Optimized Frontend Pipeline**
  * It supports Lazy Loading and Preloading for the next page, loading only the cards within the viewport, to ensure a seamless reading experience.

* **Flexible Metadata Plugins**
  * It supports the plugin architecture to control external information channels like the Aladin Open API, specialized for the domestic environment.
  * It allows integrating book descriptions, author information, and high-quality covers with a single click, and supports manual metadata editing and cover replacement.

* **Mobile Viewer Compatibility**
  * It supports the OPDS standard for integration with external viewer applications.
  * It applies Basic Authentication security processing based on database authentication information.

### 🎨 Behind the Scenes: BookOasis Scan Engines

Here is the secret of how BookOasis handles massive libraries (100k+ books) instantly without UI freezing!

![BookOasis Scanner Architecture](./docs/images/engine_webcomic_en.png)

* **High-Speed Scanner**: Without extracting files, it quickly reads minimal zip header offsets to extract book metadata and seed the database.
* **Lazy Engine**: Large and complex comic ZIP files are deferred and processed asynchronously in the background, preventing main interface freezes.

---

### Dashboard Screen

![BookOasis Dashboard](./docs/screenshot.png)

---

## Getting Started

For detailed environment configuration and installation methods, please refer to the technical documentation.

* Installation Guide: [Setup Guide (docs/guide_installation_en.md)](./docs/guide_installation_en.md)
* Admin and Settings: [Admin Guide (docs/guide_admin_en.md)](./docs/guide_admin_en.md)
* Mobile Viewer Integration: [OPDS Integration Guide (docs/guide_opds_en.md)](./docs/guide_opds_en.md)
* Architecture and Source Structure: [Architecture Guide (docs/guide_architecture_en.md)](./docs/guide_architecture_en.md)
* Plugin Development: [Plugin Guide (docs/guide_plugins_en.md)](./docs/guide_plugins_en.md)
* Wiki Portal: [Wiki Home (docs/index.md)](./docs/index.md)

### Easy Operation (Docker)

1. **Copy configuration template**
   Copy the provided override template file for your local environment configuration.
   ```bash
   cp docker-compose.override.example.yml docker-compose.override.yml
   ```

2. **Modify volume path**
   Open the generated `docker-compose.override.yml` and modify the host path to point to your actual book/comic library directory.
   ```yaml
   services:
     bookoasis:
       volumes:
         - /path/to/your/comics:/data/comics:ro
   ```

3. **Run container**
   ```bash
   docker compose up -d --build
   ```
> **Tip:** Since `docker-compose.override.yml` is listed in `.gitignore`, your local path configuration won't be overwritten or cause conflicts when you pull updates from the remote repository.

> Per security policy, operator-only deployment/update procedures are maintained in private internal documentation.

### Direct Operation (Native Python)

#### 🐧 Linux / macOS
```bash
# Activate the virtual environment and install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure the settings file

# Set your own random long string to SECRET_KEY in the .env file to lock down session encryption.
# Locking this key ensures users remain logged in even if the server application process restarts.

# Start the server
python core.py
```

#### 🪟 Windows
For Windows environments, we provide a batch file that automatically handles directory creation, packages installation, and runs a production-ready web server (`waitress`) with a single click.

1. Copy `.env.example` to `.env` and fill in your settings. (SECURITY_KEY)
2. Double-click the **`run_windows.bat`** file in the project root directory.

* Local Port: `http://localhost:5930`

---

## 🔑 Initial Login Credentials
- When logging in for the first time after server startup, use the following default administrator account:
  - **Username (ID)**: `admin`
  - **Password**: `admin`
- **Security Recommendation**: Please change the default admin password immediately after logging in by navigating to [Settings] > [Account Management].

---


## 🛡️ Proxy Header Auth (SSO) Guide

For overseas home-lab users and OIDC integration, we support **Proxy Header Auth (Reverse Proxy Auto Login)**.
By trusting the HTTP headers (`Remote-User` or `X-Forwarded-User`) delivered after verification by an upstream reverse proxy authentication server (such as Authelia, Authentik, etc.), users can automatically log into BookOasis (SSO).

> [!CAUTION]
> **Critical Security Warning**
> This feature MUST ONLY be enabled in a **closed network environment where a reverse proxy (like Nginx, Authelia) protects and sets the headers**!
> If you enable this option while exposed directly to the public internet without a proxy, malicious users can spoof the headers (e.g., `Remote-User: admin`) to hijack administrator privileges. This is a critical vulnerability. Only use this if you fully understand the risks.

**Configuration Method:**
1. Log in with an admin account and navigate to the **General Settings** menu.
2. Scroll down to find and toggle the **Proxy Header Auth (Reverse Proxy Auto Login)** option.
3. Save the settings, and configure your upstream Nginx/Proxy server to pass the correct username header to BookOasis.

---

## Nginx Configuration Guide

1. Update global settings (nginx.conf)
Requests passing through Cloudflare have significantly larger header sizes (cookies, authentication tokens, proxy headers, etc.) compared to normal requests. If Nginx's default header buffer size is too small, the server will reject requests and output 400 Bad Request or 414 Request-URI Too Large errors.

To prevent this, please add or expand the following settings within the `http { ... }` block of `/etc/nginx/nginx.conf`.

```nginx
http {
    # ------------------------------------------------------------------
    # [Cloudflare and Large Headers Support] Expand buffer size significantly
    # Prevents 4XX errors when cookies and authentication headers are too long.
    # ------------------------------------------------------------------
    client_header_buffer_size 16k;
    large_client_header_buffers 4 64k;

    # ------------------------------------------------------------------
    # Proxy Header Hash Optimization
    # Prevents hash table overflow even when multiple complex X-Forwarded-* headers are sent.
    # ------------------------------------------------------------------
    proxy_headers_hash_max_size 1024;
    proxy_headers_hash_bucket_size 128;

    # (existing settings...)
}
```

2. BookOasis Virtual Host Configuration (sites-available)
Write the following content into `/etc/nginx/sites-available/default` (or the virtual host configuration block) and create a symbolic link to `sites-enabled` to apply it.

```nginx
server {
    listen 80;
    server_name your-domain.com; # <== Change this to your own domain

    # Force redirect incoming HTTP requests to HTTPS (Security)
    if ($http_x_forwarded_proto = "http") {
        return 301 https://$host$request_uri;
    }

    # ------------------------------------------------------------------
    # Gzip Text Compression (Speed up UI and JSON API)
    # Do not compress images, compress only text resources to save CPU resources.
    # ------------------------------------------------------------------
    gzip on;
    gzip_disable "msie6";
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Maximum body size limit considering Aladin metadata plugin cover image uploads
    client_max_body_size 100M;

    # ------------------------------------------------------------------
    # Security Header Injection
    # ------------------------------------------------------------------
    add_header X-Frame-Options "SAMEORIGIN" always;         # Prevent clickjacking
    add_header X-Content-Type-Options "nosniff" always;     # Prevent MIME sniffing
    add_header Referrer-Policy "no-referrer-when-downgrade" always;

    # ------------------------------------------------------------------
    # Main Application Proxy Routing
    # ------------------------------------------------------------------
    location / {
        proxy_pass http://127.0.0.1:5930/; # BookOasis internal runtime port

        # [Basic Proxy Header Settings]
        # Uses $http_host instead of $host to perfectly maintain external port and Cloudflare compatibility.
        proxy_set_header Host $http_host; 
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;

        # [WebSocket and HTTP/1.1 Protocol Upgrade Support]
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # --------------------------------------------------------------
        # [CRITICAL] Large File Transfer Optimization (Disable Proxy Buffering)
        # Ensures BookOasis's core feature of 'offset-based real-time streaming' bypasses Nginx's
        # temporary buffers and delivers 'point-to-point direct delay' to the browser viewer immediately.
        # This is the core setting to defend against disk I/O and memory waste.
        # --------------------------------------------------------------
        proxy_buffering off;

        # [Timeout Extension] Response to long-running operations for large scans and external AI analysis
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

---

## Caddy Configuration Guide

If you use Caddy as your reverse proxy instead of Nginx, you can configure your Caddyfile as follows to optimize and connect. Caddy automatically issues and manages SSL certificates (HTTPS) and natively supports WebSockets and reverse proxy header passing.

Map your domain in the `/etc/caddy/Caddyfile` and configure it like this:

```caddy
your-domain.com { # <== Change this to your own domain
    # ------------------------------------------------------------------
    # Gzip and Zstd Text Compression Settings (Speed up UI and JSON API)
    # ------------------------------------------------------------------
    encode gzip zstd

    # ------------------------------------------------------------------
    # Maximum Request Body Size Limit (Corresponds to Nginx's client_max_body_size 100M)
    # Limits file uploads, considering cover image uploads from the Aladin metadata plugin, etc.
    # ------------------------------------------------------------------
    request_body {
        max_size 100mb
    }

    # ------------------------------------------------------------------
    # Main Application Proxy Routing
    # ------------------------------------------------------------------
    reverse_proxy 127.0.0.1:5930 {
        # [CRITICAL] Large File Transfer Optimization (Disable Proxy Buffering)
        # Configures the server to send data immediately without buffering, preventing
        # BookOasis's core 'offset-based real-time streaming' from being delayed.
        flush_interval -1
    }
}
```

After updating Caddyfile, reload the settings by running `sudo systemctl reload caddy`.

## License and Trademark Info

* **Open Source License**: This project is licensed under the [GNU AGPLv3 (Affero General Public License v3.0)](./LICENSE). Anyone is free to view, modify, and distribute the source code. If you provide a service (including over a network) based on this software, you must publicly disclose the modified source code under the same AGPLv3 license. For detailed terms, please refer to the LICENSE file.
* **Trademark Guidelines**: The name "BookOasis" and its official logos are protected trademarks of the original author. If you fork and redistribute this software, you must respect the copyrights, but you may not use the same name ("BookOasis") or official logo for your derivative works. You must rename it to avoid brand confusion.

Copyright &copy; 2026 leeyj (Carls, leeyj78@gmail.com). All rights reserved.