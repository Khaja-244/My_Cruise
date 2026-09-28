import { Link } from 'react-router-dom';
import { cruiseImages, getCruiseImage } from '../../lib/images';

const money = cents => new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
}).format((Number(cents) || 0) / 100);

/** Shared cruise card used by homepage and See All page. */
export default function FeaturedCruiseCard({ cruise }) {
  return (
    <Link to={`/cruises/${cruise.slug}`} className="group cruise-card featured-cruise-card overflow-hidden">
      <div className="featured-cruise-media relative overflow-hidden">
        <img
          src={getCruiseImage(cruise)}
          alt={`${cruise.name} cruise`}
          className="absolute inset-0 h-full w-full object-cover"
          loading="lazy"
          onError={event => { event.currentTarget.src = cruiseImages.whiteShip; }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent" />
      </div>
      <div className="featured-cruise-content flex flex-1 flex-col p-4">
        <h3 className="text-[1.05rem] font-extrabold leading-tight text-primary transition group-hover:text-[#f0cfff]">
          {cruise.name}
        </h3>
        <p className="featured-cruise-description muted mt-2 text-xs leading-5">
          {cruise.description || `Enjoy a ${cruise.sailing_days}-day cruise with comfortable cabins, ocean views and memorable onboard experiences.`}
        </p>
        <div className="featured-cruise-meta mt-3 flex flex-wrap items-center gap-2 text-[10px] text-[#bfc2cf]">
          <span>◷ {cruise.sailing_days} Days</span>
          {cruise.embark_port && <span>• {cruise.embark_port}</span>}
          <span>• From {money(cruise.from_price_cents)}</span>
        </div>
        <span className="featured-cruise-action mt-auto self-start rounded-full border border-[#a343ff]/45 bg-[#a343ff]/8 px-3 py-1.5 text-[10px] font-bold text-[#d9b9ff] transition group-hover:border-[#ff6767]/55 group-hover:bg-[#ff6767]/8 group-hover:text-[#ffd1d1]">
          View Details
        </span>
      </div>
    </Link>
  );
}
