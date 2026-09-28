import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import { cruiseImages } from '../../lib/images';
import FeaturedCruiseCard from '../../components/cruises/FeaturedCruiseCard';


const features = [
  ['01', 'Choose your sailing', 'Compare routes, dates and live cabin availability before you book.'],
  ['02', 'Pick your cabin', 'Explore interior, ocean-view, balcony and suite options.'],
  ['03', 'Add your guests', 'Enter traveler details once and keep the booking simple.'],
  ['04', 'Pay securely', 'Your cabin is held while Stripe securely completes payment.'],
];

export default function Landing() {
  const navigate = useNavigate();
  const [form, setForm] = React.useState({ destination: '', month: '', guests: '2' });
  const featuredQuery = useQuery({
    queryKey: ['featured'],
    queryFn: async () => (await api.get('/cruises/featured')).data,
    staleTime: 300000,
  });
  const data = Array.isArray(featuredQuery.data)
    ? featuredQuery.data
    : Array.isArray(featuredQuery.data?.items)
      ? featuredQuery.data.items
      : [];

  const submit = event => {
    event.preventDefault();
    const params = new URLSearchParams();
    if (form.destination) params.set('q', form.destination);
    if (form.month) {
      const now = new Date();
      const monthIndex = new Date(`${form.month} 1, 2000`).getMonth();
      let year = now.getFullYear();
      if (monthIndex < now.getMonth()) year += 1;
      const mm = String(monthIndex + 1).padStart(2, '0');
      params.set('departure_from', `${year}-${mm}-01`);
      params.set('departure_to', `${year}-${mm}-${new Date(year, monthIndex + 1, 0).getDate()}`);
    }
    if (form.guests) params.set('guests', form.guests);
    navigate(`/cruises?${params.toString()}`);
  };

  return (
    <div>
      <section className="landing-hero relative overflow-hidden text-inverse">
        <img
          src={cruiseImages.whiteShip}
          alt="White cruise ship sailing across the ocean"
          className="hero-photo absolute inset-0 h-full w-full object-cover"
          aria-hidden="true"
          onError={event => { event.currentTarget.src = cruiseImages.hero; }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#061224]/95 via-[#081426]/65 to-[#081426]/18" />
        <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/10" />

        <div className="container-app relative grid items-center gap-10 py-16 lg:grid-cols-[1.05fr_.95fr] lg:py-20">
          <div>
            <div className="landing-experience-badge inline-flex items-center gap-2 rounded-full border border-white/20 bg-black/30 px-3 py-1.5 text-xs font-bold text-white shadow-sm backdrop-blur-md">
              <span className="h-2 w-2 rounded-full bg-[#ff6767]" /> Unforgettable ocean experiences
            </div>
            <h1 className="landing-hero-title mt-5 font-extrabold tracking-[-.055em]">
              Your Dream Cruise<br /><span className="heading-gradient">Awaits</span>
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-inverse-muted sm:text-lg">
              Explore beautiful destinations, relax on board, enjoy comfortable cabins and create memorable moments at sea.
            </p>

            <form onSubmit={submit} className="landing-search-panel mt-7 rounded-2xl border border-white/15 bg-[#101a2b]/80 p-3 backdrop-blur-xl">
              <div className="grid gap-2 sm:grid-cols-3">
                <label className="landing-search-field">
                  <span>Destination</span>
                  <input value={form.destination} onChange={event => setForm({ ...form, destination: event.target.value })} placeholder="Any destination" />
                </label>
                <label className="landing-search-field">
                  <span>When</span>
                  <select value={form.month} onChange={event => setForm({ ...form, month: event.target.value })}>
                    <option value="">Any month</option>
                    {['January','February','March','April','May','June','July','August','September','October','November','December'].map(month => <option key={month}>{month}</option>)}
                  </select>
                </label>
                <label className="landing-search-field">
                  <span>Guests</span>
                  <select value={form.guests} onChange={event => setForm({ ...form, guests: event.target.value })}>
                    {[1,2,3,4,5].map(number => <option key={number} value={number}>{number}{number === 5 ? '+' : ''} {number === 1 ? 'guest' : 'guests'}</option>)}
                  </select>
                </label>
              </div>
              <button className="btn btn-primary landing-search-button mt-3 w-full sm:w-auto">Search <span aria-hidden="true">→</span></button>
            </form>

            <div className="landing-stats mt-6 flex flex-wrap gap-x-7 gap-y-3 text-sm">
              <span><strong>100+</strong> Luxury Cruises</span>
              <span><strong>50+</strong> Destinations</span>
              <span><strong>4.8/5</strong> Guest Rating</span>
            </div>
          </div>

          <div className="hidden lg:block">
            <div className="landing-hero-side rounded-[26px] border border-white/15 bg-black/20 p-3 backdrop-blur-sm">
              <img src={cruiseImages.whiteShip} alt="White cruise ship" className="h-[300px] w-full rounded-[20px] object-cover" />
              <div className="p-4">
                <p className="eyebrow">A better way to cruise</p>
                <h2 className="mt-2 text-2xl font-extrabold">Choose the journey, cabin and date that fit you.</h2>
                <p className="mt-2 text-sm leading-6 text-inverse-muted">Browse real sailings, compare cabin options and keep the booking process clear from search to e-ticket.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="landing-section container-app py-16 lg:py-20">
        <div className="max-w-3xl">
          <p className="eyebrow">How it works</p>
          <h2 className="section-title mt-3">Everything you need, <span className="heading-gradient">without the booking maze.</span></h2>
          <p className="muted mt-3 max-w-2xl">A cruise combines your transport, accommodation, dining and entertainment into one journey, so you can focus on the places and experiences along the way.</p>
        </div>
        <div className="landing-feature-grid mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {features.map(([number, title, description]) => (
            <div key={number} className="landing-feature-card card p-5 transition hover:-translate-y-1">
              <span className="text-sm font-extrabold text-accent">{number}</span>
              <h3 className="mt-5 text-lg font-extrabold">{title}</h3>
              <p className="muted mt-2 text-sm leading-6">{description}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="deals" className="landing-section border-y border-white/5 bg-[#0d0d12]">
        <div className="container-app py-16 lg:py-20">
          <div className="flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="eyebrow">Real booking activity</p>
              <h2 className="section-title mt-2"><span className="heading-gradient">Most booked cruises</span></h2>
              <p className="muted mt-2">Popular sailings based on confirmed bookings.</p>
            </div>
            <Link className="btn btn-outline" to="/cruises">View all cruises →</Link>
          </div>

          <div className="featured-cruise-grid mt-9 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
            {data.slice(0, 3).map(cruise => (
              <FeaturedCruiseCard key={cruise.id} cruise={cruise} />
            ))}
            {!data.length && <div className="col-span-full card p-10 text-center muted">Featured cruises will appear here once published.</div>}
          </div>

          {data.length > 0 && (
            <div className="mt-6 flex justify-center">
              <Link className="featured-see-all rounded-full border border-[#a343ff]/70 bg-transparent px-8 py-2 text-xs font-bold text-primary transition hover:border-[#ff6767] hover:text-[#ffb1b1]" to="/cruises">See All</Link>
            </div>
          )}
        </div>
      </section>

      <section className="container-app py-16 lg:py-20">
        <div className="why-cruise-panel rounded-[26px] border border-white/10 bg-[#17171e] p-7 sm:p-10">
          <p className="eyebrow">Why cruise?</p>
          <div className="mt-3 grid gap-8 lg:grid-cols-3">
            <div><h3 className="text-xl font-extrabold">One trip, many places</h3><p className="muted mt-2 text-sm leading-6">Wake up in a new destination without changing hotels. Cruises make multi-stop journeys simple and comfortable.</p></div>
            <div><h3 className="text-xl font-extrabold">A cabin that fits</h3><p className="muted mt-2 text-sm leading-6">Choose from practical interiors, ocean views, balconies and larger suites based on your travel style.</p></div>
            <div><h3 className="text-xl font-extrabold">More time to enjoy</h3><p className="muted mt-2 text-sm leading-6">Dining, entertainment, ocean views and onboard activities are part of the journey, not just the destination.</p></div>
          </div>
        </div>
      </section>
    </div>
  );
}
