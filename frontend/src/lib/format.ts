export const divisions = [
  'HEAVYWEIGHT',
  'LIGHT_HEAVYWEIGHT',
  'MIDDLEWEIGHT',
  'WELTERWEIGHT',
  'LIGHTWEIGHT',
  'FEATHERWEIGHT',
  'BANTAMWEIGHT',
  'FLYWEIGHT',
  'WOMENS_FEATHERWEIGHT',
  'WOMENS_BANTAMWEIGHT',
  'WOMENS_FLYWEIGHT',
  'WOMENS_STRAWWEIGHT',
];
export function label(value: string | null | undefined): string {
  if (!value) return '—';
  return value
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/Womens/g, "Women's");
}
export function date(value: string, short = false): string {
  return new Intl.DateTimeFormat('en-US', {
    month: short ? 'short' : 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`));
}
export function number(value: number | null | undefined, digits = 0): string {
  return value == null || !Number.isFinite(value)
    ? '—'
    : value.toLocaleString('en-US', { maximumFractionDigits: digits });
}
export function odds(value: number | null | undefined): string {
  return value == null ? '—' : `${value > 0 ? '+' : ''}${value}`;
}
export function inches(value: number | null | undefined): string {
  return value == null ? '—' : `${value}″`;
}
export function delta(
  a: number | null | undefined,
  b: number | null | undefined,
  unit = '',
): string {
  return a == null || b == null ? '—' : `${a - b > 0 ? '+' : ''}${a - b}${unit}`;
}
export function fighterHref(uid: string): string {
  return `?view=fighters&fighter=${encodeURIComponent(uid)}`;
}
