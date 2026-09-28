import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import { api } from '../../api/client';
import CabinDeckMap from '../../components/booking/CabinDeckMap';
import { Loading, ErrorBox } from '../../components/ui/States';

const stripePromise = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY
  ? loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY)
  : null;

function money(cents) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format((cents || 0) / 100);
}

/**
 * Stripe payment is intentionally kept in its own small component.
 * The server webhook is still the final source of truth for confirmation.
 */
function PaymentStep({ onConfirmed }) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    if (!stripe || !elements) return;

    setBusy(true);
    setError('');

    // Stripe recommends submitting the Payment Element first so its built-in
    // validation runs before the PaymentIntent is confirmed.
    const submitResult = await elements.submit();
    if (submitResult.error) {
      setError(submitResult.error.message || 'Please check your payment details.');
      setBusy(false);
      return;
    }

    const result = await stripe.confirmPayment({
      elements,
      redirect: 'if_required',
    });

    if (result.error) {
      setError(result.error.message || 'Payment could not be completed.');
    } else {
      onConfirmed();
    }

    setBusy(false);
  };

  return (
    <form onSubmit={submit} className="card max-w-2xl p-6 sm:p-8">
      <p className="eyebrow">Secure checkout</p>
      <h2 className="mt-2 text-2xl font-extrabold text-primary">Complete payment</h2>
      <p className="muted mt-2 text-sm">
        Stripe securely handles your payment details. Your booking is confirmed only by the server webhook.
      </p>

      <div className="mt-7">
        <PaymentElement />
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-error bg-error-soft p-3 text-sm text-error">
          {error}
        </div>
      )}

      <button className="btn btn-primary mt-6 w-full" disabled={!stripe || busy}>
        {busy ? 'Processing payment…' : 'Pay securely'}
      </button>
    </form>
  );
}

function BookingStepper({ currentStep }) {
  const steps = ['Cabin', 'Occupancy', 'Guests', 'Review', 'Payment', 'Confirmation'];

  return (
    <div className="mb-8 overflow-x-auto">
      <div className="flex min-w-max gap-2">
        {steps.map((label, index) => {
          const number = index + 1;
          const completed = currentStep > number;
          const active = currentStep === number;

          return (
            <div
              key={label}
              className={`rounded-full border px-4 py-2 text-sm font-bold ${
                active
                  ? 'border-accent bg-accent text-inverse'
                  : completed
                    ? 'border-brand-100 bg-accent-soft text-accent'
                    : 'border-default bg-surface text-muted'
              }`}
            >
              {number}. {label}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function BookingWizard() {
  const { sailingId } = useParams();
  const [searchParams] = useSearchParams();
  const cabinFromUrl = searchParams.get('cabin');
  const navigate = useNavigate();

  // One idempotency key is used for this checkout attempt. If the user clicks
  // twice or the network retries, the backend can safely return the same hold.
  const idempotencyKey = useRef(crypto.randomUUID());

  const {
    data: rawData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['availability', sailingId],
    queryFn: async () => (await api.get(`/sailings/${sailingId}/availability`)).data,
  });

  const data = rawData && typeof rawData === 'object' ? rawData : {};
  const decks = useMemo(() => (Array.isArray(data.decks) ? data.decks.map((deck) => ({ ...deck, cabin_types: Array.isArray(deck?.cabin_types) ? deck.cabin_types.map((type) => ({ ...type, cabins: Array.isArray(type?.cabins) ? type.cabins : [] })) : [] })) : []), [data.decks]);

  const [step, setStep] = useState(1);
  const [selected, setSelected] = useState([]);
  const [guests, setGuests] = useState({});
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [booking, setBooking] = useState(null);
  const [clientSecret, setClientSecret] = useState('');
  const [secondsLeft, setSecondsLeft] = useState(null);

  // If CruiseDetail sent a cabin in the URL, preselect it for the traveler.
  useEffect(() => {
    if (!cabinFromUrl || !decks.length) return;

    const cabin = decks
      .flatMap((deck) =>
        deck.cabin_types.flatMap((type) =>
          type.cabins.map((item) => ({
            ...item,
            extra_guest_price_cents: type.price_per_extra_guest_cents || 0,
            cabin_type_name: type.name,
          })),
        ),
      )
      .find((item) => item.cabin_id === cabinFromUrl);

    if (cabin?.status === 'available') {
      setSelected((current) =>
        current.some((item) => item.cabin_id === cabin.cabin_id)
          ? current
          : [{ ...cabin, occupancy: 1 }],
      );
      setStep(1);
    }
  }, [cabinFromUrl, decks]);

  // Keep a partially completed booking in this browser so an accidental
  // refresh does not immediately lose the cabin/guest selections.
  useEffect(() => {
    if (cabinFromUrl) return;

    const saved = sessionStorage.getItem(`booking:${sailingId}`);
    if (!saved) return;

    try {
      const state = JSON.parse(saved);
      setSelected(state.selected || []);
      setGuests(state.guests || {});
      setStep(state.step || 1);
    } catch {
      // Stale session data is ignored safely.
    }
  }, [sailingId, cabinFromUrl]);

  useEffect(() => {
    if (step <= 4) {
      sessionStorage.setItem(
        `booking:${sailingId}`,
        JSON.stringify({ selected, guests, step }),
      );
    }
  }, [sailingId, selected, guests, step]);

  // Countdown starts after the server creates the cabin hold.
  useEffect(() => {
    if (!booking?.hold_expires_at) return undefined;

    const updateCountdown = () => {
      const remaining = Math.max(
        0,
        Math.floor((new Date(booking.hold_expires_at).getTime() - Date.now()) / 1000),
      );
      setSecondsLeft(remaining);
    };

    updateCountdown();
    const timer = setInterval(updateCountdown, 1000);
    return () => clearInterval(timer);
  }, [booking?.hold_expires_at]);

  // Stripe PaymentIntent is created only after the server has successfully
  // held the selected cabins.
  useEffect(() => {
    if (step !== 5 || !booking?.reference || clientSecret) return undefined;

    let cancelled = false;

    api.post('/payments/intent', { booking_reference: booking.reference })
      .then((response) => {
        if (!cancelled) setClientSecret(response.data.client_secret);
      })
      .catch((requestError) => {
        setError(
          requestError.response?.data?.error?.message || 'Unable to start payment.',
        );
      });

    return () => {
      cancelled = true;
    };
  }, [step, booking?.reference, clientSecret]);

  // Payment confirmation is webhook-driven on the backend. Polling only makes
  // the UI notice the confirmed status without forcing the traveler to refresh.
  useEffect(() => {
    if (!booking?.reference || step !== 5) return undefined;

    const startedAt = Date.now();
    const timer = setInterval(async () => {
      if (Date.now() - startedAt >= 90000) {
        clearInterval(timer);
        setError(
          'Payment was submitted, but confirmation is taking longer than expected. Check My Bookings or your email for the final status.',
        );
        return;
      }

      try {
        const response = await api.get(`/bookings/${booking.reference}`);
        const status = response.data.status;

        if (status === 'confirmed') {
          setStep(6);
          clearInterval(timer);
        }

        if (['expired', 'payment_failed'].includes(status)) {
          setError('The payment window has ended. Please select a cabin again.');
          clearInterval(timer);
        }
      } catch {
        // A temporary network error is retried on the next polling cycle.
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [booking?.reference, step]);

  // Convert the nested availability response into one easy-to-use cabin list.
  const cabins = useMemo(
    () => decks.flatMap((deck) =>
      deck.cabin_types.flatMap((type) =>
        type.cabins.map((cabin) => ({
          ...cabin,
          extra_guest_price_cents: type.price_per_extra_guest_cents || 0,
          cabin_type_name: type.name,
        })),
      ),
    ) || [],
    [decks],
  );

  const totalGuests = selected.reduce((sum, cabin) => sum + cabin.occupancy, 0);

  // The estimate uses the same public pricing inputs as the backend. The
  // server still recalculates everything inside the booking transaction.
  const estimatedSubtotal = selected.reduce(
    (sum, cabin) =>
      sum + cabin.price_cents + Math.max(0, cabin.occupancy - 1) * cabin.extra_guest_price_cents,
    0,
  );
  const estimatedPortFees = (data?.port_fee_per_guest_cents || 0) * totalGuests;
  const estimatedTax = Math.round(estimatedSubtotal * (data?.tax_rate || 0));
  const estimatedTotal = estimatedSubtotal + estimatedPortFees + estimatedTax;

  const guestRows = selected.flatMap((cabin) =>
    Array.from({ length: cabin.occupancy }, (_, index) => ({
      cabin_id: cabin.cabin_id,
      key: `${cabin.cabin_id}-${index}`,
    })),
  );

  function toggleCabin(cabin) {
    setSelected((current) => {
      const alreadySelected = current.some((item) => item.cabin_id === cabin.cabin_id);

      if (alreadySelected) {
        return current.filter((item) => item.cabin_id !== cabin.cabin_id);
      }

      return [...current, { ...cabin, occupancy: 1 }];
    });
  }

  function setOccupancy(cabinId, value) {
    setSelected((current) =>
      current.map((cabin) =>
        cabin.cabin_id === cabinId
          ? {
              ...cabin,
              occupancy: Math.max(1, Math.min(cabin.max_occupancy, value || 1)),
            }
          : cabin,
      ),
    );
  }

  function updateGuest(key, field, value) {
    setGuests((current) => ({
      ...current,
      [key]: {
        ...(current[key] || {}),
        [field]: value,
      },
    }));
  }

  async function holdCabins() {
    setBusy(true);
    setError('');

    try {
      const payload = {
        sailing_id: sailingId,
        cabins: selected.map((cabin) => ({
          cabin_id: cabin.cabin_id,
          occupancy: cabin.occupancy,
        })),
        guests: guestRows.map((row, index) => ({
          ...guests[row.key],
          cabin_id: row.cabin_id,
          is_lead_guest: index === 0,
        })),
      };

      const response = await api.post('/bookings/hold', payload, {
        headers: { 'Idempotency-Key': idempotencyKey.current },
      });

      sessionStorage.removeItem(`booking:${sailingId}`);
      setBooking(response.data);
      setStep(5);
    } catch (requestError) {
      // A 409 normally means another traveler changed inventory. Refresh the
      // deck map so the user immediately sees the new availability.
      if (requestError.response?.status === 409) await refetch();

      setError(
        requestError.response?.data?.error?.message ||
          'Unable to hold the selected cabin. Please try again.',
      );
    } finally {
      setBusy(false);
    }
  }

  if (isLoading) {
    return (
      <div className="container-app py-14">
        <Loading />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="container-app py-14">
        <ErrorBox retry={refetch} />
      </div>
    );
  }

  return (
    <div className="container-app py-10 lg:py-14">
      <div className="mb-8">
        <p className="eyebrow">Booking journey</p>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-primary sm:text-4xl">
          Book your cruise cabin
        </h1>
        <p className="muted mt-2">
          Choose a deck and cabin, add guests, review the booking, and complete secure USD payment.
        </p>
      </div>

      <BookingStepper currentStep={step} />

      {error && (
        <div className="mb-6 rounded-xl border border-error bg-error-soft p-4 text-sm text-error">
          {error}
        </div>
      )}

      {/* STEP 1: visual deck/cabin selection */}
      {step === 1 && (
        <section>
          <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="eyebrow">Step 1</p>
              <h2 className="mt-1 text-3xl font-extrabold text-primary">Choose your cabin</h2>
            </div>
            <p className="muted text-sm">
              {data.departure_date} → {data.return_date} · {totalGuests} guest{totalGuests === 1 ? '' : 's'} selected
            </p>
          </div>

          <CabinDeckMap
            decks={decks}
            selectedCabins={selected}
            onToggle={toggleCabin}
            onContinue={() => setStep(2)}
            totalGuests={totalGuests}
            estimatedTotal={estimatedTotal}
          />
        </section>
      )}

      {/* STEP 2: how many guests are staying in each selected cabin */}
      {step === 2 && (
        <section className="max-w-3xl">
          <p className="eyebrow">Step 2</p>
          <h2 className="mt-2 text-3xl font-extrabold text-primary sm:text-4xl">Set occupancy</h2>
          <p className="muted mt-2">Choose how many guests will stay in each selected cabin.</p>

          <div className="mt-8 space-y-3">
            {selected.map((cabin) => (
              <div key={cabin.cabin_id} className="card flex items-center justify-between gap-5 p-5">
                <div>
                  <p className="font-extrabold text-primary">Cabin {cabin.cabin_number}</p>
                  <p className="muted mt-1 text-sm">Maximum {cabin.max_occupancy} guests</p>
                </div>
                <input
                  aria-label={`Guests in cabin ${cabin.cabin_number}`}
                  className="input w-24"
                  type="number"
                  min="1"
                  max={cabin.max_occupancy}
                  value={cabin.occupancy}
                  onChange={(event) => setOccupancy(cabin.cabin_id, Number(event.target.value))}
                />
              </div>
            ))}
          </div>

          <div className="mt-7 flex gap-3">
            <button className="btn btn-outline" onClick={() => setStep(1)}>Back</button>
            <button className="btn btn-primary" onClick={() => setStep(3)}>Continue →</button>
          </div>
        </section>
      )}

      {/* STEP 3: passenger information required by the booking API */}
      {step === 3 && (
        <section>
          <p className="eyebrow">Step 3</p>
          <h2 className="mt-2 text-3xl font-extrabold text-primary sm:text-4xl">Guest details</h2>
          <p className="muted mt-2">Enter the required details for every traveler.</p>

          <div className="mt-8 space-y-4">
            {guestRows.map((row, index) => (
              <div key={row.key} className="card p-6">
                <h3 className="font-extrabold text-primary">
                  Guest {index + 1} · Cabin {cabins.find((cabin) => cabin.cabin_id === row.cabin_id)?.cabin_number}
                </h3>

                <div className="mt-5 grid gap-3 md:grid-cols-2">
                  <label className="block">
                    <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted">Full name *</span>
                    <input className="input" placeholder="Enter full name as in passport" autoComplete="name" value={guests[row.key]?.full_name || ''} onChange={(event) => updateGuest(row.key, 'full_name', event.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted">Date of birth *</span>
                    <input className="input" type="date" value={guests[row.key]?.date_of_birth || ''} onChange={(event) => updateGuest(row.key, 'date_of_birth', event.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted">Gender</span>
                    <input className="input" placeholder="Optional" value={guests[row.key]?.gender || ''} onChange={(event) => updateGuest(row.key, 'gender', event.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted">Nationality *</span>
                    <input className="input" placeholder="e.g. Indian" autoComplete="country-name" value={guests[row.key]?.nationality || ''} onChange={(event) => updateGuest(row.key, 'nationality', event.target.value)} />
                  </label>
                  <label className="block md:col-span-2">
                    <span className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted">Passport / ID number *</span>
                    <input className="input uppercase" placeholder="Enter passport or travel ID number" autoComplete="off" minLength={5} maxLength={30} value={guests[row.key]?.passport_number || ''} onChange={(event) => updateGuest(row.key, 'passport_number', event.target.value.toUpperCase())} />
                  </label>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-7 flex gap-3">
            <button className="btn btn-outline" onClick={() => setStep(2)}>Back</button>
            <button
              className="btn btn-primary"
              onClick={() => {
                const incomplete = guestRows.some((row) => {
                  const guest = guests[row.key] || {};
                  return (
                    !guest.full_name?.trim() ||
                    !guest.date_of_birth ||
                    !guest.nationality?.trim() ||
                    !guest.passport_number?.trim() ||
                    guest.passport_number.trim().length < 5
                  );
                });

                if (incomplete) {
                  setError('Full name, date of birth, nationality and passport / ID number are required for every guest.');
                  return;
                }

                setError('');
                setStep(4);
              }}
            >
              Review →
            </button>
          </div>
        </section>
      )}

      {/* STEP 4: final review before the inventory hold */}
      {step === 4 && (
        <section className="max-w-3xl">
          <p className="eyebrow">Step 4</p>
          <h2 className="mt-2 text-3xl font-extrabold text-primary sm:text-4xl">Review your booking</h2>

          <div className="card mt-8 p-6">
            <div className="flex flex-col justify-between gap-5 sm:flex-row">
              <div>
                <p className="font-extrabold text-primary">Selected cabins</p>
                <p className="muted mt-1 text-sm">{selected.map((cabin) => cabin.cabin_number).join(', ')}</p>
              </div>
              <p className="text-2xl font-extrabold text-primary">{money(estimatedTotal)}</p>
            </div>

            <div className="mt-6 grid gap-3 rounded-2xl bg-surface-muted p-4 text-sm">
              <div className="flex justify-between gap-4"><span className="muted">Cabins + extra guests</span><strong>{money(estimatedSubtotal)}</strong></div>
              <div className="flex justify-between gap-4"><span className="muted">Port fees</span><strong>{money(estimatedPortFees)}</strong></div>
              <div className="flex justify-between gap-4"><span className="muted">Estimated tax</span><strong>{money(estimatedTax)}</strong></div>
              <div className="border-t border-default pt-3 flex justify-between gap-4"><span className="font-extrabold">Estimated total</span><strong>{money(estimatedTotal)}</strong></div>
            </div>

            <p className="muted mt-5 text-sm">
              The server recalculates the final total using live inventory prices, extra-guest pricing, port fees, and tax. The cabin hold lasts 10 minutes.
            </p>

            <label className="mt-6 flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={accepted}
                onChange={(event) => setAccepted(event.target.checked)}
              />
              <span>I agree to the booking terms and the refund/cancellation policy.</span>
            </label>
          </div>

          <div className="mt-7 flex gap-3">
            <button className="btn btn-outline" onClick={() => setStep(3)}>Back</button>
            <button disabled={!accepted || busy} className="btn btn-primary" onClick={holdCabins}>
              {busy ? 'Securing cabin…' : 'Secure cabin & continue →'}
            </button>
          </div>
        </section>
      )}

      {/* STEP 5: Stripe payment */}
      {step === 5 && (
        <section>
          <div className="mb-5 max-w-2xl">
            <p className="eyebrow">Step 5</p>
            <h2 className="mt-2 text-3xl font-extrabold text-primary sm:text-4xl">Pay for your booking</h2>

            {secondsLeft !== null && (
              <div
                className={`mt-4 rounded-xl p-4 text-sm font-bold ${
                  secondsLeft < 120 ? 'bg-error-soft text-error' : 'bg-warning-soft text-warning'
                }`}
                aria-live="polite"
              >
                Cabin hold expires in {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}
              </div>
            )}
          </div>

          {secondsLeft === 0 ? (
            <div className="card max-w-2xl p-7">
              <h3 className="text-xl font-extrabold">Your hold expired</h3>
              <p className="muted mt-2">The cabin has been released. Please choose another available cabin.</p>
              <button className="btn btn-primary mt-5" onClick={() => navigate(`/booking/${sailingId}`)}>
                Choose another cabin
              </button>
            </div>
          ) : clientSecret && stripePromise ? (
            <Elements stripe={stripePromise} options={{ clientSecret }}>
              <PaymentStep onConfirmed={() => { /* webhook polling moves the UI to confirmation */ }} />
            </Elements>
          ) : (
            <div className="card max-w-2xl p-7"><Loading /></div>
          )}
        </section>
      )}

      {/* STEP 6: booking confirmation */}
      {step === 6 && (
        <section className="max-w-2xl">
          <div className="card p-8 text-center sm:p-10">
            <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-accent-soft text-3xl text-accent">✓</div>
            <p className="eyebrow mt-6">Step 6 · Confirmed</p>
            <h2 className="mt-2 text-3xl font-extrabold text-primary sm:text-4xl">Your cruise is confirmed</h2>
            <p className="muted mt-3">Booking reference <strong>{booking?.reference}</strong></p>
            <p className="muted mt-2 text-sm">Your e-ticket will be available from your booking details.</p>

            <div className="mt-7 flex flex-col justify-center gap-3 sm:flex-row">
              <Link to={`/bookings/${booking?.reference}`} className="btn btn-primary">View booking</Link>
              <Link to="/cruises" className="btn btn-outline">Explore more cruises</Link>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
