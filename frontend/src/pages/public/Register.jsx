import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api, setAccessToken } from '../../api/client';
import { cruiseImages } from '../../lib/images';
import shipLogo from '../../assets/images/cruise-logo.png';
import NoticeDialog from '../../components/ui/NoticeDialog';

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showSuccess, setShowSuccess] = useState(false);

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');

    try {
      const response = await api.post('/auth/register', form);
      setAccessToken(response.data.access_token);
      setShowSuccess(true);
    } catch (requestError) {
      setError(
        requestError.response?.data?.error?.message ||
          'We could not create your account. Please check your details and try again.',
      );
    } finally {
      setBusy(false);
    }
  }

  function continueToVerification() {
    setShowSuccess(false);
    navigate(`/verify-otp?email=${encodeURIComponent(form.email)}`);
  }

  return (
    <>
      <NoticeDialog
        open={showSuccess}
        title="Account created"
        message="Your account has been created. We will verify your email before you start booking."
        buttonLabel="Verify my email"
        onClose={continueToVerification}
      />

      <div className="min-h-[calc(100vh-72px)] bg-surface-muted px-4 py-10 sm:py-14">
        <div className="mx-auto grid max-w-5xl overflow-hidden rounded-[30px] border border-default bg-surface shadow-xl lg:grid-cols-2">
          <div className="register-hero-panel relative min-h-[460px] overflow-hidden p-8 text-inverse sm:p-12 lg:p-14">
            <img
              src={cruiseImages.hero}
              alt="Luxury cruise ship sailing across the ocean"
              className="absolute inset-0 h-full w-full object-cover"
              onError={(event) => {
                event.currentTarget.style.display = 'none';
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-br from-navy-950/80 via-navy-900/55 to-brand-900/45" />

            <div className="relative z-10 flex h-full flex-col justify-between">
              <div>
                <img src={shipLogo} alt="my_cruise" className="brand-logo" />
                <p className="eyebrow mt-12 text-inverse-muted">Start your journey</p>
                <h1 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">
                  More sea.
                  <br />
                  Less planning.
                </h1>
                <p className="mt-5 max-w-md leading-7 text-inverse-muted">
                  Save cruises, manage your bookings and keep your travel details together.
                </p>
              </div>

              <div className="mt-10 space-y-2 text-sm text-slate-100">
                <p>✓ Choose your exact cabin</p>
                <p>✓ Secure USD checkout</p>
                <p>✓ Get a digital e-ticket</p>
              </div>
            </div>
          </div>

          <div className="p-7 sm:p-12 lg:p-14">
            <p className="eyebrow">Traveler account</p>
            <h2 className="mt-2 text-3xl font-extrabold text-primary">Create your account</h2>
            <p className="muted mt-2">Create your account in less than a minute.</p>

            {error && (
              <div className="mt-5 rounded-xl border border-error bg-error-soft p-4 text-sm text-error" role="alert">
                {error}
              </div>
            )}

            <form className="mt-7 space-y-4" onSubmit={handleSubmit}>
              <label className="block text-sm font-bold text-secondary">
                Full name
                <input
                  className="input mt-1.5"
                  value={form.full_name}
                  onChange={(event) => updateField('full_name', event.target.value)}
                  required
                  placeholder="Your full name"
                />
              </label>

              <label className="block text-sm font-bold text-secondary">
                Email
                <input
                  className="input mt-1.5"
                  type="email"
                  value={form.email}
                  onChange={(event) => updateField('email', event.target.value)}
                  required
                  placeholder="you@example.com"
                />
              </label>

              <label className="block text-sm font-bold text-secondary">
                Password
                <input
                  className="input mt-1.5"
                  type="password"
                  value={form.password}
                  onChange={(event) => updateField('password', event.target.value)}
                  required
                  minLength={8}
                  placeholder="At least 8 characters"
                />
              </label>

              <p className="text-xs text-muted">Use at least 8 characters with a letter and a number.</p>

              <button type="submit" disabled={busy} className="btn btn-primary w-full py-3.5">
                {busy ? 'Creating account…' : 'Create account'}
              </button>
            </form>

            <p className="muted mt-7 text-center text-sm">
              Already registered?{' '}
              <Link className="font-bold text-accent" to="/login">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
