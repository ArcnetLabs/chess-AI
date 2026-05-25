/* ============================================================
   ChessIQ Document Suite — shared.js
   ============================================================ */

/* ── IntersectionObserver: Active TOC highlighting ──────────── */
function initTOCObserver() {
  const anchors  = document.querySelectorAll('.section-anchor');
  const tocLinks = document.querySelectorAll('.toc-link');
  if (!anchors.length || !tocLinks.length) return;

  const linkMap = new Map();
  tocLinks.forEach(link => {
    const href = link.getAttribute('href');
    if (href && href.startsWith('#')) linkMap.set(href.slice(1), link);
  });

  let lastActive = null;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      const link = linkMap.get(entry.target.id);
      if (!link) return;
      if (entry.isIntersecting) {
        if (lastActive) lastActive.classList.remove('active');
        link.classList.add('active');
        lastActive = link;
      }
    });
  }, {
    rootMargin: `-${56 + 20}px 0px -68% 0px`,
    threshold: 0
  });

  anchors.forEach(el => observer.observe(el));
}

/* ── Copy-to-Clipboard ───────────────────────────────────────── */
function copyCode(btn) {
  const block  = btn.closest('.code-block');
  const codeEl = block ? block.querySelector('code') : null;
  if (!codeEl) return;

  const text = codeEl.textContent || codeEl.innerText;

  const finish = () => {
    btn.textContent = 'Copied ✓';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  };

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(finish).catch(() => fallbackCopy(text, finish));
  } else {
    fallbackCopy(text, finish);
  }
}

function fallbackCopy(text, callback) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;opacity:0;top:-9999px;left:-9999px';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch (_) {}
  document.body.removeChild(ta);
  callback();
}

/* ── Sidebar Toggle (mobile) ─────────────────────────────────── */
function initSidebarToggle() {
  const hamburger = document.getElementById('hamburger');
  const sidebar   = document.querySelector('.sidebar');
  const overlay   = document.querySelector('.sidebar-overlay');
  if (!hamburger || !sidebar) return;

  const open  = () => { sidebar.classList.add('open');    overlay && overlay.classList.add('visible'); };
  const close = () => { sidebar.classList.remove('open'); overlay && overlay.classList.remove('visible'); };

  hamburger.addEventListener('click', () =>
    sidebar.classList.contains('open') ? close() : open()
  );

  overlay && overlay.addEventListener('click', close);

  /* Close when a TOC link is tapped on mobile */
  sidebar.querySelectorAll('.toc-link').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 768) close();
    });
  });
}

/* ── Back-to-Top ─────────────────────────────────────────────── */
function initBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;

  window.addEventListener('scroll', () => {
    btn.classList.toggle('visible', window.scrollY > 320);
  }, { passive: true });

  btn.addEventListener('click', () =>
    window.scrollTo({ top: 0, behavior: 'smooth' })
  );
}

/* ── Mermaid Configuration ───────────────────────────────────── */
function initMermaid() {
  if (typeof mermaid === 'undefined') return;

  mermaid.initialize({
    startOnLoad: true,
    theme: 'base',
    themeVariables: {
      primaryColor:          '#141a20',
      primaryTextColor:      '#e7ebf3',
      primaryBorderColor:    '#252d35',
      lineColor:             '#4a5568',
      secondaryColor:        '#0e1419',
      tertiaryColor:         '#252d35',
      background:            '#0a0f14',
      mainBkg:               '#141a20',
      nodeBorder:            '#252d35',
      clusterBkg:            '#0e1419',
      clusterBorder:         '#252d35',
      titleColor:            '#84FF00',
      edgeLabelBackground:   '#141a20',
      fontFamily:            'Inter, -apple-system, sans-serif',
      nodeTextColor:         '#e7ebf3',
      labelTextColor:        '#e7ebf3',
      /* Sequence diagrams */
      actorBkg:              '#141a20',
      actorBorder:           '#252d35',
      actorTextColor:        '#e7ebf3',
      actorLineColor:        '#4a5568',
      signalColor:           '#8a97a8',
      signalTextColor:       '#e7ebf3',
      loopTextColor:         '#e7ebf3',
      noteBkgColor:          '#252d35',
      noteTextColor:         '#e7ebf3',
      noteBorderColor:       '#2e3840',
    },
    flowchart: { htmlLabels: true, curve: 'basis', diagramPadding: 16 },
    sequence:  { diagramMarginX: 20, diagramMarginY: 20 },
  });
}

/* ── highlight.js init ───────────────────────────────────────── */
function initHljs() {
  if (typeof hljs === 'undefined') return;
  hljs.configure({ ignoreUnescapedHTML: true });
  hljs.highlightAll();
}

/* ── DOMContentLoaded bootstrap ─────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initMermaid();
  initHljs();
  initTOCObserver();
  initSidebarToggle();
  initBackToTop();
});
