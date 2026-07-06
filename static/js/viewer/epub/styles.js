export function applyMergedThemeStyles(merged, theme, fontCSS, fontSize, lineHeight, paragraphSpacing) {
  merged.style.color = theme.text;
  merged.style.fontFamily = fontCSS;
  merged.style.fontSize = `${fontSize}rem`;

  const pList = merged.querySelectorAll('p, span, div');
  pList.forEach(p => {
    p.style.fontFamily = fontCSS; // 자식 요소에도 선택한 폰트를 강제 적용하여 EPUB 고유 폰트 스타일 덮어쓰기
    p.style.lineHeight = lineHeight;
    if (p.tagName === 'P') {
      p.style.marginTop = `${paragraphSpacing}em`;
      p.style.marginBottom = `${paragraphSpacing}em`;
      p.style.paddingLeft = '0';
      p.style.paddingRight = '0';
    }
  });
}

export function applyRenditionTheme(rendition, theme, fontCSS, fontSize, lineHeight, paragraphSpacing) {
  if (!rendition) return;

  rendition.themes.default({
    body: {
      background: theme.background,
      color: theme.text,
      'font-family': fontCSS,
      'font-size': `${fontSize}rem`,
      'line-height': lineHeight
    },
    'p, span, div, a, li': {
      'font-family': `${fontCSS} !important`
    },
    p: {
      'margin-top': `${paragraphSpacing}em`,
      'margin-bottom': `${paragraphSpacing}em`
    },
    img: {
      'max-width': '100%'
    }
  });

  rendition.themes.select('default');
}
