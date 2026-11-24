/** Icônes SVG décoratives (aria-hidden) — aucune dépendance externe, compatibles CSP. */
import type { ReactNode } from "react";

const PATHS = {
  dashboard: <path d="M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z" />,
  book: <path d="M6 2h11a2 2 0 0 1 2 2v16a1 1 0 0 1-1 1H6a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3Zm0 15a1 1 0 0 0 0 2h11v-2H6Zm1-12v2h8V5H7Z" />,
  loan: <path d="M12 3a9 9 0 1 1-9 9h2a7 7 0 1 0 2.05-4.95L9 9H3V3l2.64 2.64A8.97 8.97 0 0 1 12 3Zm-1 4h2v4.59l3.2 3.2-1.4 1.42L11 12.4V7Z" />,
  bookmark: <path d="M6 2h12a1 1 0 0 1 1 1v19l-7-4.5L5 22V3a1 1 0 0 1 1-1Z" />,
  coin: <path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm1 4h-2v1.1A3 3 0 0 0 11.5 13h1a1 1 0 0 1 0 2H9v2h2v1h2v-1.1A3 3 0 0 0 12.5 11h-1a1 1 0 0 1 0-2H15V7h-2V6Z" />,
  tag: <path d="M3 3h8l10 10-8 8L3 11V3Zm4.5 3a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z" />,
  users: <path d="M9 11a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm8 0a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM1 20c0-3.3 3.6-6 8-6s8 2.7 8 6v1H1v-1Zm17.5 1v-1c0-1.9-.8-3.6-2.1-4.9 3.5.3 6.6 2.4 6.6 4.9v1h-4.5Z" />,
  shield: <path d="M12 2 4 5v6c0 5 3.4 9.6 8 11 4.6-1.4 8-6 8-11V5l-8-3Zm-1 13.4-3.7-3.7 1.4-1.4 2.3 2.3 4.6-4.6 1.4 1.4-6 6Z" />,
  logout: <path d="M10 3h9a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-9v-2h9V5h-9V3Zm1.6 4.6L13 6.2 18.8 12 13 17.8l-1.4-1.4 3.4-3.4H3v-2h12l-3.4-3.4Z" />,
  alert: <path d="M12 2 1 21h22L12 2Zm-1 7h2v6h-2V9Zm0 8h2v2h-2v-2Z" />,
  check: <path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2Z" />,
  clock: <path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20Zm-1 5v6l5.2 3.1 1-1.6-4.2-2.5V7h-2Z" />,
  search: <path d="M10 2a8 8 0 0 1 6.32 12.9l5.39 5.4-1.41 1.4-5.4-5.39A8 8 0 1 1 10 2Zm0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12Z" />,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof PATHS;
const ICONS = new Map<string, ReactNode>(Object.entries(PATHS));

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
      {ICONS.get(name)}
    </svg>
  );
}
