(() => {
  'use strict';

  const root = document.documentElement;
  const themeButton = document.querySelector('[data-theme-toggle]');
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  const darkPreference = window.matchMedia('(prefers-color-scheme: dark)');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  const storage = {
    get(key) {
      try {
        return window.localStorage.getItem(key);
      } catch (_) {
        return null;
      }
    },
    set(key, value) {
      try {
        window.localStorage.setItem(key, value);
      } catch (_) {
        // Theme persistence is optional; the interface remains fully usable.
      }
    },
  };

  let manualTheme = storage.get('lexicon-theme');
  if (!['light', 'dark'].includes(manualTheme)) manualTheme = null;

  const preferredTheme = () => (darkPreference.matches ? 'dark' : 'light');
  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    if (themeMeta) themeMeta.content = theme === 'dark' ? '#000000' : '#f5f5f7';
    if (themeButton) {
      themeButton.dataset.currentTheme = theme;
      themeButton.setAttribute(
        'aria-label',
        theme === 'dark' ? '切换到浅色主题' : '切换到深色主题',
      );
      themeButton.title = themeButton.getAttribute('aria-label');
    }
  };

  applyTheme(manualTheme || preferredTheme());
  themeButton?.addEventListener('click', () => {
    const nextTheme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    manualTheme = nextTheme;
    storage.set('lexicon-theme', nextTheme);
    applyTheme(nextTheme);
  });
  darkPreference.addEventListener?.('change', () => {
    if (!manualTheme) applyTheme(preferredTheme());
  });

  const dateFormatter = new Intl.DateTimeFormat(
    navigator.languages?.length ? navigator.languages : ['zh-CN'],
    { year: 'numeric', month: 'short', day: 'numeric' },
  );
  document.querySelectorAll('time[data-format-date][datetime]').forEach((time) => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(time.getAttribute('datetime') || '');
    if (!match) return;
    const [, year, month, day] = match;
    const value = new Date(Number(year), Number(month) - 1, Number(day));
    const prefix = time.dataset.datePrefix || '';
    time.textContent = `${prefix}${prefix ? ' ' : ''}${dateFormatter.format(value)}`;
  });

  const baseUrl = document.body.dataset.baseUrl || '/';
  let searchIndexPromise;
  const getSearchIndex = () => {
    if (!searchIndexPromise) {
      const indexUrl = new URL(`${baseUrl}search-index.json`, window.location.href);
      searchIndexPromise = fetch(indexUrl, { credentials: 'same-origin' }).then((response) => {
        if (!response.ok) throw new Error(`Search index returned ${response.status}`);
        return response.json();
      });
    }
    return searchIndexPromise;
  };

  const normalize = (value) => String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase()
    .replace(/\s+/g, ' ')
    .trim();

  const secureRandomIndex = (length) => {
    if (length <= 1) return 0;
    if (window.crypto?.getRandomValues) {
      const values = new Uint32Array(1);
      window.crypto.getRandomValues(values);
      return values[0] % length;
    }
    return Math.floor(Math.random() * length);
  };

  const library = document.querySelector('[data-library]');
  let randomVisibleCard = null;

  if (library) {
    const grid = library.querySelector('#word-grid');
    const cards = [...library.querySelectorAll('[data-card]')];
    const search = library.querySelector('#search-input');
    const clearSearch = library.querySelector('[data-clear-search]');
    const resetLibrary = library.querySelector('[data-reset-library]');
    const modeButtons = [...library.querySelectorAll('[data-filter]')];
    const signalButtons = [...library.querySelectorAll('[data-signal]')];
    const sortSelect = library.querySelector('#sort-select');
    const visibleCount = library.querySelector('#visible-count');
    const resultStatus = library.querySelector('#result-status');
    const empty = library.querySelector('#empty-state');
    const collator = new Intl.Collator(['en', 'zh-CN'], {
      numeric: true,
      sensitivity: 'base',
    });
    const validModes = new Set(['all', 'production', 'recognition', 'phrase']);
    const validSignals = new Set(['repeat', 'lapse', 'focus']);
    const validSorts = new Set(['priority', 'encounters', 'lapses', 'az']);
    const params = new URLSearchParams(window.location.search);

    const state = {
      query: params.get('q') || '',
      mode: validModes.has(params.get('mode')) ? params.get('mode') : 'all',
      signals: new Set(
        (params.get('signals') || '')
          .split(',')
          .filter((signal) => validSignals.has(signal)),
      ),
      sort: validSorts.has(params.get('sort')) ? params.get('sort') : 'priority',
    };

    const records = cards.map((card, originalIndex) => ({
      card,
      originalIndex,
      title: card.dataset.title || '',
      mode: card.dataset.mode || '',
      encounters: Number(card.dataset.encounters || 1),
      lapses: Number(card.dataset.lapses || 0),
      priority: Number(card.dataset.priority || 0),
      priorityScore: Number(card.dataset.priorityScore || 0),
      focus: card.dataset.focus === 'true',
      searchText: normalize(card.dataset.search),
    }));

    if (search) search.value = state.query;
    if (sortSelect) sortSelect.value = state.sort;

    const compareRecords = (left, right) => {
      const alpha = collator.compare(left.title, right.title);
      if (state.sort === 'az') return alpha || left.originalIndex - right.originalIndex;
      if (state.sort === 'encounters') {
        return right.encounters - left.encounters
          || right.lapses - left.lapses
          || right.priorityScore - left.priorityScore
          || alpha;
      }
      if (state.sort === 'lapses') {
        return right.lapses - left.lapses
          || right.encounters - left.encounters
          || right.priorityScore - left.priorityScore
          || alpha;
      }
      return right.priority - left.priority
        || right.priorityScore - left.priorityScore
        || right.lapses - left.lapses
        || right.encounters - left.encounters
        || alpha;
    };

    const updateUrl = () => {
      const url = new URL(window.location.href);
      const query = state.query.trim();
      if (query) url.searchParams.set('q', query);
      else url.searchParams.delete('q');
      if (state.mode !== 'all') url.searchParams.set('mode', state.mode);
      else url.searchParams.delete('mode');
      if (state.signals.size) {
        url.searchParams.set('signals', [...state.signals].sort().join(','));
      } else {
        url.searchParams.delete('signals');
      }
      if (state.sort !== 'priority') url.searchParams.set('sort', state.sort);
      else url.searchParams.delete('sort');
      try {
        window.history.replaceState(null, '', url);
      } catch (_) {
        // Local file previews can reject history changes; filtering still works.
      }
    };

    const matchesSignals = (record) => {
      if (state.signals.has('repeat') && record.encounters <= 1) return false;
      if (state.signals.has('lapse') && record.lapses <= 0) return false;
      if (state.signals.has('focus') && !record.focus) return false;
      return true;
    };

    const refresh = ({ persist = true } = {}) => {
      const tokens = normalize(state.query).split(' ').filter(Boolean);
      const sorted = [...records].sort(compareRecords);
      let visible = 0;

      sorted.forEach((record) => {
        const modeMatch = state.mode === 'all' || record.mode === state.mode;
        const searchMatch = tokens.every((token) => record.searchText.includes(token));
        const show = modeMatch && matchesSignals(record) && searchMatch;
        record.card.hidden = !show;
        if (show) visible += 1;
        grid?.append(record.card);
      });

      modeButtons.forEach((button) => {
        const active = button.dataset.filter === state.mode;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      signalButtons.forEach((button) => {
        const active = state.signals.has(button.dataset.signal);
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      if (visibleCount) {
        visibleCount.textContent = new Intl.NumberFormat(navigator.languages).format(visible);
      }
      if (resultStatus) {
        resultStatus.setAttribute(
          'aria-label',
          `当前显示 ${visible} 张，共 ${records.length} 张词卡`,
        );
      }
      if (empty) empty.hidden = visible !== 0;
      if (clearSearch) clearSearch.hidden = !state.query;
      library.classList.toggle('has-active-filters', state.mode !== 'all' || state.signals.size > 0);
      if (persist) updateUrl();
    };

    const reset = () => {
      state.query = '';
      state.mode = 'all';
      state.signals.clear();
      state.sort = 'priority';
      if (search) search.value = '';
      if (sortSelect) sortSelect.value = state.sort;
      refresh();
      search?.focus();
    };

    search?.addEventListener('input', () => {
      state.query = search.value;
      refresh();
    });
    clearSearch?.addEventListener('click', () => {
      state.query = '';
      if (search) search.value = '';
      refresh();
      search?.focus();
    });
    resetLibrary?.addEventListener('click', reset);
    modeButtons.forEach((button) => {
      button.addEventListener('click', () => {
        state.mode = button.dataset.filter || 'all';
        refresh();
      });
    });
    signalButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const signal = button.dataset.signal;
        if (!validSignals.has(signal)) return;
        if (state.signals.has(signal)) state.signals.delete(signal);
        else state.signals.add(signal);
        refresh();
      });
    });
    sortSelect?.addEventListener('change', () => {
      state.sort = validSorts.has(sortSelect.value) ? sortSelect.value : 'priority';
      refresh();
    });

    const visibleLinks = () => [...grid.querySelectorAll('[data-card]:not([hidden]) [data-card-link]')];

    const focusCard = (direction) => {
      const links = visibleLinks();
      if (!links.length) return;
      const activeIndex = links.indexOf(document.activeElement);
      const nextIndex = activeIndex < 0
        ? (direction > 0 ? 0 : links.length - 1)
        : (activeIndex + direction + links.length) % links.length;
      const link = links[nextIndex];
      link.focus({ preventScroll: true });
      link.scrollIntoView({
        block: 'nearest',
        behavior: reducedMotion.matches ? 'auto' : 'smooth',
      });
    };

    randomVisibleCard = () => {
      const links = visibleLinks();
      const link = links[secureRandomIndex(links.length)];
      if (link) window.location.href = link.href;
    };

    document.addEventListener('keydown', (event) => {
      const target = event.target;
      const isEditable = target instanceof HTMLElement
        && (target.matches('input, textarea, select') || target.isContentEditable);

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && search) {
        event.preventDefault();
        search.focus();
        search.select();
        return;
      }
      if (event.key === 'Escape' && search && (document.activeElement === search || state.query)) {
        event.preventDefault();
        state.query = '';
        search.value = '';
        refresh();
        search.focus();
        return;
      }
      if (isEditable || event.ctrlKey || event.metaKey || event.altKey) return;
      const cardHasFocus = document.activeElement instanceof HTMLElement
        && document.activeElement.matches('[data-card-link]')
        && grid?.contains(document.activeElement);
      if (!cardHasFocus) return;
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        event.preventDefault();
        focusCard(1);
      } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        event.preventDefault();
        focusCard(-1);
      }
    });

    refresh({ persist: false });

    getSearchIndex()
      .then((entries) => {
        const bySlug = new Map(entries.map((entry) => [entry.slug, entry]));
        records.forEach((record) => {
          const entry = bySlug.get(record.card.dataset.slug);
          if (!entry) return;
          record.searchText = normalize([
            record.searchText,
            entry.title,
            entry.lemma,
            ...(entry.forms || []),
            ...(entry.pos || []),
            entry.summary_cn,
            entry.zh_gloss,
            entry.summary_en,
            entry.plain,
          ].join(' '));
        });
        refresh({ persist: false });
      })
      .catch(() => {
        // The compact in-page index remains available when fetch is unavailable.
      });
  }

  document.querySelectorAll('[data-random-word]').forEach((button) => {
    button.addEventListener('click', async () => {
      if (randomVisibleCard) {
        randomVisibleCard();
        return;
      }
      try {
        const entries = await getSearchIndex();
        const item = entries[secureRandomIndex(entries.length)];
        if (item) window.location.href = item.url;
      } catch (_) {
        window.location.href = baseUrl;
      }
    });
  });

  const revealButton = document.querySelector('[data-reveal]');
  revealButton?.addEventListener('click', () => {
    const prose = document.querySelector('.vocabulary-note .prose');
    if (!prose) return;
    const concealed = prose.classList.toggle('is-concealed');
    prose.inert = concealed;
    if (concealed) prose.setAttribute('aria-hidden', 'true');
    else prose.removeAttribute('aria-hidden');
    revealButton.setAttribute('aria-pressed', String(concealed));
    revealButton.textContent = concealed ? '显示释义与例句' : '进入回忆模式';
  });
})();
