(() => {
  const cards = [...document.querySelectorAll('.word-card')];
  const search = document.querySelector('#search-input');
  const filters = [...document.querySelectorAll('.filter')];
  const visibleCount = document.querySelector('#visible-count');
  const empty = document.querySelector('#empty-state');
  let activeMode = 'all';

  const normalize = (value) => value.toLocaleLowerCase().trim();
  const refresh = () => {
    const query = normalize(search?.value || '');
    let visible = 0;
    cards.forEach((card) => {
      const modeMatch = activeMode === 'all' || card.dataset.mode === activeMode;
      const searchMatch = !query || normalize(card.dataset.search || '').includes(query);
      const show = modeMatch && searchMatch;
      card.hidden = !show;
      if (show) {
        visible += 1;
      }
    });
    if (visibleCount) visibleCount.textContent = String(visible);
    if (empty) empty.hidden = visible !== 0;
  };

  search?.addEventListener('input', refresh);
  filters.forEach((button) => {
    button.addEventListener('click', () => {
      activeMode = button.dataset.filter || 'all';
      filters.forEach((item) => item.classList.toggle('is-active', item === button));
      refresh();
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && search && document.activeElement !== search) {
      event.preventDefault();
      search.focus();
    }
  });

  const randomButtons = [...document.querySelectorAll('#random-word')];
  randomButtons.forEach((button) => {
    button.addEventListener('click', async () => {
      try {
        const base = document.querySelector('link[rel="manifest"]')?.href.replace('site.webmanifest', '') || '/';
        const response = await fetch(`${base}search-index.json`);
        const entries = await response.json();
        const item = entries[Math.floor(Math.random() * entries.length)];
        if (item) window.location.href = item.url;
      } catch (_) {
        const visible = cards.filter((card) => !card.hidden);
        const item = visible[Math.floor(Math.random() * visible.length)];
        item?.querySelector('a')?.click();
      }
    });
  });

  document.querySelector('[data-reveal]')?.addEventListener('click', (event) => {
    const prose = document.querySelector('.prose');
    const concealed = prose?.classList.toggle('is-concealed');
    event.currentTarget.textContent = concealed ? '显示释义与例句' : '先遮住释义';
  });

  refresh();
})();
