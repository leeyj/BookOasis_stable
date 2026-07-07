export function applyMergedThemeStyles(merged, theme, fontCSS, fontSize, lineHeight, paragraphSpacing) {
  merged.style.color = theme.text;
  merged.style.fontFamily = fontCSS;
  merged.style.fontSize = `${fontSize}rem`;

  const pList = merged.querySelectorAll('p, span, div, a, li');
  pList.forEach(p => {
    p.style.setProperty('font-family', fontCSS, 'important');
    p.style.setProperty('color', theme.text, 'important');
    p.style.lineHeight = lineHeight;
    if (p.tagName === 'P') {
      p.style.marginTop = `${paragraphSpacing}em`;
      p.style.marginBottom = `${paragraphSpacing}em`;
      p.style.paddingLeft = '0';
      p.style.paddingRight = '0';
    }
  });

  const hList = merged.querySelectorAll('h1, h2, h3, h4, h5, h6');
  hList.forEach(h => {
    h.style.setProperty('font-family', fontCSS, 'important');
    if (theme.heading) {
      h.style.setProperty('color', theme.heading, 'important');
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
      'font-family': `${fontCSS} !important`,
      'color': `${theme.text} !important`
    },
    'h1, h2, h3, h4, h5, h6': {
      'font-family': `${fontCSS} !important`,
      'color': `${theme.heading || theme.text} !important`
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
