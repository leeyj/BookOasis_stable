export async function buildMergedContent(book, options = {}) {
  const coverFallbackUrl = options && options.coverFallbackUrl ? String(options.coverFallbackUrl) : '';
  const normalizePath = path => String(path || '')
    .replace(/\\/g, '/')
    .replace(/^\.\//, '')
    .replace(/^[\s\u0000]+|[\s\u0000]+$/g, '');

  const normalizeRelativeSegments = path => {
    const input = normalizePath(path);
    if (!input) return '';
    const parts = input.split('/');
    const stack = [];
    for (const part of parts) {
      if (!part || part === '.') continue;
      if (part === '..') {
        if (stack.length > 0) stack.pop();
        continue;
      }
      stack.push(part);
    }
    return stack.join('/');
  };

  const stripQueryHash = value => String(value || '').split('#')[0].split('?')[0];

  const guessMimeType = path => {
    const lower = String(path || '').toLowerCase();
    if (lower.endsWith('.png')) return 'image/png';
    if (lower.endsWith('.gif')) return 'image/gif';
    if (lower.endsWith('.webp')) return 'image/webp';
    if (lower.endsWith('.svg')) return 'image/svg+xml';
    if (lower.endsWith('.bmp')) return 'image/bmp';
    if (lower.endsWith('.avif')) return 'image/avif';
    return 'image/jpeg';
  };

  const bytesFromBinaryString = str => {
    const bytes = new Uint8Array(str.length);
    for (let i = 0; i < str.length; i++) {
      bytes[i] = str.charCodeAt(i) & 0xff;
    }
    return bytes;
  };

  const sniffMimeFromBytes = bytes => {
    if (!bytes || bytes.length === 0) return '';
    const isJpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
    const isPng = bytes.length >= 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
    const isGif = bytes.length >= 6 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46;
    const isWebp = bytes.length >= 12
      && bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46
      && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50;
    const isBmp = bytes.length >= 2 && bytes[0] === 0x42 && bytes[1] === 0x4d;
    const isAvif = bytes.length >= 12
      && bytes[4] === 0x66 && bytes[5] === 0x74 && bytes[6] === 0x79 && bytes[7] === 0x70
      && bytes[8] === 0x61 && bytes[9] === 0x76 && bytes[10] === 0x69 && bytes[11] === 0x66;
    const isHeic = bytes.length >= 12
      && bytes[4] === 0x66 && bytes[5] === 0x74 && bytes[6] === 0x79 && bytes[7] === 0x70
      && bytes[8] === 0x68 && bytes[9] === 0x65 && bytes[10] === 0x69;

    if (isJpeg) return 'image/jpeg';
    if (isPng) return 'image/png';
    if (isGif) return 'image/gif';
    if (isWebp) return 'image/webp';
    if (isBmp) return 'image/bmp';
    if (isAvif) return 'image/avif';
    if (isHeic) return 'image/heic';

    try {
      const head = new TextDecoder('utf-8', { fatal: false }).decode(bytes.slice(0, 512)).toLowerCase();
      if (head.includes('<svg')) return 'image/svg+xml';
    } catch (_) {
      // ignore
    }

    return '';
  };

  const tryDecodeBase64Bytes = str => {
    const compact = String(str || '').trim();
    if (!compact || compact.length < 32) return null;
    if (!/^[a-z0-9+/=\r\n]+$/i.test(compact)) return null;
    try {
      const decoded = atob(compact.replace(/[\r\n\s]+/g, ''));
      return bytesFromBinaryString(decoded);
    } catch (_) {
      return null;
    }
  };

  const toImageBlob = (data, pathCandidate, loadMode = 'default') => {
    if (!data) return null;

    if (data instanceof Blob) {
      return data;
    }

    if (data instanceof ArrayBuffer) {
      const bytes = new Uint8Array(data);
      const sniffed = sniffMimeFromBytes(bytes);
      return new Blob([data], { type: sniffed || guessMimeType(pathCandidate) });
    }

    if (ArrayBuffer.isView(data)) {
      const view = data;
      const sliced = view.buffer.slice(view.byteOffset, view.byteOffset + view.byteLength);
      const bytes = new Uint8Array(sliced);
      const sniffed = sniffMimeFromBytes(bytes);
      return new Blob([sliced], { type: sniffed || guessMimeType(pathCandidate) });
    }

    if (typeof data === 'string') {
      // EPUB libs can return a binary string depending on request mode.
      if (loadMode === 'binary') {
        const rawBytes = bytesFromBinaryString(data);
        const decodedBase64 = tryDecodeBase64Bytes(data);
        const rawMime = sniffMimeFromBytes(rawBytes);
        const b64Mime = decodedBase64 ? sniffMimeFromBytes(decodedBase64) : '';

        if (b64Mime) {
          return new Blob([decodedBase64], { type: b64Mime });
        }

        return new Blob([rawBytes], { type: rawMime || guessMimeType(pathCandidate) });
      }

      // data URL path (rare): decode base64 payload.
      const dataUrlMatch = data.match(/^data:([^;,]+)?(;base64)?,(.*)$/i);
      if (dataUrlMatch) {
        const mime = (dataUrlMatch[1] || guessMimeType(pathCandidate)).toLowerCase();
        const isBase64 = !!dataUrlMatch[2];
        const payload = dataUrlMatch[3] || '';
        if (isBase64) {
          const decoded = atob(payload);
          return new Blob([bytesFromBinaryString(decoded)], { type: mime });
        }
        return new Blob([decodeURIComponent(payload)], { type: mime });
      }

      // Plain text is not trusted for image resources.
      return null;
    }

    return null;
  };

  const createArchiveUrl = async pathCandidate => {
    if (!pathCandidate) return null;

    // Prefer stable object URL created from raw bytes.
    if (typeof book.load === 'function') {
      const loadModes = ['arraybuffer', 'blob', 'binary', undefined];
      for (const mode of loadModes) {
        try {
          const data = mode ? await book.load(pathCandidate, mode) : await book.load(pathCandidate);
          const blob = toImageBlob(data, pathCandidate, mode || 'default');
          if (blob) {
            return URL.createObjectURL(blob);
          }
        } catch (_) {
          // try next mode
        }
      }
    }

    if (book.archive && typeof book.archive.createUrl === 'function') {
      try {
        let url = book.archive.createUrl(pathCandidate);
        if (url && typeof url.then === 'function') {
          url = await url;
        }
        if (typeof url === 'string' && url) return url;
      } catch (_) {
        // ignore
      }
    }

    return null;
  };

  const isLikelyImageBlobUrl = async (url, fallbackPath = '') => {
    if (!url) return false;
    try {
      const res = await fetch(url);
      if (!res.ok) return false;
      const blob = await res.blob();
      const mime = String(blob.type || '').toLowerCase();
      if (mime.startsWith('image/')) return true;

      // Some EPUB resources miss mime; sniff binary signatures.
      const ab = await blob.arrayBuffer();
      const bytes = new Uint8Array(ab);
      const isJpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
      const isPng = bytes.length >= 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
      const isGif = bytes.length >= 6 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46;
      const isWebp = bytes.length >= 12
        && bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46
        && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50;
      const isBmp = bytes.length >= 2 && bytes[0] === 0x42 && bytes[1] === 0x4d;
      const isSvgText = (() => {
        try {
          const head = new TextDecoder('utf-8', { fatal: false }).decode(bytes.slice(0, 256)).toLowerCase();
          return head.includes('<svg');
        } catch (_) {
          return false;
        }
      })();

      if (isJpeg || isPng || isGif || isWebp || isBmp || isSvgText) return true;

      return false;
    } catch (_) {
      return false;
    }
  };

  const canRenderImageUrl = async (url, timeoutMs = 4000) => {
    if (!url) return false;
    return await new Promise(resolve => {
      let settled = false;
      const img = new Image();
      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        resolve(false);
      }, timeoutMs);

      img.onload = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(true);
      };

      img.onerror = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve(false);
      };

      img.src = url;
    });
  };

  const getManifestHrefs = () => {
    try {
      const manifest = book && book.packaging && book.packaging.manifest;
      if (!manifest) return [];
      const entries = Object.values(manifest);
      const hrefs = entries
        .map(entry => entry && entry.href)
        .filter(Boolean)
        .map(href => normalizeRelativeSegments(stripQueryHash(href)));
      return Array.from(new Set(hrefs));
    } catch (_) {
      return [];
    }
  };

  const manifestHrefs = getManifestHrefs();

  const isCoverLikePath = value => {
    const v = String(value || '').toLowerCase();
    if (!v) return false;
    return /(^|[\/_-])cover([\/_\-.]|$)/i.test(v) || v.includes('cover.jpg') || v.includes('cover.jpeg') || v.includes('cover.png');
  };

  const resolveImageUrl = async (rawSrc, chapterHref) => {
    if (!rawSrc) return null;

    const src = stripQueryHash(String(rawSrc).trim());
    if (!src || /^(data:|https?:|blob:|\/\/)/i.test(src)) return null;

    const srcNoLeading = src.replace(/^\/+/, '');
    const srcBaseName = srcNoLeading.includes('/') ? srcNoLeading.split('/').pop() : srcNoLeading;

    const chapterPath = normalizeRelativeSegments(chapterHref || '');
    const chapterDir = chapterPath.includes('/') ? chapterPath.slice(0, chapterPath.lastIndexOf('/') + 1) : '';

    const candidates = [];
    const pushCandidate = value => {
      const normalized = normalizeRelativeSegments(value);
      if (!normalized) return;
      if (!candidates.includes(normalized)) candidates.push(normalized);
    };

    // 1) 원본 그대로
    pushCandidate(src);

    // 2) EPUB 내부 루트 절대경로('/images/...')를 아카이브 상대경로로 변환
    if (src.startsWith('/')) {
      pushCandidate(src.replace(/^\/+/, ''));
    }

    // 3) chapter 기준 상대경로 후보
    if (!src.startsWith('/')) {
      pushCandidate(`${chapterDir}${src}`);
    } else {
      pushCandidate(`${chapterDir}${src.replace(/^\/+/, '')}`);
    }

    // 4) epub.js 경로 해석기 후보
    if (book.path && typeof book.path.resolve === 'function') {
      try {
        pushCandidate(book.path.resolve(src, chapterPath));
      } catch (_) {
        // ignore
      }
      try {
        pushCandidate(book.path.resolve(src.replace(/^\/+/, ''), chapterPath));
      } catch (_) {
        // ignore
      }
    }

    // 5) 매니페스트 경로 매칭 후보
    if (manifestHrefs.length > 0) {
      for (const href of manifestHrefs) {
        if (href === srcNoLeading || href.endsWith(`/${srcNoLeading}`)) {
          pushCandidate(href);
        }
      }
      // 파일명만 일치하는 fallback (레거시 EPUB 절대경로 대응)
      for (const href of manifestHrefs) {
        const hrefBase = href.includes('/') ? href.split('/').pop() : href;
        if (srcBaseName && hrefBase === srcBaseName) {
          pushCandidate(href);
        }
      }
    }

    for (const candidate of candidates) {
      const blobUrl = await createArchiveUrl(candidate);
      if (!blobUrl) continue;

      const isImage = await isLikelyImageBlobUrl(blobUrl, candidate);
      if (isImage) {
        const canRender = await canRenderImageUrl(blobUrl);
        if (canRender) return blobUrl;
      }

      // Prevent leaking invalid object URLs when candidate resolves to non-image resource.
      if (blobUrl.startsWith('blob:')) {
        try {
          URL.revokeObjectURL(blobUrl);
        } catch (_) {
          // ignore revoke errors
        }
      }
    }

    if (coverFallbackUrl && isCoverLikePath(src)) {
      return coverFallbackUrl;
    }

    return null;
  };

  const container = document.createElement('div');
  container.id = 'epub-merged-container';
  container.className = 'epub-merged-content';

  const spineItems = book.spine.spineItems;

  const chapters = [];
  // Promise.all 병렬 로딩은 대량의 JSZip 비동기 해제 경합으로 인한 OOM/누락을 유발하므로 순차 로드로 안정성 확보
  for (let idx = 0; idx < spineItems.length; idx++) {
    const item = spineItems[idx];
    try {
      // item.load()는 내부 컨텍스트 유실로 서버에 직접 GET을 날려 404를 내므로 book.load() 직접 기동
      const raw = await book.load(item.href, 'text');
      let doc = null;

      if (raw && (raw instanceof Document || raw.nodeType === 9 || typeof raw.getElementsByTagName === 'function')) {
        doc = raw;
      } else if (typeof raw === 'string') {
        doc = new DOMParser().parseFromString(raw, 'text/html');
      } else if (raw && raw.documentElement) {
        doc = raw;
      }

      chapters.push({ href: item.href, cfi: item.cfi, doc, idx });
    } catch (err) {
      console.warn('[Viewer-Epub] spine load skip:', item.href, err);
    }
  }

  const chapterNodes = await Promise.all(chapters.map(async chapter => {
    const chapterDiv = document.createElement('div');
    chapterDiv.className = 'epub-chapter-section';
    chapterDiv.dataset.href = chapter.href;
    chapterDiv.dataset.cfi = chapter.cfi;
    chapterDiv.dataset.index = chapter.idx;

    let html = '';
    if (chapter.doc) {
      let body = chapter.doc.body;
      if (!body && chapter.doc.querySelector) {
        body = chapter.doc.querySelector('body');
      }
      if (!body) {
        const bodies = chapter.doc.getElementsByTagName('body');
        if (bodies && bodies.length > 0) body = bodies[0];
      }

      const scopeNode = body || chapter.doc.documentElement;
      if (scopeNode) {
        const imgs = [];
        if (scopeNode.tagName && ['img', 'image'].includes(String(scopeNode.tagName).toLowerCase())) {
          imgs.push(scopeNode);
        }
        if (scopeNode.querySelectorAll) {
          imgs.push(...Array.from(scopeNode.querySelectorAll('img, image')));
        }

        for (const img of imgs) {
          const rawSrc =
            img.getAttribute('src') ||
            img.getAttribute('href') ||
            img.getAttribute('xlink:href') ||
            img.getAttribute('data-src') ||
            img.getAttribute('data-original');

          const blobUrl = await resolveImageUrl(rawSrc, chapter.href);
          if (blobUrl) {
            if (img.tagName && String(img.tagName).toLowerCase() === 'image') {
              img.setAttribute('href', blobUrl);
              img.setAttribute('xlink:href', blobUrl);
            } else {
              // XHTML/XML documents may not reflect property assignment to serialized attributes.
              img.setAttribute('src', blobUrl);
              img.removeAttribute('srcset');
              img.removeAttribute('sizes');

              // If image is inside <picture>, clear source srcset candidates that may override img src.
              const picture = img.closest && img.closest('picture');
              if (picture && picture.querySelectorAll) {
                const sources = Array.from(picture.querySelectorAll('source'));
                sources.forEach(source => {
                  source.removeAttribute('srcset');
                  source.removeAttribute('sizes');
                });
              }
            }
            img.removeAttribute('data-src');
            img.removeAttribute('data-original');
          } else if (rawSrc && !/^(data:|https?:|blob:|\/\/)/i.test(String(rawSrc).trim())) {
            const unresolved = String(rawSrc).trim();
            if (coverFallbackUrl && isCoverLikePath(unresolved)) {
              img.setAttribute('src', coverFallbackUrl);
              img.removeAttribute('data-src');
              img.removeAttribute('data-original');
              img.style.display = '';
            } else {
              // Prevent unresolved internal paths from falling back to site root / relative web paths.
              img.removeAttribute('src');
              img.setAttribute('data-unresolved-src', unresolved);
              img.style.display = 'none';
            }
          }
        }

        html = body ? body.innerHTML : (scopeNode.innerHTML || '');
      }
    }

    chapterDiv.innerHTML = html;
    return chapterDiv;
  }));

  chapterNodes.forEach(node => {
    if (node) container.appendChild(node);
  });

  return container;
}
