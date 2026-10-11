// Small inline SVG icons (Material Symbols style) so there is no icon dependency.

export const GeminiIcon = ({ size = 18, id = "gem" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
        <stop stopColor="#4285F4" />
        <stop offset="0.5" stopColor="#9B72CB" />
        <stop offset="1" stopColor="#D96570" />
      </linearGradient>
    </defs>
    <path
      fill={`url(#${id})`}
      d="M12 0c0 6.627-5.373 12-12 12 6.627 0 12 5.373 12 12 0-6.627 5.373-12 12-12-6.627 0-12-5.373-12-12z"
    />
  </svg>
);

/** Same spark but solid white — for use inside gradient buttons. */
export const SparkIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 0c0 6.627-5.373 12-12 12 6.627 0 12 5.373 12 12 0-6.627 5.373-12 12-12-6.627 0-12-5.373-12-12z" />
  </svg>
);

const I = ({ children, size = 20, className }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
    {children}
  </svg>
);

export const IconDashboard = (p) => (
  <I {...p}><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" /></I>
);
export const IconShip = (p) => (
  <I {...p}><path d="M20 21c-1.4 0-2.8-.5-4-1.5-2.4 2-5.6 2-8 0-1.2 1-2.6 1.5-4 1.5H2v-2h2c1.4 0 2.8-.6 4-1.7 2.4 2.2 5.6 2.2 8 0 1.2 1.1 2.6 1.7 4 1.7h2v2h-2zM3.95 16.4 2 15.8l2.5-8.1c.25-.82 1-1.4 1.87-1.4H9V4h6v2.3h2.63c.87 0 1.62.58 1.87 1.4L22 15.8l-1.95.6L17.63 8.3H6.37L3.95 16.4z" /></I>
);
export const IconWarning = (p) => (
  <I {...p}><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" /></I>
);
export const IconCheck = (p) => (
  <I {...p}><path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z" /></I>
);
export const IconSignal = (p) => (
  <I {...p}><path d="M12 3a9 9 0 0 0-9 9h2a7 7 0 0 1 14 0h2a9 9 0 0 0-9-9zm0 4a5 5 0 0 0-5 5h2a3 3 0 0 1 6 0h2a5 5 0 0 0-5-5zm0 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4z" /></I>
);
export const IconGrid = (p) => (
  <I {...p}><path d="M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z" /></I>
);
export const IconStar = (p) => (
  <I {...p}><path d="m12 17.27 6.18 3.73-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27z" /></I>
);
export const IconReceipt = (p) => (
  <I {...p}><path d="M3 22l1.5-1.5L6 22l1.5-1.5L9 22l1.5-1.5L12 22l1.5-1.5L15 22l1.5-1.5L18 22l1.5-1.5L21 22V2l-1.5 1.5L18 2l-1.5 1.5L15 2l-1.5 1.5L12 2l-1.5 1.5L9 2 7.5 3.5 6 2 4.5 3.5 3 2v20zm4-6V8h10v8H7z" /></I>
);
export const IconLeaf = (p) => (
  <I {...p}><path d="M6.05 8.05a7 7 0 0 0-.02 9.9c1.47-3.4 4.09-6.24 7.37-7.93A13.9 13.9 0 0 0 8 19.32c1.9.7 4.1.42 5.73-.9C17.84 15.1 17 7 22 3c-6 1-13 2-15.95 5.05z" /></I>
);
export const IconSettings = (p) => (
  <I {...p}><path d="M19.14 12.94a7.5 7.5 0 0 0 0-1.88l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.03 7.03 0 0 0-1.62-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54c-.59.24-1.13.56-1.62.94l-2.39-.96a.5.5 0 0 0-.6.22L2.71 8.84a.5.5 0 0 0 .12.64l2.03 1.58a7.5 7.5 0 0 0 0 1.88L2.83 14.52a.5.5 0 0 0-.12.64l1.92 3.32c.13.22.39.3.6.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.04.24.25.42.5.42h3.84c.25 0 .46-.18.5-.42l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7z" /></I>
);
export const IconMenu = (p) => (
  <I {...p}><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" /></I>
);
export const IconSun = (p) => (
  <I {...p}><path d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 8a3 3 0 1 1 0-6 3 3 0 0 1 0 6zM11 1h2v3h-2V1zm0 19h2v3h-2v-3zM1 11h3v2H1v-2zm19 0h3v2h-3v-2zM4.2 5.6 5.6 4.2l2.1 2.1-1.4 1.4-2.1-2.1zm12.1 12.1 1.4-1.4 2.1 2.1-1.4 1.4-2.1-2.1zM18.4 4.2l1.4 1.4-2.1 2.1-1.4-1.4 2.1-2.1zM6.3 16.3l1.4 1.4-2.1 2.1-1.4-1.4 2.1-2.1z" /></I>
);
export const IconMoon = (p) => (
  <I {...p}><path d="M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36A5.39 5.39 0 0 1 16.5 13 5.5 5.5 0 0 1 11 7.5c0-1.73.8-3.27 2.05-4.28A9.3 9.3 0 0 0 12 3z" /></I>
);
export const IconClose = (p) => (
  <I {...p}><path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z" /></I>
);
export const IconRefresh = (p) => (
  <I {...p}><path d="M17.65 6.35A7.96 7.96 0 0 0 12 4a8 8 0 1 0 7.73 10h-2.08A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" /></I>
);
export const IconMoney = (p) => (
  <I {...p}><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15.9V19h-2v-1.1c-1.6-.3-2.9-1.3-3-3.1h1.9c.1 1 .8 1.7 2.1 1.7 1.4 0 1.9-.7 1.9-1.4 0-.6-.3-1.2-2.1-1.6-2-.5-3.4-1.3-3.4-2.9 0-1.4 1.1-2.4 2.6-2.7V7h2v1.1c1.5.3 2.4 1.4 2.5 2.7h-1.9c-.1-.9-.6-1.5-1.7-1.5-1.1 0-1.7.5-1.7 1.2 0 .6.5 1 2.1 1.4 1.9.5 3.4 1.2 3.4 3.1 0 1.5-1.1 2.5-2.7 2.9z" /></I>
);
