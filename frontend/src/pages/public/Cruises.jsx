import PageHero from '../../components/ui/PageHero';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { EmptyState, ErrorBox, Loading } from '../../components/ui/States';
import FeaturedCruiseCard from '../../components/cruises/FeaturedCruiseCard';

/**
 * All-cruises page.
 *
 * The cruise cards intentionally reuse the exact visual pattern used by
 * "Most booked cruises" on the landing page. This keeps the See All page
 * visually consistent with the reference design.
 */
export default function Cruises() {
  const [params, setParams] = useSearchParams();
  const initial = useMemo(() => ({
    q: params.get('q') || '',
    min_price: params.get('min_price') || '',
    max_price: params.get('max_price') || '',
    sort: params.get('sort') || 'departure_asc',
    departure_from: params.get('departure_from') || '',
    departure_to: params.get('departure_to') || '',
    guests: params.get('guests') || '',
  }), [params]);

  const [filters, setFilters] = useState(initial);
  const [submitted, setSubmitted] = useState(initial);

  const queryParams = useMemo(() => ({
    q: submitted.q || undefined,
    min_price: submitted.min_price ? Number(submitted.min_price) * 100 : undefined,
    max_price: submitted.max_price ? Number(submitted.max_price) * 100 : undefined,
    sort: submitted.sort || 'departure_asc',
    departure_from: submitted.departure_from || undefined,
    departure_to: submitted.departure_to || undefined,
    guests: submitted.guests ? Number(submitted.guests) : undefined,
    page: 1,
    page_size: 20,
  }), [submitted]);

  const { data: rawData, isLoading, isError, refetch } = useQuery({
    queryKey: ['cruises', queryParams],
    queryFn: async () => (await api.get('/cruises', { params: queryParams })).data,
  });

  const data = rawData && typeof rawData === 'object' ? rawData : {};
  const cruiseItems = Array.isArray(data.items) ? data.items : [];

  const submit = event => {
    event.preventDefault();
    setSubmitted(filters);

    const next = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) next.set(key, value);
    });
    setParams(next);
  };

  const clear = () => {
    const empty = {
      q: '',
      min_price: '',
      max_price: '',
      sort: 'departure_asc',
      departure_from: '',
      departure_to: '',
      guests: '',
    };
    setFilters(empty);
    setSubmitted(empty);
    setParams({});
  };

  return (
    <div>
      <PageHero
        eyebrow="Explore cruises"
        title="Find your next journey."
        subtitle="Browse every cruise with the same clean card experience as our most booked cruises."
      />

      <div className="container-app py-10 lg:py-14">
        {/* Keep the search controls, but do not change the cruise-card design. */}
        <form onSubmit={submit} className="card p-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4 items-end">
          <label className="text-xs font-bold text-muted md:col-span-2 lg:col-span-2">
            Search
            <input
              className="input mt-1"
              placeholder="Cruise name or destination"
              value={filters.q}
              onChange={e => setFilters({ ...filters, q: e.target.value })}
            />
          </label>

          <label className="text-xs font-bold text-muted">
            Guests
            <select
              className="input mt-1"
              value={filters.guests}
              onChange={e => setFilters({ ...filters, guests: e.target.value })}
            >
              <option value="">Any occupancy</option>
              {[1, 2, 3, 4, 5, 6].map(n => (
                <option key={n} value={n}>{n} {n === 1 ? 'guest' : 'guests'}</option>
              ))}
            </select>
          </label>

          <label className="text-xs font-bold text-muted">
            Sort
            <select
              className="input mt-1"
              value={filters.sort}
              onChange={e => setFilters({ ...filters, sort: e.target.value })}
            >
              <option value="departure_asc">Departure</option>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
              <option value="popularity">Popularity</option>
            </select>
          </label>

          <label className="text-xs font-bold text-muted">
            Min price
            <input
              className="input mt-1"
              type="number"
              min="0"
              placeholder="$"
              value={filters.min_price}
              onChange={e => setFilters({ ...filters, min_price: e.target.value })}
            />
          </label>

          <label className="text-xs font-bold text-muted">
            Max price
            <input
              className="input mt-1"
              type="number"
              min="0"
              placeholder="$"
              value={filters.max_price}
              onChange={e => setFilters({ ...filters, max_price: e.target.value })}
            />
          </label>

          <label className="text-xs font-bold text-muted">
            Departure from
            <input
              className="input mt-1"
              type="date"
              value={filters.departure_from}
              onChange={e => setFilters({ ...filters, departure_from: e.target.value })}
            />
          </label>

          <label className="text-xs font-bold text-muted">
            Departure to
            <input
              className="input mt-1"
              type="date"
              value={filters.departure_to}
              onChange={e => setFilters({ ...filters, departure_to: e.target.value })}
            />
          </label>

          <div className="flex gap-2 lg:justify-end">
            <button type="button" className="btn btn-outline flex-1 lg:flex-none" onClick={clear}>
              Clear
            </button>
            <button className="btn btn-primary flex-1 lg:flex-none">
              Search
            </button>
          </div>
        </form>

        {isLoading ? (
          <div className="py-12"><Loading label="Loading cruises" /></div>
        ) : isError ? (
          <div className="py-12"><ErrorBox retry={refetch} /></div>
        ) : (
          <>
            <div className="mt-9 flex items-center justify-between">
              <div>
                <p className="eyebrow">Explore the fleet</p>
                <h2 className="section-title mt-2">
                  <span className="heading-gradient">All cruises</span>
                </h2>
                <p className="muted mt-2">Choose a sailing and view the full cruise details.</p>
              </div>
              <p className="hidden text-sm font-semibold text-muted sm:block">
                {data?.total || 0} cruises
              </p>
            </div>

            {!cruiseItems.length ? (
              <div className="mt-6">
                <EmptyState
                  title="No cruises match these filters"
                  description="Try a broader search, remove the date range, or clear the price filters."
                  action={<button className="btn btn-primary" onClick={clear}>Clear filters</button>}
                />
              </div>
            ) : (
              <div className="featured-cruise-grid mt-9 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
                {cruiseItems.map(cruise => (
                  <FeaturedCruiseCard key={cruise.id} cruise={cruise} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
