[한국어](guide_install_oracle.md)

# Installing on an Oracle Cloud free server (Ubuntu, ARM/AMD)

Install BookOasis on an Oracle Cloud "Always Free" server. Written for people touching a server for the first time. (About 30 minutes)

> **What was verified** (2026-11-03): from running the installer (`get.sh`) to opening the site, how Oracle's default Ubuntu firewall rules interact with Docker, and running the arm64 image — all reproduced on Ubuntu.
> The Oracle console screens (creating an instance, security lists) were not checked directly. If your screens differ, please tell the community.

---

## 0. Tips for creating the server (instance)

- Image: **Ubuntu** (22.04 or 24.04)
- Shape
  - **ARM (Ampere A1)**: the largest free allowance (up to 4 cores / 24 GB), but popular regions can say "Out of capacity" for months.
    - Requesting **1 OCPU / 6 GB** tends to succeed; you can grow it later.
    - Upgrading the account to **Pay As You Go** keeps free-tier usage free and, by many reports, makes creation much easier. You could create paid resources by mistake, so **set a budget alert**.
  - **AMD (E2.1.Micro)**: easy to get, but 1 GB of memory is tight for running BookOasis long term. Fine for practicing the install.
- Get a public IP and download the SSH key.

The official BookOasis image ships **both ARM (arm64) and AMD (amd64)**. The same command pulls the right one for your server.
(The arm64 image was started and checked healthy. Hardware video transcoding (VAAPI) is amd64-only.)

---

## 1. Open the port — Oracle console "security list"

Oracle has one more firewall outside your server. If it is not opened here, nothing will connect.

**Networking → Virtual cloud networks → (your VCN) → Subnet → Security list → Add ingress rule**

| Field | Value |
|---|---|
| Source CIDR | `0.0.0.0/0` (anywhere) — please read "Security" below |
| IP protocol | TCP |
| Destination port range | `5930` |

---

## 2. Connect to the server and install Docker

From your PC (PowerShell on Windows):

```bash
ssh -i your-key.key ubuntu@SERVER_PUBLIC_IP
```

On the server:

```bash
sudo apt update && sudo apt install -y git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
```

Log out with `exit` and **connect again** so `docker` works without `sudo`. Check:

```bash
docker compose version
```

Success: `Docker Compose version v2…`.

> **Do not touch** the firewall inside the server (iptables). See section 5.

---

## 3. Install BookOasis (setup wizard)

Create a folder for books first. (If you will use Google Drive, do [Connecting Google Drive](guide_rclone_gdrive_en.md) first and use that mount folder instead.)

```bash
mkdir -p ~/books
curl -fsSL https://raw.githubusercontent.com/leeyj/BookOasis_stable/main/get.sh | bash
```

Answer the questions like this (the wizard is in Korean):

| Question | Answer |
|---|---|
| Install mode (설치 방식) | `1` (Docker) |
| Image mode (이미지 방식) | `1` (GHCR, download without building) |
| Install path (설치 경로) | Enter (`~/bookoasis`) |
| Book/comic folder (도서/만화책 디렉토리) | `/home/ubuntu/books` (the folder created above) |
| SECRET_KEY / WEBHOOK_TOKEN | Enter, Enter (auto-generated) |
| Proceed? (진행) | `Y` |

Success: `🎉 BookOasis 설치가 완료되었습니다!` (installation complete). Check on the server:

```bash
curl -s http://localhost:5930/health
```

`{"service":"BookOasis","status":"healthy"}`

---

## 4. Open it and create the first category

In a browser: `http://SERVER_PUBLIC_IP:5930`

- First account `admin` / `admin` → **the password change screen comes first** (nothing else works until you change it)
- **Add category** → path **`/data/comics`** → save

> ⚠️ The path is **`/data/comics`, not** the server folder (`/home/ubuntu/books`). The wizard links your book folder into BookOasis under the name `/data/comics`.
> Entering the server path gives "the following paths do not exist on the server or have a typo". (Reproduced.)

---

## 5. About the firewall (important)

Many Oracle guides online say "open the port in iptables and run `netfilter-persistent save`". **If you installed with Docker, don't.**

Results from reproducing Oracle's default Ubuntu firewall rules:

| Case | Result |
|---|---|
| Docker install, default rules untouched | **reachable** — Docker inserts its own rules ahead of the default reject rule |
| Default rules file reloaded (`netfilter-persistent reload`, etc.) | **unreachable** — Docker's rules are wiped |
| Native install (no Docker), default rules | not reachable |
| Native + port added to iptables | reachable |

- **Docker install**: only open the Oracle console security list (section 1). Leave iptables on the server alone.
  If you reloaded the rules by mistake and lost access: `sudo systemctl restart docker`
- **Native install** only:
  ```bash
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5930 -j ACCEPT
  sudo netfilter-persistent save
  ```

---

## 6. Security (a must on a public-IP server)

An Oracle server is directly exposed to the internet.

1. **admin password** — double-check you changed it in section 4. Weak passwords get guessed quickly.
2. **HTTPS** — over `http://` your password travels unencrypted. With a domain, Caddy adds HTTPS easily → [installation guide §4 Caddy example](guide_installation_en.md)
3. **Safer: Tailscale** — a private network between your own devices. Install Tailscale on the server and your phone/PC and open `http://SERVER_TAILSCALE_ADDRESS:5930`; then you do not even need to open 5930 in the security list.

---

## 7. Updating

```bash
cd ~/bookoasis
docker compose pull && docker compose up -d
```

---

## Common problems

| Symptom | Cause → fix |
|---|---|
| Browser cannot connect (timeout) | no ingress rule for 5930 in the Oracle security list (section 1) |
| Worked, then suddenly unreachable | iptables rules were reloaded → `sudo systemctl restart docker` |
| `permission denied … docker.sock` | did not reconnect after `usermod` → `exit` and reconnect |
| "does not exist … typo" when adding a category | entered the server path → `/data/comics` |
| Wizard says it cannot find a TTY | ran `curl … | bash` inside a script/cron → run it directly in an SSH terminal |
| Server disk too small | free disks are small → keep books on [Google Drive](guide_rclone_gdrive_en.md) |

---

Related: [Connecting Google Drive (rclone)](guide_rclone_gdrive_en.md) · [Synology NAS install](guide_install_synology_en.md) · [Installation guide](guide_installation_en.md)
