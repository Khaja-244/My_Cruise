import { Link, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/client';
import { Loading, ErrorBox, EmptyState } from '../../components/ui/States';
import { cruiseImages, getCabinImage, getCruiseImage } from '../../lib/images';

const money = (cents) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((Number(cents) || 0) / 100);
const asArray = (value) => (Array.isArray(value) ? value : []);
const asObject = (value) => (value && typeof value === 'object' ? value : {});

function InfoCard({ label, value }) {
  return (
    <div className="rounded-xl bg-surface-muted border border-default p-4">
      <p className="text-xs uppercase tracking-wide font-bold text-muted">{label}</p>
      <p className="font-extrabold text-primary mt-1">{value || '—'}</p>
    </div>
  );
}

function CabinStatus({ status }) {
  const normalized = status === 'unavailable' ? 'held' : status;
  const tone = normalized === 'available' ? 'status-available' : normalized === 'booked' ? 'status-booked' : normalized === 'blocked' ? 'status-blocked' : 'status-held';
  return <span className={`status-pill ${tone}`}>{normalized === 'held' ? 'Held' : String(normalized || 'Unavailable').replaceAll('_', ' ')}</span>;
}

function normalizeDecks(value) {
  return asArray(value).map((deck) => ({
    ...asObject(deck),
    deck_id: deck?.deck_id || deck?.id || `deck-${deck?.deck_number ?? 'unknown'}`,
    cabin_types: asArray(deck?.cabin_types).map((type) => ({
      ...asObject(type),
      cabin_type_id: type?.cabin_type_id || type?.id || `type-${type?.name || 'unknown'}`,
      cabins: asArray(type?.cabins),
    })),
  }));
}

export default function CruiseDetail() {
  const { slug } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [savedId, setSavedId] = useState(null);
  const [saveBusy, setSaveBusy] = useState(false);
  const [selectedSailing, setSelectedSailing] = useState('');
  const [openDecks, setOpenDecks] = useState({});

  const cruise = useQuery({ queryKey: ['cruise', slug], queryFn: async () => (await api.get(`/cruises/${slug}`)).data });
  const sailings = useQuery({ queryKey: ['sailings', slug], queryFn: async () => (await api.get(`/cruises/${slug}/sailings`)).data, enabled: !!cruise.data });
  const availability = useQuery({ queryKey: ['availability', selectedSailing], queryFn: async () => (await api.get(`/sailings/${selectedSailing}/availability`)).data, enabled: !!selectedSailing });
  const savedQuery = useQuery({ queryKey: ['saved'], queryFn: async () => (await api.get('/saved-cruises')).data, enabled: !!user });

  const data = asObject(cruise.data);
  const cabinTypes = asArray(data.cabin_types);
  const itinerary = asArray(data.itinerary);
  const sailingItems = asArray(sailings.data);
  const availabilityData = asObject(availability.data);
  const decks = normalizeDecks(availabilityData.decks);

  useEffect(() => {
    const items = asArray(savedQuery.data?.items);
    const item = items.find((x) => x?.cruise_id === cruise.data?.id);
    setSavedId(item?.id || null);
  }, [savedQuery.data, cruise.data?.id]);

  useEffect(() => {
    if (!selectedSailing || decks.length === 0) return;
    const firstDeck = decks[0];
    setOpenDecks({ [firstDeck.deck_id]: true });
  }, [selectedSailing, availability.data]);

  const saveCruise = async () => {
    if (!user) {
      window.location.assign(`/login?from=${encodeURIComponent(window.location.pathname)}`);
      return;
    }
    setSaveBusy(true);
    try {
      if (savedId) {
        await api.delete(`/saved-cruises/${savedId}`);
        setSavedId(null);
      } else {
        const response = await api.post('/saved-cruises', { cruise_id: data.id });
        setSavedId(response.data?.id || null);
      }
      qc.invalidateQueries({ queryKey: ['saved'] });
    } finally {
      setSaveBusy(false);
    }
  };



  if (cruise.isLoading) return <div className="container-app py-16"><Loading label="Loading cruise details…" /></div>;
  if (cruise.isError || !cruise.data) return <div className="container-app py-16"><ErrorBox retry={cruise.refetch} /></div>;

  const gallery = [
    { url: getCruiseImage(data), alt_text: `${data.name || 'Cruise'} cruise ship` },
    { url: cruiseImages.cabin, alt_text: 'Cruise cabin interior' },
    { url: cruiseImages.oceanView, alt_text: 'Ocean view cabin' },
    { url: cruiseImages.balcony, alt_text: 'Cruise balcony cabin' },
  ];

  return (
    <div>
      <section className="cruise-detail-hero relative overflow-hidden bg-navy-900 text-inverse">
        <img src={getCruiseImage(data)} alt={`${data.name || 'Cruise'} cruise ship`} className="absolute inset-0 h-full w-full object-cover opacity-55 hero-photo" onError={(event) => { event.currentTarget.src = cruiseImages.hero; }} />
        <div className="absolute inset-0 bg-gradient-to-r from-navy-950/92 via-navy-950/72 to-navy-950/28" />
        <div className="absolute inset-0 bg-gradient-to-t from-navy-950/80 via-transparent to-navy-950/10" />
        <div className="container-app relative py-14 lg:py-20">
          <Link to="/cruises" className="text-sm text-inverse-muted hover:text-inverse">← Back to cruises</Link>
          <div className="grid lg:grid-cols-[1fr_380px] gap-10 items-end mt-10">
            <div>
              <span className="eyebrow text-inverse-muted">Cruise collection</span>
              <h1 className="page-heading text-4xl sm:text-6xl font-extrabold tracking-[-.05em] mt-3">{data.name || 'Cruise journey'}</h1>
              <p className="text-inverse-muted text-lg leading-7 max-w-3xl mt-5">{data.description || 'Plan your journey with live sailing dates, cabin availability and transparent USD pricing.'}</p>
              <div className="flex flex-wrap gap-2 mt-6"><span className="tag bg-surface/10 border-white/20 text-inverse">Live inventory</span><span className="tag bg-surface/10 border-white/20 text-inverse">USD pricing</span><span className="tag bg-surface/10 border-white/20 text-inverse">Secure booking</span></div>
            </div>
            <div className="premium-panel rounded-2xl p-5">
              <p className="text-xs uppercase tracking-wider text-inverse-muted font-bold">Route</p>
              <p className="text-lg font-extrabold mt-2">{data.embark_port?.name || 'Embarkation'} → {data.disembark_port?.name || 'Disembarkation'}</p>
              <p className="text-sm text-inverse-muted mt-2">{data.ship?.name || 'Ship'} · {data.sailing_days || '—'} sailing days</p>
            </div>
          </div>
        </div>
      </section>

      <section className="container-app pt-8"><div className="grid grid-cols-2 md:grid-cols-4 gap-3"><InfoCard label="Ship" value={data.ship?.name} /><InfoCard label="Departure port" value={data.embark_port?.city ? `${data.embark_port.name}, ${data.embark_port.city}` : data.embark_port?.name} /><InfoCard label="Return port" value={data.disembark_port?.city ? `${data.disembark_port.name}, ${data.disembark_port.city}` : data.disembark_port?.name} /><InfoCard label="Duration" value={data.sailing_days ? `${data.sailing_days} days` : '—'} /></div></section>

      <section className="container-app pt-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {gallery.map((image, index) => (
            <div key={`${image.url}-${index}`} className={`premium-image-frame ${index === 0 ? 'col-span-2 row-span-2 h-[360px]' : 'h-[175px]'}`}>
              <img src={image.url} alt={image.alt_text} className="premium-image" loading={index === 0 ? 'eager' : 'lazy'} onError={(event) => { event.currentTarget.src = cruiseImages.hero; }} />
            </div>
          ))}
        </div>
      </section>

      <section className="container-app py-12 lg:py-16"><div className="grid lg:grid-cols-[1.08fr_.92fr] gap-8">
        <div>
          <div className="card p-7">
            <div className="flex flex-wrap justify-between gap-5 items-end"><div><p className="eyebrow">Cabin options</p><h2 className="section-title mt-2">Choose how you want to stay</h2></div><button disabled={saveBusy} onClick={saveCruise} className="btn btn-outline text-sm">{savedId ? '♥ Saved' : '♡ Save cruise'}</button></div>
            <div className="grid sm:grid-cols-2 gap-4 mt-7">
              {cabinTypes.map((x, index) => <div className="overflow-hidden rounded-2xl border border-default bg-surface shadow-sm" key={x.id || `${x.name}-${index}`}>
                <div className="relative h-40 bg-slate-900">
                  <img src={getCabinImage(x.name)} alt={`${x.name || 'Cruise'} cabin`} className="absolute inset-0 w-full h-full object-cover" loading="lazy" onError={(event) => { event.currentTarget.src = cruiseImages.cabin; }} />
                  <div className="absolute inset-0 bg-gradient-to-t from-navy-900/80 to-transparent" />
                  <div className="absolute left-4 right-4 bottom-3 flex justify-between gap-3 items-end"><h3 className="font-extrabold text-inverse text-lg">{x.name || 'Cabin'}</h3><span className="text-inverse font-extrabold">{money(x.base_price_cents)}</span></div>
                </div>
                <div className="p-5"><p className="muted text-sm leading-6">{x.description || 'A comfortable cabin designed for a relaxing journey.'}</p><p className="text-xs font-bold text-muted mt-4">Up to {x.max_occupancy || '—'} guests · extra guest {money(x.price_per_extra_guest_cents)}</p>{asArray(x.amenities).length > 0 && <div className="flex flex-wrap gap-2 mt-4">{asArray(x.amenities).map((a, amenityIndex) => <span key={a?.name || amenityIndex} className="tag">{a?.name || 'Amenity'}</span>)}</div>}</div>
              </div>)}
              {cabinTypes.length === 0 && <EmptyState title="Cabin information unavailable" description="Please try again later." />}
            </div>
          </div>

          <div className="card p-7 mt-6"><p className="eyebrow">Journey map</p><h2 className="section-title mt-2">Itinerary</h2><div className="mt-7">{itinerary.map((item, index) => <div className="flex gap-4" key={`${item?.day_number ?? 'day'}-${index}`}><div className="flex flex-col items-center"><span className="h-9 w-9 rounded-full bg-accent-soft text-accent grid place-items-center text-xs font-extrabold">{item?.day_number ?? index + 1}</span>{index < itinerary.length - 1 && <span className="w-px bg-surface-subtle flex-1 my-1" />}</div><div className="pb-7"><p className="font-extrabold text-primary">{item?.port?.name || 'At sea'}</p><p className="text-sm muted mt-1">{item?.port?.city ? `${item.port.city} · ` : ''}{item?.description || 'Enjoy your day aboard.'}</p>{(item?.arrival_time || item?.departure_time) && <p className="text-xs text-muted mt-2">{item?.arrival_time || '—'} arrival · {item?.departure_time || '—'} departure</p>}</div></div>)}{itinerary.length === 0 && <p className="muted text-sm">Itinerary details will be published soon.</p>}</div></div>
        </div>

        <aside><div className="card p-7 sticky top-24"><div className="flex justify-between items-start gap-3"><div><p className="eyebrow">Live availability</p><h2 className="section-title text-2xl mt-2">Choose a sailing</h2></div><span className="tag">USD</span></div>
          <div className="space-y-3 mt-6">
            {sailings.isLoading && <Loading label="Loading sailings" />}
            {sailings.isError && <ErrorBox retry={sailings.refetch} />}
            {sailingItems.map((sailing, sailingIndex) => <div key={sailing?.id || sailingIndex} className={`rounded-2xl border p-4 transition ${selectedSailing === sailing?.id ? 'border-accent bg-accent-soft/40 shadow-sm' : 'border-default bg-surface'}`}>
              <button className="w-full text-left" onClick={() => sailing?.id && setSelectedSailing(sailing.id)} aria-expanded={selectedSailing === sailing?.id} disabled={!sailing?.id}><div className="flex justify-between gap-3"><div><p className="font-extrabold text-primary">{sailing?.departure_date || '—'} → {sailing?.return_date || '—'}</p><p className="text-xs muted mt-1">{sailing?.cabins_left ?? 0} cabins available</p></div><p className="font-extrabold text-primary">{money(sailing?.from_price_cents)}</p></div></button>
              {selectedSailing === sailing?.id && <div className="mt-5 pt-5 border-t border-default"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-muted">Cabin availability</p><p className="text-xs muted mt-1">Choose an available room below; held or booked rooms cannot be selected.</p></div>{availabilityData.summary && <div className="flex gap-2 text-xs"><span className="tag tag-active">{availabilityData.summary.available ?? 0} available</span><span className="tag">{availabilityData.summary.booked ?? 0} booked</span></div>}</div>
                {availability.isLoading ? <p className="text-sm muted mt-4">Checking live cabin inventory…</p> : availability.isError ? <ErrorBox retry={availability.refetch} /> : decks.length === 0 ? <p className="text-sm muted mt-4">No cabin inventory is currently published for this sailing.</p> : <div className="space-y-3 mt-4">{decks.map((deck, deckIndex) => {
                  const cabinTypesInDeck = asArray(deck.cabin_types);
                  const cabins = cabinTypesInDeck.flatMap((type) => asArray(type.cabins).map((cabin) => ({ ...cabin, cabin_type_name: type.name, extra_guest_price_cents: type.price_per_extra_guest_cents || 0 })));
                  const available = cabins.filter((cabin) => cabin.status === 'available').length;
                  const deckKey = deck.deck_id || `deck-${deckIndex}`;
                  const open = !!openDecks[deckKey];
                  return <div key={deckKey} className="rounded-xl border border-default overflow-hidden"><button type="button" className="w-full flex items-center justify-between gap-4 p-4 text-left hover:bg-surface-muted" onClick={() => setOpenDecks((current) => ({ ...current, [deckKey]: !current[deckKey] }))} aria-expanded={open}><span><b className="text-primary">{deck.name || `Deck ${deck.deck_number ?? deckIndex + 1}`}</b><span className="block text-xs muted mt-1">{cabins.length} cabins · {available} available</span></span><span className="flex items-center gap-2"><span className="tag tag-active">{available} available</span><span className="text-muted text-lg">{open ? '−' : '+'}</span></span></button>{open && <div className="p-3 bg-surface-muted border-t border-default space-y-2">{cabinTypesInDeck.map((type, typeIndex) => <div key={type.cabin_type_id || `${type.name}-${typeIndex}`}><div className="flex justify-between items-center gap-3 px-2 py-1"><p className="text-xs uppercase tracking-wide font-extrabold text-muted">{type.name || 'Cabin'}</p><span className="text-xs muted">Up to {type.max_occupancy ?? '—'} guests</span></div><div className="grid grid-cols-1 sm:grid-cols-2 gap-2">{asArray(type.cabins).map((cabin, cabinIndex) => { const selectable = cabin?.status === 'available'; return <div key={cabin?.cabin_id || cabinIndex} className={`cabin-card p-3 flex items-center justify-between gap-3 ${!selectable ? 'disabled' : ''}`}><div><p className="font-extrabold text-primary">Cabin {cabin?.cabin_number || '—'}</p><p className="text-xs muted mt-1">{money(cabin?.price_cents)} · max {cabin?.max_occupancy ?? '—'}</p></div><div className="text-right"><CabinStatus status={cabin?.status}/>{selectable && <Link to={`/booking/${sailing.id}?cabin=${encodeURIComponent(cabin.cabin_id)}`} className="cabin-select-link">Select</Link>}</div></div>; })}</div></div>)}</div>}</div>;
                })}</div>}
              </div>}
            </div>)}
            {!sailings.isLoading && !sailings.isError && sailingItems.length === 0 && <EmptyState title="No open sailings" description="Published sailings will appear here when they are available." />}
          </div>
        </div></aside>
      </div></section>
    </div>
  );
}
