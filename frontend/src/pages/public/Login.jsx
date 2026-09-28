import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { cruiseImages } from '../../lib/images';
import shipLogo from '../../assets/images/cruise-logo.png';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(event) {
    event.preventDefault();

    setBusy(true);
    setError('');

    try {
      const result = await login({ email, password });
      const user = result.user;

      if (user.must_change_password) {
        navigate('/profile', {
          replace: true,
          state: { mustChangePassword: true },
        });
      } else if (user.role === 'admin') {
        navigate('/admin', { replace: true });
      } else if (user.role === 'partner') {
        navigate('/partner', { replace: true });
      } else {
        navigate('/dashboard', { replace: true });
      }
    } catch (requestError) {
      setError(
        requestError.response?.data?.error?.message ||
          'Login failed. Please check your details.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-72px)] bg-surface-muted px-4 py-6 sm:py-8">
      <div className="mx-auto grid max-w-6xl overflow-hidden rounded-[24px] border border-default bg-surface shadow-xl lg:grid-cols-2">
      <div className="login-hero-panel relative hidden min-h-[560px] overflow-hidden bg-navy-900 p-8 xl:p-10 text-inverse lg:flex lg:items-end">
        <img
          src={cruiseImages.whiteShip}
          alt="White cruise ship sailing on the ocean"
          className="absolute inset-0 h-full w-full object-cover"
          onError={(event) => {
            event.currentTarget.src = cruiseImages.hero;
          }}
        />

        <div className="absolute inset-0 bg-gradient-to-t from-navy-900 via-navy-900/65 to-navy-900/15" />

        <div className="relative z-10">
          <p className="eyebrow text-inverse-muted">Welcome aboard</p>
          <h1 className="mt-3 text-4xl font-extrabold tracking-tight xl:text-[2.8rem]">
            Pick up where
            <br />
            your journey left off.
          </h1>
          <p className="mt-5 max-w-lg text-inverse-muted">
            Manage your saved cruises, bookings, tickets and notifications from
            one place.
          </p>
        </div>
      </div>

      <div className="grid place-items-center bg-surface p-6 sm:p-8 lg:p-10">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex items-center gap-3">
            <img src={shipLogo} alt="my_cruise" className="brand-logo" />
            <div>
              <p className="font-extrabold text-primary">my_cruise</p>
              <p className="text-[10px] font-extrabold uppercase tracking-[.18em] text-accent">
                Sail beautifully
              </p>
            </div>
          </div>

          <p className="eyebrow">Traveler account</p>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-primary">
            Welcome back
          </h1>
          <p className="muted mt-2">
            Sign in to continue your cruise journey.
          </p>

          {error && (
            <div className="mt-5 rounded-xl border border-error bg-error-soft p-3 text-sm text-error">
              {error}
            </div>
          )}

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <label className="block text-sm font-bold text-secondary">
              Email
              <input
                className="input mt-1.5"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                placeholder="you@example.com"
              />
            </label>

            <label className="block text-sm font-bold text-secondary">
              Password
              <input
                className="input mt-1.5"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                placeholder="Your password"
              />
            </label>

            <div className="flex justify-end">
              <Link
                className="text-sm font-bold text-accent"
                to="/forgot-password"
              >
                Forgot password?
              </Link>
            </div>

            <button
              disabled={busy}
              className="btn btn-primary w-full py-3.5"
            >
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="muted mt-7 text-center text-sm">
            New to my_cruise?{' '}
            <Link className="font-bold text-accent" to="/register">
              Create an account
            </Link>
          </p>
        </div>
      </div>
      </div>
    </div>
  );
}
