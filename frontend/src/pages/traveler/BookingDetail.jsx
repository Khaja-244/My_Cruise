import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import { api } from '../../api/client';
import { enablePushAfterBooking } from '../../lib/firebase';
import { Loading, ErrorBox } from '../../components/ui/States';

const stripePromise = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY ? loadStripe(import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY) : null;
const money = (cents) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((cents || 0) / 100);

function PaymentForm({ onDone }) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function pay(event) {
    event.preventDefault();

    if (!stripe || !elements) return;

    setBusy(true);
    setError('');

    // Validate the Payment Element before asking Stripe to confirm payment.
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
      setError(result.error.message || 'Payment failed.');
    } else {
      onDone();
    }

    setBusy(false);
  }

  return (
    <form onSubmit={pay} className="card p-6 sm:p-8 mt-6">
      <p className="eyebrow">Secure payment</p>
      <h2 className="text-2xl font-extrabold text-primary mt-2">Complete payment</h2>

      <div className="mt-6">
        <PaymentElement />
      </div>

      {error && <p className="text-sm text-error mt-4">{error}</p>}

      <button className="btn btn-primary w-full mt-5" disabled={!stripe || busy}>
        {busy ? 'Processing…' : 'Pay securely'}
      </button>
    </form>
  );
}

export default function BookingDetail() {
  const { reference } = useParams(); const qc = useQueryClient();
  const [clientSecret, setClientSecret] = useState(''); const [paymentError, setPaymentError] = useState(''); const [pushPrompt, setPushPrompt] = useState(true);
  const [reason, setReason] = useState(''); const [cancelOpen, setCancelOpen] = useState(false); const [cancelBusy, setCancelBusy] = useState(false); const [cancelMessage, setCancelMessage] = useState('');
  const bookingQuery = useQuery({ queryKey: ['booking', reference], queryFn: async () => (await api.get(`/bookings/${reference}`)).data, refetchInterval: (q) => q.state.data?.status === 'pending_payment' ? 2000 : false });
  const { data, isLoading, isError, refetch } = bookingQuery;

  useEffect(() => { if (data?.status !== 'pending_payment' || clientSecret) return; api.post('/payments/intent', { booking_reference: reference }).then(r => setClientSecret(r.data.client_secret)).catch(e => setPaymentError(e.response?.data?.error?.message || 'Unable to start payment.')); }, [data?.status, reference, clientSecret]);
  const [ticketError, setTicketError] = useState('');
  const [ticketBusy, setTicketBusy] = useState(false);

  async function fetchTicketPdf() {
    const response = await api.get(`/bookings/${reference}/ticket`, { responseType: 'blob' });
    const contentType = response.headers?.['content-type'] || '';
    if (!contentType.includes('application/pdf')) {
      throw new Error('The server did not return a valid PDF ticket.');
    }
    return new Blob([response.data], { type: 'application/pdf' });
  }

  const openTicket = async () => {
    setTicketError('');
    setTicketBusy(true);

    // Create the tab synchronously from the button click. Waiting until after
    // the API request can make Chrome block the new tab as a popup.
    const ticketTab = window.open('', '_blank');

    try {
      const pdfBlob = await fetchTicketPdf();
      const url = URL.createObjectURL(pdfBlob);

      if (ticketTab && !ticketTab.closed) {
        ticketTab.location.replace(url);
        ticketTab.focus();
      } else {
        // Popup blocking fallback: use a normal link so the user can still
        // open the PDF in a new browser tab.
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.click();
      }

      // Keep the object URL alive long enough for Chrome's PDF viewer to load.
      setTimeout(() => URL.revokeObjectURL(url), 10 * 60 * 1000);
    } catch (e) {
      if (ticketTab && !ticketTab.closed) ticketTab.close();
      setTicketError(e.response?.data?.error?.message || e.message || 'Unable to open the e-ticket right now.');
    } finally {
      setTicketBusy(false);
    }
  };

  const downloadTicket = async () => {
    setTicketError('');
    setTicketBusy(true);
    try {
      const pdfBlob = await fetchTicketPdf();
      const url = URL.createObjectURL(pdfBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `my_cruise-${reference}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60 * 1000);
    } catch (e) {
      setTicketError(e.response?.data?.error?.message || e.message || 'Unable to download the e-ticket right now.');
    } finally {
      setTicketBusy(false);
    }
  };
  const preview = useQuery({ queryKey: ['refund-preview', reference], queryFn: async () => (await api.get(`/bookings/${reference}/refund-preview`)).data, enabled: cancelOpen && data?.status === 'confirmed' });
  const submitCancel = async () => { if (!reason.trim()) return; setCancelBusy(true); setCancelMessage(''); try { await api.post(`/bookings/${reference}/cancel-request`, { reason }); setCancelMessage('Cancellation request submitted. An admin will review it.'); qc.invalidateQueries({ queryKey: ['booking', reference] }); } catch (e) { setCancelMessage(e.response?.data?.error?.message || 'Unable to submit cancellation request.'); } finally { setCancelBusy(false); } };

  if (isLoading) return <div className="container-app py-14"><Loading /></div>;
  if (isError || !data) return <div className="container-app py-14"><ErrorBox retry={refetch} /></div>;
  return <div className="container-app max-w-4xl py-10 lg:py-14"><div className="mb-7"><p className="eyebrow">Booking details</p><h1 className="text-3xl sm:text-4xl font-extrabold text-primary mt-2">Your cruise reservation</h1><p className="muted mt-2">Review your sailing, cabins, payment and cancellation information.</p></div><Link to="/bookings" className="text-sm font-bold text-accent">← My bookings</Link><div className="card p-7 sm:p-9 mt-6"><div className="flex flex-col sm:flex-row justify-between gap-4"><div><p className="eyebrow">Booking reference</p><h1 className="text-3xl sm:text-4xl font-extrabold text-primary mt-2">{reference}</h1></div><span className="self-start rounded-full bg-accent-soft text-accent px-3 py-1.5 text-xs font-bold capitalize">{data.status.replaceAll('_',' ')}</span></div><div className="grid sm:grid-cols-3 gap-4 mt-8"><div className="rounded-xl bg-surface-muted p-4"><p className="text-xs muted">Guests</p><p className="font-extrabold mt-1">{data.guest_count}</p></div><div className="rounded-xl bg-surface-muted p-4"><p className="text-xs muted">Total</p><p className="font-extrabold mt-1">{money(data.total_cents)}</p></div><div className="rounded-xl bg-surface-muted p-4"><p className="text-xs muted">Currency</p><p className="font-extrabold mt-1">{data.currency}</p></div></div>{data.cabins?.length>0&&<div className="mt-8"><h2 className="font-extrabold text-lg">Cabins</h2><div className="mt-3 space-y-2">{data.cabins.map(c=><div key={c.cabin_id} className="flex justify-between rounded-xl border border-default p-4 text-sm"><span>Cabin {c.cabin_number || c.cabin_id}</span><span>{c.occupancy} guests · {money(c.price_cents)}</span></div>)}</div></div>}
  {data.status==='confirmed'&&pushPrompt&&<div className="mt-7 p-4 rounded-xl bg-surface-muted border"><b>Get booking updates?</b><p className="text-sm muted mt-1">Enable browser notifications for booking and refund updates.</p><button className="btn btn-primary mt-3 mr-2" onClick={async()=>{await enablePushAfterBooking().catch(()=>{});setPushPrompt(false)}}>Enable notifications</button><button className="btn btn-outline mt-3" onClick={()=>setPushPrompt(false)}>Not now</button></div>}
  {['confirmed','refunded','partially_refunded'].includes(data.status)&&<div className="flex flex-wrap gap-3 mt-7"><><button className="btn btn-primary" onClick={openTicket} disabled={ticketBusy}>{ticketBusy ? 'Opening…' : 'View e-ticket'}</button><button className="btn btn-outline" onClick={downloadTicket} disabled={ticketBusy}>Download PDF</button></>{data.status==='confirmed'&&<button className="btn btn-outline" onClick={()=>setCancelOpen(v=>!v)}>Request cancellation</button>}</div>}
  {cancelOpen&&data.status==='confirmed'&&<div className="mt-6 rounded-2xl border border-warning bg-warning-soft/50 p-5"><h2 className="font-extrabold text-primary">Cancellation preview</h2>{preview.isLoading?<p className="text-sm muted mt-3">Calculating your refund…</p>:preview.isError?<p className="text-sm text-warning mt-3">{preview.error?.response?.data?.error?.message||"We couldn't calculate an estimated refund right now. You can still submit your cancellation request below — an admin will review it manually."}</p>:preview.data&&<p className="text-sm text-secondary mt-3">Estimated refund: <strong>{money(preview.data.refund_cents)}</strong> ({preview.data.refund_percent}% minus {money(preview.data.flat_fee_cents)} fee), based on {preview.data.days_before_departure} days before departure.</p>}<textarea className="input mt-4 min-h-24" placeholder="Why are you cancelling?" value={reason} onChange={e=>setReason(e.target.value)} />{cancelMessage&&<p className="text-sm mt-3 text-secondary">{cancelMessage}</p>}<button disabled={cancelBusy||!reason.trim()} className="btn btn-primary mt-4" onClick={submitCancel}>{cancelBusy?'Submitting…':'Submit cancellation request'}</button><p className="text-xs muted mt-3">Phase 1 cancellation applies to the whole booking; individual cabin cancellation is not supported.</p></div>}
  {ticketError&&<p className="text-error mt-3 text-sm">{ticketError}</p>}
  {paymentError&&<div className="mt-5 rounded-xl border border-warning bg-warning-soft p-4 text-sm text-warning"><b>Payment could not start.</b><p className="mt-1">{paymentError}</p><Link className="inline-block mt-3 font-bold text-accent" to="/bookings">Back to bookings</Link></div>}</div>{data.status==='pending_payment'&&!stripePromise&&!paymentError&&<div className="mt-6 rounded-xl border border-warning bg-warning-soft p-4 text-sm text-warning"><b>Secure payment is temporarily unavailable.</b><p className="mt-1">Stripe checkout is not configured in this environment. Your cabin hold remains subject to its expiry time.</p></div>}{clientSecret&&stripePromise&&data.status==='pending_payment'&&<Elements stripe={stripePromise} options={{clientSecret}}><PaymentForm onDone={()=>qc.invalidateQueries({queryKey:['booking',reference]})}/></Elements>}{data.status==='pending_payment'&&data.hold_expires_at&&<p className="mt-4 text-sm text-warning">Hold expires at {new Date(data.hold_expires_at).toLocaleString()}.</p>}</div>;
}
