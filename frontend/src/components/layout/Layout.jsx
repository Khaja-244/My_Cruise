import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import shipLogo from '../../assets/images/cruise-logo.png';

const navClass = ({ isActive }) =>
  `text-sm font-semibold transition ${isActive ? 'text-accent' : 'text-secondary hover:text-primary'}`;

export default function Layout() {
  const { user, logout, loading } = useAuth();
  const [open, setOpen] = useState(false);
  // The refreshed UI uses the clean light theme by default on every page.
  // Use a versioned key so older dark-theme preferences do not make the
  // updated application open in the old dark design.
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('my-cruise-theme-v2') || 'light'; } catch { return 'light'; }
  });
  const location = useLocation();
  const { data } = useQuery({
    queryKey: ['unread-count'],
    queryFn: async () => (await api.get('/notifications/unread-count')).data,
    enabled: !!user,
    refetchInterval: 60_000,
  });
  const close = () => setOpen(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('my-cruise-theme-v2', theme); } catch { /* storage may be unavailable */ }
  }, [theme]);

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <button
        type="button"
        className="theme-toggle"
        onClick={() => setTheme(current => current === 'dark' ? 'light' : 'dark')}
        aria-label={theme === 'dark' ? 'Switch to day mode' : 'Switch to dark mode'}
        title={theme === 'dark' ? 'Day mode' : 'Dark mode'}
      >
        <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
      </button>
      <header className="sticky top-0 z-50 border-b border-default/80 bg-surface/90 backdrop-blur-xl">
        <div className="container-app h-[72px] flex items-center justify-between gap-5">
          <Link to="/" onClick={close} className="flex items-center gap-3 shrink-0" aria-label="my_cruise home">
            <img src={shipLogo} alt="my_cruise" className="brand-logo" />
            <span>
              <span className="block text-[17px] font-extrabold tracking-tight text-primary">my_cruise</span>
              <span className="block text-[9px] uppercase tracking-[.2em] text-accent font-bold">Sail beautifully</span>
            </span>
          </Link>

          <nav className="hidden lg:flex items-center gap-7" aria-label="Primary navigation">
            <NavLink to="/cruises" className={navClass}>Explore cruises</NavLink>
            <a href="/#how-it-works" className={navClass}>How it works</a>
            <a href="/#deals" className={navClass}>Popular cruises</a>
          </nav>

          <div className="hidden lg:flex items-center gap-2">
            {loading ? (
              <div className="h-10 w-28 rounded-xl bg-surface-muted animate-pulse" aria-hidden="true" />
            ) : user ? (
              <>
                <NavLink to="/notifications" className="icon-button relative" aria-label="Notifications">
                  <span aria-hidden="true">🔔</span>
                  {!!Number(data?.count || 0) && <span className="notification-dot">{Number(data.count) > 99 ? '99+' : Number(data.count)}</span>}
                </NavLink>
                <NavLink to={user.role === 'admin' ? '/admin' : user.role === 'partner' ? '/partner' : '/dashboard'} className="btn btn-outline">Dashboard</NavLink>
                {user.role === 'traveler' && <NavLink to="/partner/apply" className="text-sm font-bold text-secondary px-2">Become a partner</NavLink>}
                <button onClick={logout} className="text-sm font-bold text-secondary px-2 hover:text-error">Logout</button>
              </>
            ) : (
              <>
                <NavLink to="/login" className="text-sm font-bold text-secondary px-2">Log in</NavLink>
                <NavLink to="/cruises" className="btn btn-primary">Explore</NavLink>
              </>
            )}
          </div>

          <button
            className="lg:hidden icon-button"
            onClick={() => setOpen(value => !value)}
            aria-expanded={open}
            aria-controls="mobile-navigation"
            aria-label={open ? 'Close menu' : 'Open menu'}
          >
            {open ? '×' : '☰'}
          </button>
        </div>

        {open && (
          <div id="mobile-navigation" className="lg:hidden border-t border-default bg-surface shadow-lg">
            <nav className="container-app py-5 space-y-2" aria-label="Mobile navigation">
              <NavLink onClick={close} to="/cruises" className="mobile-nav-link">Explore cruises</NavLink>
              <a onClick={close} href="/#how-it-works" className="mobile-nav-link">How it works</a>
              {user ? (
                <>
                  <NavLink onClick={close} to={user.role === 'admin' ? '/admin' : user.role === 'partner' ? '/partner' : '/dashboard'} className="mobile-nav-link">Dashboard</NavLink>
                  <NavLink onClick={close} to="/bookings" className="mobile-nav-link">My bookings</NavLink>
                  <NavLink onClick={close} to="/saved" className="mobile-nav-link">Saved cruises</NavLink>
                  <NavLink onClick={close} to="/notifications" className="mobile-nav-link">Notifications</NavLink>
                  <NavLink onClick={close} to="/profile" className="mobile-nav-link">Profile</NavLink>
                  {user.role === 'traveler' && <NavLink onClick={close} to="/partner/apply" className="mobile-nav-link">Become a partner</NavLink>}
                  <button onClick={() => { logout(); close(); }} className="mobile-nav-link text-left text-error">Logout</button>
                </>
              ) : (
                <>
                  <NavLink onClick={close} to="/login" className="mobile-nav-link">Log in</NavLink>
                  <NavLink onClick={close} to="/cruises" className="btn btn-primary w-full mt-2">Explore</NavLink>
                </>
              )}
            </nav>
          </div>
        )}
      </header>

      <main id="main-content" className="flex-1 page-shell">
        <Outlet key={location.pathname} />
      </main>

      <footer className="border-t border-default bg-surface">
        <div className="container-app py-12 grid sm:grid-cols-2 lg:grid-cols-4 gap-9">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3"><img src={shipLogo} alt="my_cruise" className="brand-logo brand-logo-sm" /><span className="font-extrabold text-primary">my_cruise</span></div>
            <p className="muted text-sm leading-6 mt-4 max-w-md">A modern cruise booking experience built around transparent pricing, live cabin availability and secure payments.</p>
          </div>
          <div><p className="font-bold text-primary mb-4">Company</p><div className="space-y-3 text-sm muted"><Link className="footer-link" to="/about">About</Link><Link className="footer-link" to="/faq">FAQ</Link><Link className="footer-link" to="/support">Support</Link></div></div>
          <div><p className="font-bold text-primary mb-4">Legal</p><div className="space-y-3 text-sm muted"><Link className="footer-link" to="/terms">Terms</Link><Link className="footer-link" to="/privacy">Privacy</Link><Link className="footer-link" to="/refund-policy">Refund policy</Link><Link className="footer-link" to="/booking-policy">Booking policy</Link></div></div>
        </div>
        <div className="border-t border-default"><div className="container-app py-5 text-xs text-muted flex flex-wrap justify-between gap-3"><span>© {new Date().getFullYear()} my_cruise</span><span>Secure payments · Live availability · USD pricing</span></div></div>
      </footer>
    </div>
  );
}
