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
* **Provided Categories**:
  * Browse series by library
  * Recently Added books
  * Recently Read books

### 🔞 Adult OPDS Catalog Address
> `http://<SERVER_IP_OR_DOMAIN>:5930/opds-adult`
* **Access Permission**: Access and authentication are only permitted with accounts having **Administrator (Admin) privileges**.
* **Provided Categories**: Provides the catalog of series and books in the adult library database.

### 📖 Dedicated Address for Tachiyomi / Mihon
> General: `http://<SERVER_IP_OR_DOMAIN>:5930/app-opds`
> Adult: `http://<SERVER_IP_OR_DOMAIN>:5930/app-opds-adult`
* This is a dedicated endpoint for special apps like Tachiyomi or Mihon. It is optimized to be parsed smoothly by these apps following the standard OPDS format.

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
