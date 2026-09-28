import { cruisePhotoAssets } from '../assets/images/photoSources';

export const cruiseImages = {
  hero: cruisePhotoAssets.hero,
  whiteShip: cruisePhotoAssets.whiteShip,
  sunset: cruisePhotoAssets.shipSunrise,
  harbor: cruisePhotoAssets.shipOcean,
  shipDeck: cruisePhotoAssets.shipDeck,
  shipSide: cruisePhotoAssets.shipSide,
  cabin: cruisePhotoAssets.cabinInterior,
  oceanView: cruisePhotoAssets.cabinOceanView,
  balcony: cruisePhotoAssets.cabinBalcony,
};

export const cabinImages = {
  interior: cruisePhotoAssets.cabinInterior,
  'ocean view': cruisePhotoAssets.cabinOceanView,
  balcony: cruisePhotoAssets.cabinBalcony,
  suite: cruisePhotoAssets.cabinBalcony,
};

const legacyImageFragments = [
  '1764609627878-4cb050c7c583',
  '1580698360366-a34bd05adce4',
  '/car',
  'car-',
  'car_',
  'automobile',
  'vehicle',
  'road-trip',
  'steering-wheel',
  'dashboard',
];

function isUsableImage(url) {
  const normalizedUrl = String(url || '').toLowerCase();
  return Boolean(normalizedUrl) && !legacyImageFragments.some((fragment) => normalizedUrl.includes(fragment));
}

export function getCruiseImage(cruise) {
  if (isUsableImage(cruise?.cover_image)) return cruise.cover_image;
  if (isUsableImage(cruise?.images?.[0]?.url)) return cruise.images[0].url;

  const key = `${cruise?.slug || ''} ${cruise?.name || ''}`.toLowerCase();

  if (key.includes('caribbean') || key.includes('sunset')) {
    return cruiseImages.sunset;
  }

  if (key.includes('mediterranean') || key.includes('aegean')) {
    return cruiseImages.harbor;
  }

  if (key.includes('arabian') || key.includes('dubai')) {
    return cruiseImages.shipDeck;
  }

  if (key.includes('gulf')) {
    return cruiseImages.shipSide;
  }

  return cruiseImages.hero;
}

export function getCabinImage(name = '') {
  const normalizedName = String(name || '').trim().toLowerCase();
  return cabinImages[normalizedName] || cruiseImages.cabin;
}
