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

### Dashboard Screen

![BookOasis Dashboard](./docs/screenshot.png)

---

## Getting Started

For detailed environment configuration and installation methods, please refer to the technical documentation.

* Installation Guide: [Setup Guide (docs/guide_installation_en.md)](./docs/guide_installation_en.md)
* Admin and Settings: [Admin Guide (docs/guide_admin_en.md)](./docs/guide_admin_en.md)
* Wiki Portal: [Wiki Home (docs/index.md)](./docs/index.md)

### Easy Operation (Docker)

```bash
# Run after modifying the volume path in docker-compose.yml
docker compose up -d --build
```

### Direct Operation (Native Python)

```bash
# Activate the virtual environment and install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure the settings file
cp .env.example .env
# Enter essential settings such as Aladin TTBKey in the .env file

# Start the server
python api.py
```
* Local Port: `http://localhost:5930`

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

## License

This project is licensed under the [MIT License](./LICENSE).
Free use, modification, and distribution are allowed for commercial purposes. For detailed terms, please refer to the LICENSE file.