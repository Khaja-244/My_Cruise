import PageHero from '../../components/ui/PageHero';
import {Link, useParams} from 'react-router-dom';
import {useQuery} from '@tanstack/react-query';
import {api} from '../../api/client';
import {Loading, ErrorBox} from '../../components/ui/States';

const money = (cents, currency = 'USD') =>
  new Intl.NumberFormat('en-US', {style: 'currency', currency}).format((cents || 0) / 100);

const dateText = value => value ? new Date(value).toLocaleDateString() : '—';

function Badge({children}) {
  return <span className="inline-flex rounded-full bg-surface-muted px-3 py-1 text-xs font-bold capitalize text-secondary">{String(children || '—').replaceAll('_', ' ')}</span>;
}

function Card({title, children}) {
  return <section className="card p-6">
    <h2 className="text-lg font-extrabold text-primary">{title}</h2>
    <div className="mt-4">{children}</div>
  </section>;
}

function Field({label, value}) {
  return <div>
    <p className="text-xs font-bold uppercase tracking-wide text-muted">{label}</p>
    <p className="mt-1 text-sm font-semibold text-primary break-words">{value ?? '—'}</p>
  </div>;
}

export default function AdminBookingDetail() {
  const {reference} = useParams();
  const query = useQuery({
    queryKey: ['admin-booking', reference],
    queryFn: async () => (await api.get(`/admin/bookings/${reference}`)).data,
    enabled: !!reference,
  });

  if (query.isLoading) return <div className="container-app py-12"><Loading /></div>;
  if (query.isError) return <div className="container-app py-12"><ErrorBox retry={query.refetch} /></div>;

  const booking = query.data;

  return <div><PageHero eyebrow="Booking operations" title={`Booking ${reference}`} subtitle="Review traveler, sailing, cabin, payment and cancellation information." /><div className="container-app py-10 lg:py-14 space-y-6">
    <div>
      <Link to="/admin/bookings" className="text-sm font-bold text-accent">← Back to bookings</Link>
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Booking operations</p>
          <h1 className="mt-2 text-4xl font-extrabold tracking-tight text-primary">{booking.reference}</h1>
          <p className="muted mt-2">Complete traveler, inventory, payment and cancellation history.</p>
        </div>
        <div className="flex gap-2">
          <Badge>{booking.channel}</Badge>
          <Badge>{booking.status}</Badge>
        </div>
      </div>
    </div>

    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Traveler">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" value={booking.traveler?.full_name} />
          <Field label="Email" value={booking.traveler?.email} />
          <Field label="Phone" value={booking.traveler?.phone} />
          <Field label="Guest count" value={booking.guest_count} />
        </div>
      </Card>

      <Card title="Partner">
        {booking.partner ? <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Agency" value={booking.partner.business_name} />
          <Field label="Email" value={booking.partner.email} />
          <Field label="Partner ID" value={booking.partner.id} />
        </div> : <p className="muted text-sm">Direct my_cruise booking — no partner involved.</p>}
      </Card>

      <Card title="Cruise & sailing">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Cruise" value={booking.cruise?.name} />
          <Field label="Sailing ID" value={booking.sailing?.id} />
          <Field label="Departure" value={dateText(booking.sailing?.departure_date)} />
          <Field label="Return" value={dateText(booking.sailing?.return_date)} />
        </div>
      </Card>

      <Card title="Financial summary">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Subtotal" value={money(booking.subtotal_cents, booking.currency)} />
          <Field label="Tax" value={money(booking.tax_cents, booking.currency)} />
          <Field label="Total" value={money(booking.total_cents, booking.currency)} />
          <Field label="Commission" value={money(booking.commission_cents, booking.currency)} />
          <Field label="Currency" value={booking.currency} />
        </div>
      </Card>
    </div>

    <Card title="Cabins booked">
      {booking.cabins?.length ? <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b bg-surface-muted"><tr>
            <th className="px-4 py-3 text-left">Cabin</th>
            <th className="px-4 py-3 text-left">Occupancy</th>
            <th className="px-4 py-3 text-left">Price</th>
          </tr></thead>
          <tbody className="divide-y">{booking.cabins.map(cabin => <tr key={cabin.cabin_id}>
            <td className="px-4 py-3 font-bold">{cabin.cabin_number}</td>
            <td className="px-4 py-3">{cabin.occupancy}</td>
            <td className="px-4 py-3">{money(cabin.price_cents, booking.currency)}</td>
          </tr>)}</tbody>
        </table>
      </div> : <p className="muted text-sm">No cabin records found.</p>}
    </Card>

    <Card title="Guest list">
      {booking.guests?.length ? <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b bg-surface-muted"><tr>
            <th className="px-4 py-3 text-left">Guest</th>
            <th className="px-4 py-3 text-left">Date of birth</th>
            <th className="px-4 py-3 text-left">Nationality</th>
            <th className="px-4 py-3 text-left">Cabin</th>
            <th className="px-4 py-3 text-left">Lead</th>
          </tr></thead>
          <tbody className="divide-y">{booking.guests.map((guest, index) => <tr key={`${guest.full_name}-${index}`}>
            <td className="px-4 py-3 font-semibold">{guest.full_name}</td>
            <td className="px-4 py-3">{dateText(guest.date_of_birth)}</td>
            <td className="px-4 py-3">{guest.nationality || '—'}</td>
            <td className="px-4 py-3">{guest.cabin_number || guest.cabin_id || '—'}</td>
            <td className="px-4 py-3">{guest.is_lead_guest ? 'Yes' : 'No'}</td>
          </tr>)}</tbody>
        </table>
      </div> : <p className="muted text-sm">No guest records found.</p>}
    </Card>

    <Card title="Payment records">
      {booking.payments?.length ? <div className="space-y-3">{booking.payments.map(payment => <div key={payment.id} className="rounded-xl border border-default p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="font-bold">{money(payment.amount_cents, payment.currency)}</div>
          <Badge>{payment.status}</Badge>
        </div>
        <div className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
          <Field label="Payment record" value={payment.id} />
          <Field label="Stripe PaymentIntent" value={payment.stripe_payment_intent_id} />
          <Field label="Stripe charge" value={payment.stripe_charge_id} />
          <Field label="Currency" value={payment.currency} />
        </div>
      </div>)}</div> : <p className="muted text-sm">No payment records found.</p>}
    </Card>

    <Card title="Cancellation & refund history">
      {booking.cancellations?.length ? <div className="space-y-3">{booking.cancellations.map(item => <div key={item.id} className="rounded-xl border border-default p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-bold">{item.reason || 'Cancellation request'}</p>
          <Badge>{item.status}</Badge>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Field label="Calculated refund" value={money(item.calculated_refund_cents, booking.currency)} />
          <Field label="Final refund" value={money(item.final_refund_cents, booking.currency)} />
          <Field label="Admin note" value={item.admin_note || '—'} />
        </div>
      </div>)}</div> : <p className="muted text-sm">No cancellation requests recorded.</p>}
      {booking.refunds?.length ? <div className="mt-6 space-y-3">{booking.refunds.map(item => <div key={item.id} className="rounded-xl border border-brand-100 bg-accent-soft/40 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-bold">Stripe refund</p>
          <Badge>{item.status}</Badge>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Amount" value={money(item.amount_cents, booking.currency)} />
          <Field label="Stripe refund ID" value={item.stripe_refund_id || '—'} />
          <Field label="Payment ID" value={item.payment_id} />
          <Field label="Failure reason" value={item.failure_reason || '—'} />
        </div>
      </div>)}</div> : null}
    </Card>
  </div></div>;
}
