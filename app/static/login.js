(() => {
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)');

    const getTheme = () => localStorage.getItem('theme') || 'auto';

    function applyTheme(mode = getTheme()) {
        const dark =
            mode === 'dark' ||
            (mode === 'auto' && systemDark.matches);

        document.documentElement.classList.toggle('dark', dark);
        document.documentElement.dataset.theme = mode;

        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) {
            meta.content = dark ? '#0c1118' : '#f4f6f8';
        }
    }

    systemDark.addEventListener?.('change', () => {
        if (getTheme() === 'auto') {
            applyTheme('auto');
        }
    });

    applyTheme();
})();
