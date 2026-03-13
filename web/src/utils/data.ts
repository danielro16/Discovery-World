import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '../../..');
const DATA_DIR = path.join(ROOT, 'data');
const VERTICALS_DIR = path.join(ROOT, 'verticals');

// --- Types ---

export interface Place {
  id: string;
  name: string;
  address: string;
  location: { lat: number; lng: number };
  phone: string;
  website: string;
  google_maps_url: string;
  rating: number | null;
  review_count: number;
  business_status: string;
  price_level: string;
  types: string[];
  hours: Record<string, string>;
  reviews: Review[];
  photos: Photo[];
  enriched: boolean;
  enriched_data: Record<string, any>;
  profile_completeness: number;
  claimed: boolean;
  review_analysis?: {
    sentiment: string | null;
    score?: number;
    themes_positive?: string[];
    themes_negative?: string[];
    summary?: string;
  };
}

export interface Review {
  rating: number;
  text: string;
  time: string;
  author: string;
}

export interface Photo {
  name: string;
  width: number;
  height: number;
}

export interface VerticalConfig {
  name: string;
  display_name: string;
  display_name_singular: string;
  google_places_type: string;
  search_queries: string[];
  schema_type: string;
  fields_to_extract: string[];
  extraction_prompt: string;
  content_templates: string[];
  premium_price_monthly: number;
  value_per_new_client: string;
  seo_keywords: string[];
}

// --- Color per vertical ---

export const VERTICAL_COLORS: Record<string, { accent: string; bg: string; light: string }> = {
  dentists:    { accent: '#3b82f6', bg: '#eff6ff', light: '#dbeafe' },
  restaurants: { accent: '#f97316', bg: '#fff7ed', light: '#ffedd5' },
  gyms:        { accent: '#22c55e', bg: '#f0fdf4', light: '#dcfce7' },
  attorneys:   { accent: '#8b5cf6', bg: '#f5f3ff', light: '#ede9fe' },
  therapists:  { accent: '#14b8a6', bg: '#f0fdfa', light: '#ccfbf1' },
};

export const VERTICAL_EMOJIS: Record<string, string> = {
  dentists: '🦷',
  restaurants: '🍽️',
  gyms: '💪',
  attorneys: '⚖️',
  therapists: '🧠',
};

// --- Data loading ---

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

export function getVerticals(): VerticalConfig[] {
  const files = fs.readdirSync(VERTICALS_DIR).filter(f => f.endsWith('.json'));
  return files.map(f => {
    const content = fs.readFileSync(path.join(VERTICALS_DIR, f), 'utf-8');
    return JSON.parse(content) as VerticalConfig;
  });
}

export function getVertical(name: string): VerticalConfig {
  const content = fs.readFileSync(path.join(VERTICALS_DIR, `${name}.json`), 'utf-8');
  return JSON.parse(content) as VerticalConfig;
}

export function getCities(vertical: string): string[] {
  const verticalDir = path.join(DATA_DIR, vertical);
  if (!fs.existsSync(verticalDir)) return [];
  return fs.readdirSync(verticalDir).filter(f =>
    fs.statSync(path.join(verticalDir, f)).isDirectory()
  );
}

export function getPlaces(vertical: string, city: string): Place[] {
  const filePath = path.join(DATA_DIR, vertical, city, 'places.json');
  if (!fs.existsSync(filePath)) return [];
  const content = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(content) as Place[];
}

export function getPlace(vertical: string, city: string, slug: string): Place | undefined {
  const places = getPlaces(vertical, city);
  return places.find(p => slugify(p.name) === slug);
}

export function getAllPlaces(): { vertical: string; city: string; places: Place[] }[] {
  const results: { vertical: string; city: string; places: Place[] }[] = [];
  for (const v of getVerticals()) {
    for (const city of getCities(v.name)) {
      const places = getPlaces(v.name, city);
      if (places.length > 0) {
        results.push({ vertical: v.name, city, places });
      }
    }
  }
  return results;
}

export function formatCityName(citySlug: string): string {
  return citySlug
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

export function formatCitySlug(citySlug: string): string {
  return citySlug.replace(/_/g, '-');
}

export function getStats(places: Place[]) {
  const total = places.length;
  const withWebsite = places.filter(p => p.website).length;
  const withPhone = places.filter(p => p.phone).length;
  const enriched = places.filter(p => p.enriched).length;
  const ratings = places.filter(p => p.rating != null).map(p => p.rating!);
  const avgRating = ratings.length > 0
    ? Math.round((ratings.reduce((a, b) => a + b, 0) / ratings.length) * 10) / 10
    : 0;
  const avgReviews = total > 0
    ? Math.round(places.reduce((a, p) => a + (p.review_count || 0), 0) / total)
    : 0;

  return { total, withWebsite, withPhone, enriched, avgRating, avgReviews };
}
