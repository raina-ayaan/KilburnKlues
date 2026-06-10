const { useState, useEffect, useRef } = React;

/* ── Auth helpers ────────────────────────────────────────────────────── */
function getUser() {
    try { return JSON.parse(sessionStorage.getItem('kk_user')); } catch { return null; }
}

/* ── Apply saved theme before first paint ────────────────────────────── */
(function () {
    const saved = localStorage.getItem('kk_theme') ||
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', saved);
})();

/* ── Google Sign-In Modal ────────────────────────────────────────────── */
function GoogleSignInModal({ onClose, onSuccess }) {
    const btnRef = useRef(null);
    const CLIENT_ID = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? '414005391283-o63ui3ti7j32medre5k4qfbkofbvcti3.apps.googleusercontent.com'
        : '414005391283-kbg8ht1vi44mkaale2rst3v0l5ff6pj0.apps.googleusercontent.com';

    useEffect(() => {
        function renderButton() {
            if (!window.google || !btnRef.current) return;
            window.google.accounts.id.initialize({
                client_id: CLIENT_ID,
                callback: (response) => {
                    const payload  = JSON.parse(atob(response.credential.split('.')[1]));
                    const userData = {
                        name:      payload.name,
                        email:     payload.email,
                        google_id: payload.sub,
                        picture:   payload.picture,
                    };
                    sessionStorage.setItem('kk_user', JSON.stringify(userData));
                    onSuccess(userData);
                },
            });
            window.google.accounts.id.renderButton(btnRef.current, {
                theme: 'outline', size: 'large', width: 300,
                text: 'signin_with', shape: 'rectangular',
            });
        }
        if (window.google) {
            renderButton();
        } else {
            const interval = setInterval(() => {
                if (window.google) { clearInterval(interval); renderButton(); }
            }, 100);
            return () => clearInterval(interval);
        }
    }, []);

    return (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
            <div className="modal">
                <button className="modal-close" onClick={onClose}>✕</button>
                <div className="modal-logo">
                    <span style={{ width:8, height:8, borderRadius:'50%', background:'var(--accent)', display:'inline-block' }} />
                    Kilburn Klues
                </div>
                <div>
                    <div className="modal-title">Sign in</div>
                    <div className="modal-sub" style={{ marginTop:'0.4rem' }}>
                        Use your University of Manchester Google account to save your score and track progress.
                    </div>
                </div>
                <div className="modal-divider" />
                <div className="google-btn-wrap"><div ref={btnRef} /></div>
                <p style={{ fontSize:'0.75rem', color:'var(--text-3)', textAlign:'center' }}>
                    Your account details are only used to save your score.
                </p>
            </div>
        </div>
    );
}

/* ── App ─────────────────────────────────────────────────────────────── */
function App() {
    const [user,     setUser]     = useState(getUser);
    const [showAuth, setShowAuth] = useState(false);
    const [dropOpen, setDropOpen] = useState(false);

    /* ── One-time setup on mount ── */
    useEffect(() => {
        /* 1. Theme toggle */
        const themeBtn = document.getElementById('theme-toggle');
        if (themeBtn) {
            themeBtn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙';
            themeBtn.addEventListener('click', () => {
                const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', next);
                localStorage.setItem('kk_theme', next);
                themeBtn.textContent = next === 'dark' ? '☀️' : '🌙';
            });
        }

        /* 2. User menu toggle */
        const menuToggle = document.getElementById('user-menu-toggle');
        if (menuToggle) menuToggle.addEventListener('click', () => setDropOpen(o => !o));

        /* 3. Hero sign-in ghost button */
        const heroBtn = document.getElementById('hero-sign-in');
        if (heroBtn) heroBtn.addEventListener('click', () => setShowAuth(true));

        /* 4. Close dropdown on outside click */
        function handleOutside(e) {
            const menu = document.getElementById('user-menu');
            if (menu && !menu.contains(e.target)) setDropOpen(false);
        }
        document.addEventListener('mousedown', handleOutside);

        /* 5. Nav becomes frosted after scrolling past the hero title */
        const nav = document.querySelector('.nav');
        function handleScroll() {
            if (nav) nav.classList.toggle('scrolled', window.scrollY > 80);
        }
        window.addEventListener('scroll', handleScroll, { passive: true });
        handleScroll(); // run once in case page is already scrolled

        /* 6. Scroll-reveal: watch every .reveal element */
        const revealEls = document.querySelectorAll('.reveal');
        const revealObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                        revealObserver.unobserve(entry.target); // animate once
                    }
                });
            },
            { threshold: 0.12 }
        );
        revealEls.forEach(el => revealObserver.observe(el));

        /* 7. Hero panels — animate in when they enter the viewport */
        const panelInners = document.querySelectorAll('.hero-panel-inner');
        const panelObserver = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('visible');
                        panelObserver.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.2 }
        );
        panelInners.forEach(el => panelObserver.observe(el));

        return () => {
            document.removeEventListener('mousedown', handleOutside);
            window.removeEventListener('scroll', handleScroll);
            revealObserver.disconnect();
            panelObserver.disconnect();
        };
    }, []);

    /* ── Sync dropdown visibility ── */
    useEffect(() => {
        const dropdown = document.getElementById('user-dropdown');
        if (dropdown) dropdown.style.display = dropOpen ? 'block' : 'none';
    }, [dropOpen]);

    /* ── Sync auth state to HTML elements ── */
    useEffect(() => {
        const menuToggle = document.getElementById('user-menu-toggle');
        const authBtn    = document.getElementById('auth-btn');
        const badge      = document.getElementById('score-badge');
        const heroBtn    = document.getElementById('hero-sign-in');
        const pastScoresLink = document.getElementById('past-scores-link');

        if (menuToggle) {
            menuToggle.innerHTML = `${user ? user.name : 'Account'} <span style="opacity:0.5">▾</span>`;
        }
        if (heroBtn) heroBtn.style.display = user ? 'none' : '';

        if (authBtn) {
            authBtn.textContent = user ? 'Sign Out' : 'Sign In';
            authBtn.onclick = user
                ? () => { sessionStorage.removeItem('kk_user'); setUser(null); setDropOpen(false); }
                : () => { setDropOpen(false); setShowAuth(true); };
        }

        if (pastScoresLink) {
            pastScoresLink.style.display = user ? '' : 'none';
        }

        if (user) {
            fetch(`api.php?action=get_total_score&google_id=${encodeURIComponent(user.google_id)}`)
                .then(r => r.json())
                .then(d => {
                    if (badge && d.total_score > 0) {
                        badge.textContent   = `⭐ ${d.total_score} pts`;
                        badge.style.display = '';
                    }
                })
                .catch(() => {});
        } else if (badge) {
            badge.style.display = 'none';
        }
    }, [user]);

    return showAuth ? (
        <GoogleSignInModal
            onClose={() => setShowAuth(false)}
            onSuccess={u => { setUser(u); setShowAuth(false); }}
        />
    ) : null;
}

ReactDOM.createRoot(document.getElementById('react-modal-root')).render(<App />);
