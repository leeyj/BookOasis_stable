# 📱 OPDS Mobile Viewer Integration Guide (OPDS Guide)

This document describes how to connect wirelessly to your BookOasis book library from external reader applications (apps) in mobile and tablet environments using the **BookOasis OPDS Feed** to stream or download books.

---

## 1. What is OPDS?
**OPDS (Open Publication Distribution System)** is an industry standard protocol based on Atom XML for distributing e-book and comic catalogs.
BookOasis has a built-in OPDS server feature, allowing you to **browse library series and book lists and download them instantly from various external reader apps**, in addition to the dedicated web viewer.

---

## 2. BookOasis OPDS Endpoint URLs

The BookOasis OPDS catalog addresses to register in external apps are as follows.
When attempting to connect, Basic Authentication using the **ID and password used to log in to the BookOasis web library** is strictly required.

### 🌐 General OPDS Catalog Address
> `http://<SERVER_IP_OR_DOMAIN>:5930/opds`
* **Access Permission**: Accessible with any general user account registered in BookOasis.
* **Download and page-view permission** (since 3.2.2): same as the web. Books outside the account's category permission cannot be downloaded (404); accounts without download permission, or books rated above the account's content rating, are refused (403). Comic page viewing (OPDS-PSE) checks category and rating only.
* **Provided Categories**:
  * Browse series by library
  * Recently Added books
  * Recently Read books
  * Favorites
  * Integrated search features (supports title, series, author search)

### 🔞 Adult OPDS Catalog Address
> `http://<SERVER_IP_OR_DOMAIN>:5930/opds-adult`
* **Access Permission**: Access and authentication are only permitted with accounts having **Administrator (Admin) privileges**.
* **Provided Categories**: Provides the catalog of series, books and integrated search features in the adult library database.

### 📖 Dedicated Address for Tachiyomi / Mihon
> General: `http://<SERVER_IP_OR_DOMAIN>:5930/app-opds`
> Adult: `http://<SERVER_IP_OR_DOMAIN>:5930/app-opds-adult`
* This is a dedicated endpoint for special apps like Tachiyomi or Mihon. It is optimized to be parsed smoothly by these apps following the standard OPDS format, and also provides integrated search features.

### 🔍 OPDS Search Endpoints (OpenSearch Support)
BookOasis OPDS feeds support the OpenSearch specification, enabling keyword searches (matching title, series, or author) directly from compatible external reader apps.
* **General Search URL**: `http://<SERVER_IP_OR_DOMAIN>:5930/opds/search?q={searchTerms}`
* **Adult Search URL**: `http://<SERVER_IP_OR_DOMAIN>:5930/opds-adult/search?q={searchTerms}`
* **Tachiyomi General Search URL**: `http://<SERVER_IP_OR_DOMAIN>:5930/app-opds/search?q={searchTerms}`
* **Tachiyomi Adult Search URL**: `http://<SERVER_IP_OR_DOMAIN>:5930/app-opds-adult/search?q={searchTerms}`
> Note: Most modern OPDS apps (such as Moon+ Reader, KyBook, etc.) will automatically detect the search API URL if you simply register the root catalog URL.


---

## 3. How to Connect in Popular Mobile Reader Apps

Here are the configuration methods for popular external viewer apps that support OPDS catalog features.

### 🍎 iOS (iPhone / iPad)
* **KyBook 3 / Yomu / PocketBook Reader**, etc.
  1. Open the app and go to the **"Catalog"** or **"Add OPDS Bookcase"** menu.
  2. Tap the Add New Catalog (+) button.
  3. Enter `http://<SERVER_IP>:5930/opds` in the **Catalog URL** field.
  4. When the authentication window prompt appears, enter your BookOasis login **Username** and **Password**.
  5. Once successfully added, the BookOasis libraries will appear as a list. You can tap a book to download and start reading instantly.

### 🤖 Android (Android Phone / Tablet)
* **Moon+ Reader / FBReader / Aldiko**, etc.
  1. Select **"Net Library"** from the left sidebar menu of the app.
  2. Click **"Add new catalog"**.
  3. Enter a name for the catalog (e.g., `BookOasis`) and fill in the URL field with `http://<SERVER_IP>:5930/opds`.
  4. Input your web login account credentials (username, password) and save it.
  5. Enter the registered bookcase to freely download and enjoy your books.

* **Tachiyomi / Mihon**
  1. In the **Extensions** tab, install an OPDS extension (e.g., `Kavita` or the generic `OPDS` extension).
  2. Open the settings of the added OPDS extension from the **Sources** tab.
  3. In the server address field, make sure to enter the dedicated endpoint: `http://<SERVER_IP>:5930/app-opds` (or `/app-opds-adult` for adults).
  4. Set your username and password, save, and start browsing.

---

## 4. Supported Formats and Important Notes

* **Supported Formats**: Transmits all book file formats scanned in the library, including `EPUB`, `ZIP`, `CBZ`, `PDF`, `TXT`, etc.
* **External Network Connection (Access from outside)**:
  * In a home server environment behind a router, you must configure **Port Forwarding for port 5930** on your router page, or set up a Reverse Proxy (such as Nginx) and DDNS to access the server outside via mobile data network (LTE/5G).
* **Password Security**:
  * Since external OPDS connections use Basic Auth, it is highly recommended to configure an **SSL certificate (HTTPS)** on your Nginx reverse proxy to encrypt the authentication traffic for security.

## 5. KOReader (e-readers: Kobo, Kindle, PocketBook, Android, ...)

### Reading (OPDS)
In KOReader, open **Search (magnifier) → OPDS catalog → `+`** and enter:
* **URL**: `http://<server>:5930/opds` (adult catalog: `/opds-adult`, admin accounts only)
* **Username / password**: your BookOasis account

Browse category → series → book, or search. EPUB, PDF, CBZ and TXT are downloaded and opened directly.

### Comic page streaming (OPDS-PSE)
For comics (ZIP/CBZ/image folders) you can choose **Stream** (view page by page without downloading).
* Streaming links are only added for **books whose page count is known**. In remote-drive (GDS, etc.) categories the
  page count is filled once a book has been opened in the web viewer or analyzed by the Lazy-Scanner; other books are downloaded.
* Pages viewed by streaming are also recorded as your BookOasis reading position.
* Streaming links are sent **to KOReader only**. Sending them to other apps such as Moon+ Reader made their read button disappear (2.9.4), so other apps download the book instead.

### Reading-position sync (KOReader progress sync)
1. In the BookOasis web app, open the **account icon (top right) → KOReader sync** and set a **sync password**.
   KOReader only sends the MD5 of the password, which cannot be checked against your BookOasis login password, so it is separate.
2. In KOReader, go to **Settings (gear) → Progress sync → Custom sync server**, enter the address shown in the panel
   (`http://<server>:5930/kosync`), then **Log in** with your BookOasis username and the sync password.
   Do not use "Register" (your BookOasis account is used).
3. Keep the document matching method at the **default (binary)**. BookOasis identifies books the same way when they are downloaded over OPDS.

| Format | What syncs |
| :--- | :--- |
| Comics (ZIP/CBZ/image folders), PDF | Between KOReader devices + **both ways with the BookOasis web viewer** (page number) |
| EPUB, TXT | Between KOReader devices only (the web viewer uses a different position format, so it is never overwritten) |

* Only **books downloaded over OPDS** are synced (the server cannot recognize files copied to the device some other way).
* The **original (`/opds`) and the e-paper converted copy (section 6)** of the same EPUB count as the same book. For example, you can pick up on an e-paper device's converted copy where you left off in the original on iPad KOReader (both devices must use the same account).

## 6. e-paper reader feed (`/opds-epaper/v1`, since 3.2.0)

A feed for small, low-powered e-paper devices. Downloads are **cleaned-up EPUBs (converted copies)** fitted to the device. The standard `/opds` still sends the original files.

* **Address**: `http://<server>:5930/opds-epaper/v1` (Basic auth, BookOasis account)
* **Books shown**: EPUB and TXT in general libraries only. Comics, PDF and the adult library are not listed. Lists are split into pages of 40.
* **Download permission** (since 3.2.2): same as web downloads. Accounts without download permission, or books rated above the account's content rating, cannot be downloaded (they still appear in the list).
* **What conversion does**: images are shrunk to the device screen (2-color dithered PNG or gray/color JPEG depending on the device), embedded fonts and complex CSS are cleaned up, and TXT becomes an EPUB split into chapters. Conversion happens on the first download, so a large book may take a moment. Converted copies are cached on the server.

### Choosing a device (since 3.2.1)
Conversion follows the device chosen per account, in the web app under **Settings → My settings → e-paper reader**.

| Setting | Used by |
| :--- | :--- |
| **Feed device** | The device that connects to `/opds-epaper/v1` with this account. The feed list, covers and conversion follow it. If not set, reTerminal (`v1`) is used. |
| **Web download device** | **"Download for device"** in the web book menu (right-click / long-press). Use it to get a converted copy for USB or Send to Kindle. If not set, the menu item is hidden. |

* The list includes Seeed reTerminal, Xteink X4/X3, several Kobo models and Kindle (Send to Kindle, web download only). For devices not listed (Crema, RIDIPAPER, Boox, etc.) or a Kindle running KOReader, pick an **"Other device"** entry by the screen's short side (758px).
* If you use more than one feed device, create **a separate account per device** and set each one. With a device-only account, sign in to the web app with that account to choose its feed device.
* The web download button always sends the original. TXT conversion is the same for every device.

### Characters on BookOasis firmware devices
The BookOasis firmware for reTerminal and Xteink draws text with fonts stored on the device. Characters missing from that font (rare hanja, simplified Chinese, emoji, etc.) appear as □. "Download for device" tells you how many characters will appear as □ and how many it would be with another device font.

The device developer spec (feed structure, conversion rules, upload API) is in [`device-api.md`](device-api.md) (Korean), and how to add a device is in [`epaper-devices.md`](epaper-devices.md) (Korean).
