import { useMemo, useState } from 'react';

// The API already tells us which cabins are available, held, or booked.
// This component only turns that data into a visual deck plan.
const TYPE_STYLES = {
  suite: { className: 'cabin-type-suite', label: 'Suite' },
  balcony: { className: 'cabin-type-balcony', label: 'Balcony' },
  'ocean view': { className: 'cabin-type-ocean', label: 'Ocean View' },
  interior: { className: 'cabin-type-interior', label: 'Interior' },
};

function getTypeKey(name = '') {
  return name.trim().toLowerCase();
}

function getTypeStyle(name) {
  return TYPE_STYLES[getTypeKey(name)] || TYPE_STYLES.interior;
}

function sortCabins(a, b) {
  return String(a.cabin_number).localeCompare(String(b.cabin_number), undefined, {
    numeric: true,
  });
}

function formatMoney(cents) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format((cents || 0) / 100);
}

function statusText(status) {
  return status === 'unavailable'
    ? 'Held'
    : String(status || 'unavailable').replaceAll('_', ' ');
}

/**
 * A single cabin selection button.
 * Keeping this small makes the main deck layout easier to understand.
 */
// A cabin represents a passenger room/accommodation on the ship.
function CabinRoom({ cabin, selected, onSelect }) {
  const style = getTypeStyle(cabin.cabin_type_name);
  const available = cabin.status === 'available';

  return (
    <button
      type="button"
      disabled={!available}
      onClick={() => onSelect(cabin)}
      title={`${cabin.cabin_number} · ${cabin.cabin_type_name} · ${formatMoney(cabin.price_cents)}`}
      aria-label={`Cabin ${cabin.cabin_number}, ${cabin.cabin_type_name}, ${statusText(cabin.status)}`}
      className={[
        'cabin-room group relative flex w-full flex-col items-center justify-center rounded-xl px-2 py-2 text-center transition-all duration-150',
        style.className,
        selected ? 'selected' : '',
        !available ? 'booked cursor-not-allowed opacity-70' : 'cursor-pointer',
      ].join(' ')}
    >
      <span className="text-xs font-extrabold leading-tight sm:text-sm">
        {cabin.cabin_number}
      </span>
      <span className="mt-1 text-[8px] font-bold uppercase tracking-[0.08em] opacity-70 sm:text-[9px]">
        {cabin.cabin_type_name || 'Cabin'}
      </span>
      <span
        className={`cabin-state-pill mt-1 ${
          selected ? 'cabin-state-selected' : available ? 'cabin-state-available' : 'cabin-state-unavailable'
        }`}
      >
        {selected ? 'Selected' : available ? 'Select' : statusText(cabin.status)}
      </span>
    </button>
  );
}

/**
 * Visual deck plan for cruise-ship cabin rooms and their live availability.
 *
 * It does NOT create a new inventory system. Every click still uses the same
 * cabin ID that the existing booking API expects, so the backend remains the
 * source of truth and double-booking protection is unchanged.
 */
export default function CabinDeckMap({
  decks: rawDecks,
  selectedCabins,
  onToggle,
  onContinue,
  totalGuests,
  estimatedTotal,
}) {
  const decks = Array.isArray(rawDecks) ? rawDecks.map((deck) => ({ ...deck, cabin_types: Array.isArray(deck?.cabin_types) ? deck.cabin_types.map((type) => ({ ...type, cabins: Array.isArray(type?.cabins) ? type.cabins : [] })) : [] })) : [];

  const [activeDeckId, setActiveDeckId] = useState(decks[0]?.deck_id || '');

  const activeDeck = decks.find((deck) => deck.deck_id === activeDeckId) || decks[0];

  const cabins = useMemo(() => {
    if (!activeDeck) return [];

    // Add the cabin type name to every cabin so the map can colour-code it.
    return activeDeck.cabin_types
      .flatMap((type) =>
        type.cabins.map((cabin) => ({
          ...cabin,
          cabin_type_name: type.name,
          extra_guest_price_cents: type.price_per_extra_guest_cents || 0,
        })),
      )
      .sort(sortCabins);
  }, [activeDeck]);

  // Four cabins make one visual row: two on the left side and two on the right.
  // If a deck has fewer cabins, the empty positions simply remain blank.
  const rows = useMemo(() => {
    const result = [];
    for (let index = 0; index < cabins.length; index += 4) {
      result.push(cabins.slice(index, index + 4));
    }
    return result;
  }, [cabins]);

  const selectedIds = new Set(selectedCabins.map((cabin) => cabin.cabin_id));
  const availableCount = activeDeck?.cabin_types.reduce(
    (total, type) => total + type.cabins.filter((cabin) => cabin.status === 'available').length,
    0,
  ) || 0;

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_330px]">
      <section className="card overflow-hidden p-4 sm:p-6">
        <div className="flex flex-col gap-4 border-b border-default pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="eyebrow">Step 1 · Deck plan</p>
            <h2 className="mt-1 text-2xl font-extrabold text-primary">Choose your cabin</h2>
            <p className="muted mt-1 text-sm">
              Select one or more available cabins. Booked and held cabins cannot be selected.
            </p>
          </div>
          <div className="rounded-xl bg-surface-muted px-4 py-3 text-right">
            <p className="text-xs font-bold uppercase tracking-wide text-muted">Deck availability</p>
            <p className="mt-1 text-lg font-extrabold text-primary">{availableCount} available</p>
          </div>
        </div>

        <div className="mt-5 flex gap-2 overflow-x-auto pb-1">
          {decks.map((deck) => {
            const count = deck.cabin_types.reduce(
              (total, type) => total + type.cabins.filter((cabin) => cabin.status === 'available').length,
              0,
            );
            const active = deck.deck_id === activeDeck?.deck_id;
            return (
              <button
                key={deck.deck_id}
                type="button"
                onClick={() => setActiveDeckId(deck.deck_id)}
                className={`shrink-0 rounded-full border px-5 py-2.5 text-sm font-extrabold transition ${
                  active
                    ? 'deck-tab-active text-inverse shadow-sm'
                    : 'border-default bg-transparent text-inverse-muted hover:border-accent hover:text-inverse'
                }`}
              >
                {deck.name || `Deck ${deck.deck_number}`}
                <span className={`ml-2 text-xs ${active ? 'text-inverse-muted/70' : 'text-muted'}`}>{count}</span>
              </button>
            );
          })}
        </div>

        <div className="deck-plan-shell mt-5 overflow-x-auto rounded-3xl p-3 sm:p-5">
          <div className="mx-auto min-w-[650px] max-w-[820px]">
            <div className="mb-3 flex items-center justify-between px-5 text-[11px] font-extrabold uppercase tracking-[0.14em] text-muted">
              <span>▲ Bow / forward</span>
              <span>{activeDeck?.name || 'Deck'} · Stern / aft ▼</span>
            </div>

            {/* The hull is decorative. Cabin IDs and availability still come from the API. */}
            <div className="deck-hull relative mx-auto overflow-hidden rounded-[46%_46%_12%_12%/8%_8%_7%_7%] px-6 py-8 shadow-inner sm:px-10">
              <div className="pointer-events-none absolute bottom-7 left-1/2 top-7 w-8 -translate-x-1/2 rounded-full bg-[#0d0d12]" />
              <div className="relative z-10 space-y-2.5">
                {rows.map((row, rowIndex) => {
                  const left = row.slice(0, 2);
                  const right = row.slice(2, 4);
                  return (
                    <div key={`${activeDeck?.deck_id}-${rowIndex}`} className="grid grid-cols-[1fr_1fr_36px_1fr_1fr] gap-2">
                      {[0, 1].map((slot) => {
                        const cabin = left[slot];
                        return cabin ? (
                          <CabinRoom
                            key={cabin.cabin_id}
                            cabin={cabin}
                            selected={selectedIds.has(cabin.cabin_id)}
                            onSelect={onToggle}
                          />
                        ) : <div key={`left-empty-${slot}`} />;
                      })}
                      <div className="flex items-center justify-center text-[9px] font-bold text-inverse-muted">
                        {String(rowIndex + 1).padStart(2, '0')}
                      </div>
                      {[0, 1].map((slot) => {
                        const cabin = right[slot];
                        return cabin ? (
                          <CabinRoom
                            key={cabin.cabin_id}
                            cabin={cabin}
                            selected={selectedIds.has(cabin.cabin_id)}
                            onSelect={onToggle}
                          />
                        ) : <div key={`right-empty-${slot}`} />;
                      })}
                    </div>
                  );
                })}
              </div>
              <div className="pointer-events-none mt-8 text-center text-[10px] font-extrabold uppercase tracking-[0.28em] text-inverse-muted">
                Stern / aft
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 border-t border-default pt-4 text-xs font-bold text-muted">
              {Object.entries(TYPE_STYLES).map(([name, style]) => (
                <span key={name} className="inline-flex items-center gap-2 capitalize">
                  <span className={`cabin-legend-dot ${style.className}`} />
                  {style.label}
                </span>
              ))}
              <span className="inline-flex items-center gap-2">
                <span className="h-3 w-5 rounded border border-accent bg-accent-soft/40" />
                Selected
              </span>
              <span className="inline-flex items-center gap-2">
                <span className="h-3 w-5 rounded border border-default bg-surface-subtle" />
                Held / booked
              </span>
            </div>
          </div>
        </div>
      </section>

      <aside className="h-fit xl:sticky xl:top-24">
        <div className="booking-selection-panel rounded-3xl bg-navy-900 p-6 text-inverse shadow-xl sm:p-7">
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-inverse-muted">Your selection</p>
          <h3 className="mt-2 text-2xl font-extrabold">
            {selectedCabins.length
              ? `${selectedCabins.length} cabin${selectedCabins.length > 1 ? 's' : ''}`
              : 'No cabin selected'}
          </h3>

          <div className="mt-5 space-y-3">
            {selectedCabins.length ? selectedCabins.map((cabin) => (
              <div key={cabin.cabin_id} className="flex items-start justify-between gap-4 border-b border-white/10 pb-3 text-sm">
                <div>
                  <p className="font-extrabold">Cabin {cabin.cabin_number}</p>
                  <p className="mt-0.5 text-inverse-muted/60">{cabin.cabin_type_name}</p>
                </div>
                <p className="font-extrabold">{formatMoney(cabin.price_cents)}</p>
              </div>
            )) : (
              <p className="text-sm leading-6 text-inverse-muted/60">Click an available cabin on the deck plan to add it.</p>
            )}
          </div>

          <div className="mt-5 border-t border-white/15 pt-4">
            <div className="flex justify-between gap-4 text-sm text-inverse-muted/65">
              <span>Guests selected</span>
              <span className="font-extrabold text-inverse">{totalGuests}</span>
            </div>
            <div className="mt-2 flex justify-between gap-4">
              <span className="text-sm text-inverse-muted/70">Estimated total</span>
              <span className="text-2xl font-extrabold">{formatMoney(estimatedTotal)}</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-inverse-muted/50">
              Final price is recalculated by the server when the cabin is held.
            </p>
          </div>

          <button
            type="button"
            disabled={!selectedCabins.length}
            onClick={onContinue}
            className="btn cabin-continue-button mt-6 w-full"
          >
            Continue to occupancy →
          </button>
          <p className="mt-3 text-center text-xs text-inverse-muted/45">Cabin hold: 10 minutes during checkout.</p>
        </div>
      </aside>
    </div>
  );
}
