import os
import tempfile
import unittest
import zipfile

from services.text_epub_content_service import TextEpubContentService

_CONTAINER = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>'
    '</container>'
)

# 웹 서점 뷰어에서 내려받은 EPUB 2에서 실제로 나온 형태: 기본 xmlns 대신 opf: 접두사를 쓴다(표준상 유효).
_PREFIXED_OPF = (
    "<?xml version='1.0' encoding='utf-8'?>"
    '<opf:package xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf" version="2.0">'
    '<opf:metadata><dc:title>접두사 OPF</dc:title></opf:metadata>'
    '<opf:manifest>'
    '<opf:item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml" />'
    '<opf:item id="ch1" href="text/ch1.xhtml" media-type="application/xhtml+xml" />'
    '<opf:item id="ch2" href="text/ch2.xhtml" media-type="application/xhtml+xml" />'
    '</opf:manifest>'
    '<opf:spine toc="ncx"><opf:itemref idref="ch1" /><opf:itemref idref="ch2" /></opf:spine>'
    '</opf:package>'
)

_DEFAULT_NS_OPF = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>기본 OPF</dc:title></metadata>'
    '<manifest>'
    '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml" />'
    '<item id="ch1" href="text/ch1.xhtml" media-type="application/xhtml+xml" />'
    '<item id="ch2" href="text/ch2.xhtml" media-type="application/xhtml+xml" />'
    '</manifest>'
    '<spine toc="ncx"><itemref idref="ch1" /><itemref idref="ch2" /></spine>'
    '</package>'
)

_NCX = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><navMap>'
    '<navPoint id="a" playOrder="1"><navLabel><text>첫 장</text></navLabel><content src="text/ch1.xhtml" /></navPoint>'
    '<navPoint id="b" playOrder="2"><navLabel><text>둘째 장</text></navLabel><content src="text/ch2.xhtml" /></navPoint>'
    '</navMap></ncx>'
)


def _chapter(body):
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>t</title>'
        '<script src="../../../reader/fanmurim_polyfill.js"></script></head>'
        f'<body><p>{body}</p></body></html>'
    )


class PrefixedOpfTest(unittest.TestCase):
    def _make_epub(self, opf):
        handle, path = tempfile.mkstemp(suffix='.epub')
        os.close(handle)
        self.addCleanup(os.remove, path)
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('mimetype', 'application/epub+zip')
            zf.writestr('META-INF/container.xml', _CONTAINER)
            zf.writestr('OEBPS/content.opf', opf)
            zf.writestr('OEBPS/toc.ncx', _NCX)
            zf.writestr('OEBPS/text/ch1.xhtml', _chapter('첫 본문'))
            zf.writestr('OEBPS/text/ch2.xhtml', _chapter('둘째 본문'))
        return path

    def _assert_readable(self, opf, title):
        path = self._make_epub(opf)
        meta, err = TextEpubContentService.get_epub_meta(path, None, 'general')
        self.assertIsNone(err)
        self.assertEqual(meta['title'], title)
        self.assertEqual(meta['total_chapters'], 2)
        self.assertEqual(meta['spine_itemrefs'], ['text/ch1.xhtml', 'text/ch2.xhtml'])
        self.assertEqual([t['chapter_idx'] for t in meta['toc']], [0, 1])

        chapter, err = TextEpubContentService.get_epub_chapter(path, None, 'general', 1)
        self.assertIsNone(err)
        self.assertIn('둘째 본문', chapter['content'])

    def test_prefixed_opf_is_readable(self):
        self._assert_readable(_PREFIXED_OPF, '접두사 OPF')

    def test_default_namespace_opf_still_readable(self):
        self._assert_readable(_DEFAULT_NS_OPF, '기본 OPF')


if __name__ == '__main__':
    unittest.main()
