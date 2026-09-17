/**
 * theme.mjs — the visual language shared by every view of 旅行规划.
 *
 * Deliberately a custom, Airbnb-like light design (white surfaces, #222 text,
 * #717171 secondary, near-borderless 12px cards, pill controls, one brand
 * accent used sparingly). All rules live in one injected stylesheet under the
 * `.td-root` scope so nothing leaks into the dashboard around us.
 */

import { createElement as h } from 'react'
import { t } from './i18n.mjs'
import { memberTitle, memberLetter } from './data.mjs'

export const FONT = '-apple-system, "Helvetica Neue", Inter, "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", sans-serif'

export const T = {
  text: '#222222',
  muted: '#717171',
  line: '#DDDDDD',
  line2: '#EBEBEB',
  bg: '#FFFFFF',
  bg2: '#F7F7F7',
  brand: '#FF385C',
  brandDark: '#E31C5F',
  ok: '#008A05',
  warn: '#C13515',
}

const STYLE_ID = 'td-v2-styles'

const CSS = `
.td-root { position: relative; height: 100%; min-height: 0; background: ${T.bg}; color: ${T.text}; font-family: ${FONT}; font-size: 14px; line-height: 1.5; color-scheme: light; -webkit-font-smoothing: antialiased; overflow: hidden; }
.td-root *, .td-root *::before, .td-root *::after { box-sizing: border-box; }
.td-root button { font-family: inherit; }
.td-root a { color: inherit; }
.td-scroll { position: absolute; inset: 0; overflow-y: auto; overflow-x: hidden; scrollbar-width: thin; scrollbar-color: #C9C9C9 transparent; }
.td-scroll::-webkit-scrollbar { width: 8px; }
.td-scroll::-webkit-scrollbar-thumb { background: #C9C9C9; border-radius: 8px; }

/* ── controls ─────────────────────────────────────────────────────────── */
.td-pill { display: inline-flex; align-items: center; gap: 8px; height: 40px; padding: 0 16px; border-radius: 9999px; border: 1px solid ${T.line}; background: #fff; color: ${T.text}; font-size: 14px; font-weight: 600; cursor: pointer; white-space: nowrap; transition: border-color .15s, background .15s, transform .1s; }
.td-pill:hover { border-color: ${T.text}; }
.td-pill:active { transform: scale(.98); }
.td-pill.td-dark { background: ${T.text}; color: #fff; border-color: ${T.text}; }
.td-pill.td-dark:hover { background: #000; }
.td-pill.td-sm { height: 34px; padding: 0 14px; font-size: 13px; }
.td-pill.td-selected { background: ${T.text}; color: #fff; border-color: ${T.text}; }
.td-pill:disabled { opacity: .55; cursor: default; }
.td-iconbtn { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 9999px; border: 1px solid ${T.line}; background: #fff; color: ${T.text}; cursor: pointer; transition: border-color .15s, background .15s; }
.td-iconbtn:hover { border-color: ${T.text}; background: ${T.bg2}; }
.td-float { background: #fff; border-radius: 16px; box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 6px 20px rgba(0,0,0,.12); }
.td-shadow-pill { box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 4px 12px rgba(0,0,0,.08); border-color: transparent; }

/* ── menu ─────────────────────────────────────────────────────────────── */
.td-menu { position: absolute; top: 48px; right: 0; min-width: 240px; padding: 8px; z-index: 40; }
.td-menu-item { display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 12px; border: 0; background: transparent; border-radius: 10px; font-size: 14px; color: ${T.text}; cursor: pointer; text-align: left; text-decoration: none; }
.td-menu-item:hover { background: ${T.bg2}; }
.td-menu-item:disabled { color: ${T.muted}; cursor: default; }
.td-menu-sep { height: 1px; background: ${T.line2}; margin: 6px 4px; }
.td-menu-head { padding: 8px 12px 4px; font-size: 12px; color: ${T.muted}; }

/* ── trip switcher ────────────────────────────────────────────────────── */
.td-switch { position: relative; }
.td-switch-btn { display: inline-flex; align-items: center; gap: 10px; height: 44px; padding: 4px 14px 4px 6px; max-width: 520px; border-radius: 9999px; border: 1px solid ${T.line}; background: #fff; cursor: pointer; font-size: 14px; font-weight: 600; color: ${T.text}; }
.td-switch-btn:hover { box-shadow: 0 2px 8px rgba(0,0,0,.12); }
.td-switch-badge { display: inline-flex; align-items: center; justify-content: center; min-width: 32px; height: 32px; padding: 0 8px; border-radius: 9999px; background: ${T.text}; color: #fff; font-size: 12px; font-weight: 700; white-space: nowrap; flex-shrink: 0; }
.td-switch-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-switch-hint { display: inline-flex; align-items: center; gap: 4px; height: 30px; padding: 0 10px 0 12px; border-radius: 9999px; background: ${T.bg2}; color: ${T.text}; font-size: 12px; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.td-switch-btn:hover .td-switch-hint, .td-trip-pill:hover .td-switch-hint { background: ${T.line2}; }
.td-menu-adv { margin: 4px -8px -8px; padding: 4px 8px 8px; background: ${T.bg2}; border-radius: 0 0 16px 16px; }
.td-legend { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: ${T.muted}; font-weight: 500; }
.td-legend .k { display: inline-flex; align-items: center; justify-content: center; min-width: 20px; height: 20px; padding: 0 6px; border-radius: 9999px; background: #fff; border: 1px solid ${T.line}; color: ${T.text}; font-size: 11px; font-weight: 700; }
.td-legend .k.stay { background: ${T.text}; color: #fff; border-color: ${T.text}; }
.td-switch-list { position: absolute; left: 0; top: 52px; width: 420px; padding: 8px; z-index: 40; }
.td-switch-row { display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px 12px; border: 0; background: transparent; border-radius: 12px; cursor: pointer; text-align: left; color: ${T.text}; }
.td-switch-row:hover { background: ${T.bg2}; }
.td-switch-row.on { background: ${T.bg2}; }
.td-switch-row .t { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-switch-row .s { font-size: 12px; color: ${T.muted}; }

/* ── avatars ──────────────────────────────────────────────────────────── */
.td-avatar { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 9999px; color: #fff; font-size: 13px; font-weight: 700; border: 2px solid #fff; flex-shrink: 0; position: relative; }
.td-avatar.lg { width: 40px; height: 40px; font-size: 15px; }
.td-avatar.sm { width: 26px; height: 26px; font-size: 11px; border-width: 1.5px; }
.td-avatar.mono { font-size: 11px; letter-spacing: -.02em; }
.td-avatar.lg.mono { font-size: 13px; }
.td-avatar.sm.mono { font-size: 9px; }
.td-avatar .dot { position: absolute; right: -1px; bottom: -1px; width: 10px; height: 10px; border-radius: 9999px; border: 2px solid #fff; background: #B0B0B0; }
.td-avatar .dot.working { background: ${T.ok}; animation: td-pulse 1.4s ease-in-out infinite; }
.td-avatar .dot.done { background: ${T.ok}; }
.td-avatar .dot.blocked { background: ${T.warn}; }
.td-avatars { display: inline-flex; align-items: center; }
.td-avatars .td-avatar + .td-avatar { margin-left: -10px; }
.td-avatars .more { display: inline-flex; align-items: center; justify-content: center; height: 32px; min-width: 32px; padding: 0 8px; margin-left: -10px; border-radius: 9999px; background: ${T.bg2}; border: 2px solid #fff; font-size: 12px; font-weight: 700; color: ${T.text}; }
@keyframes td-pulse { 0%,100% { opacity: 1 } 50% { opacity: .35 } }

/* ── team popover ─────────────────────────────────────────────────────── */
.td-team { position: absolute; top: 48px; right: 0; width: 320px; padding: 12px; z-index: 40; max-height: 70vh; overflow: auto; }
.td-team-row { display: flex; align-items: center; gap: 12px; padding: 8px 6px; border-radius: 10px; }
.td-team-row .n { font-size: 14px; font-weight: 600; }
.td-team-row .d { font-size: 12px; color: ${T.muted}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-team-row .st { margin-left: auto; font-size: 12px; color: ${T.muted}; white-space: nowrap; }
.td-team-row .st.working { color: ${T.ok}; }

/* ── photo tiles ─────────────────────────────────────────────────────── */
.td-photo { position: relative; overflow: hidden; border-radius: 12px; background: ${T.bg2}; flex-shrink: 0; }
.td-photo img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform .35s; }
.td-photo .fallback { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 34px; font-weight: 700; letter-spacing: .04em; }
.td-photo .num { position: absolute; top: 10px; left: 10px; display: inline-flex; align-items: center; justify-content: center; min-width: 26px; height: 26px; padding: 0 8px; border-radius: 9999px; background: #fff; color: ${T.text}; font-size: 12px; font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,.2); }
.td-photo .tag { position: absolute; top: 10px; right: 10px; padding: 3px 10px; border-radius: 9999px; background: rgba(34,34,34,.85); color: #fff; font-size: 12px; font-weight: 600; }

/* ── trip page ────────────────────────────────────────────────────────── */
.td-topbar { position: sticky; top: 0; z-index: 30; display: flex; align-items: center; gap: 16px; height: 72px; padding: 0 32px; background: rgba(255,255,255,.96); backdrop-filter: saturate(180%) blur(8px); border-bottom: 1px solid ${T.line2}; }
.td-brand { display: inline-flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700; color: ${T.brand}; letter-spacing: -.01em; }
.td-hero { position: relative; height: 440px; min-height: 320px; background: ${T.bg2}; overflow: hidden; }
.td-hero img { width: 100%; height: 100%; object-fit: cover; display: block; }
.td-hero .grad { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,.18) 0%, rgba(0,0,0,0) 35%, rgba(0,0,0,.62) 100%); }
.td-hero .actions { position: absolute; top: 24px; right: 32px; display: flex; gap: 10px; }
.td-hero .actions .td-pill { border-color: transparent; box-shadow: 0 1px 2px rgba(0,0,0,.15); }
.td-hero .copy { position: absolute; left: 0; right: 0; bottom: 0; padding: 0 32px 34px; color: #fff; }
.td-hero h1 { margin: 0 0 10px; font-size: 34px; line-height: 1.2; font-weight: 700; letter-spacing: -.01em; text-shadow: 0 1px 12px rgba(0,0,0,.35); }
.td-hero .meta { display: flex; flex-wrap: wrap; gap: 6px 10px; font-size: 15px; font-weight: 500; opacity: .96; text-shadow: 0 1px 8px rgba(0,0,0,.35); }
.td-hero .meta .sep::before { content: '·'; opacity: .7; }
.td-body { max-width: 1160px; margin: 0 auto; padding: 40px 32px 120px; display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 56px; align-items: start; }
@media (max-width: 1100px) { .td-body { grid-template-columns: minmax(0, 1fr); } .td-chatcol { position: static !important; } }
.td-main { min-width: 0; }
.td-h2 { margin: 0 0 12px; font-size: 22px; font-weight: 600; letter-spacing: -.01em; }
.td-desc { margin: 0; font-size: 16px; line-height: 1.65; color: ${T.text}; white-space: pre-line; }
.td-desc.clamp { display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.td-more { margin-top: 10px; padding: 0; border: 0; background: none; font-size: 15px; font-weight: 600; text-decoration: underline; cursor: pointer; color: ${T.text}; }
.td-facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-top: 28px; }
.td-fact { display: flex; align-items: center; gap: 14px; }
.td-fact .ic { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 12px; background: ${T.bg2}; color: ${T.text}; flex-shrink: 0; }
.td-fact .t { font-size: 15px; font-weight: 600; }
.td-fact .s { font-size: 13px; color: ${T.muted}; }
.td-hr { height: 1px; background: ${T.line2}; margin: 40px 0; }
.td-day-head { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
.td-day-head .n { font-size: 22px; font-weight: 600; }
.td-day-head .d { font-size: 15px; color: ${T.muted}; font-weight: 500; }
.td-day-notes { margin: 10px 0 0; font-size: 15px; line-height: 1.6; color: ${T.muted}; }
.td-timeline { position: relative; margin-top: 22px; padding-left: 22px; display: flex; flex-direction: column; gap: 14px; }
.td-timeline::before { content: ''; position: absolute; left: 6px; top: 8px; bottom: 8px; width: 2px; background: ${T.line2}; border-radius: 2px; }
.td-note { position: relative; display: flex; gap: 12px; padding: 14px 18px; border-radius: 12px; background: ${T.bg2}; font-size: 14px; line-height: 1.55; }
.td-note::before { content: ''; position: absolute; left: -20px; top: 20px; width: 10px; height: 10px; border-radius: 9999px; background: #fff; border: 2px solid ${T.line}; }
.td-note .tm { font-weight: 700; flex-shrink: 0; font-variant-numeric: tabular-nums; }
.td-stop { position: relative; display: flex; gap: 20px; padding: 6px 0; border-radius: 16px; cursor: default; }
.td-stop::before { content: ''; position: absolute; left: -20px; top: 22px; width: 10px; height: 10px; border-radius: 9999px; background: ${T.text}; border: 2px solid ${T.text}; }
.td-stop:hover .td-photo img { transform: scale(1.04); }
.td-stop .td-photo { width: 212px; height: 150px; }
.td-stop .body { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 4px; }
.td-stop .tm { font-size: 13px; color: ${T.muted}; font-variant-numeric: tabular-nums; }
.td-stop .nm { font-size: 17px; font-weight: 600; line-height: 1.3; }
.td-stop .nt { font-size: 14px; color: ${T.muted}; line-height: 1.55; }
.td-stop .ad { display: flex; align-items: center; gap: 6px; font-size: 13px; color: ${T.muted}; margin-top: auto; padding-top: 6px; }
.td-stop .ad a { color: ${T.text}; font-weight: 600; text-decoration: underline; cursor: pointer; margin-left: auto; white-space: nowrap; }
.td-chip { display: inline-flex; align-items: center; gap: 6px; height: 26px; padding: 0 10px; border-radius: 9999px; background: ${T.bg2}; color: ${T.text}; font-size: 12px; font-weight: 600; }
.td-stay { position: relative; display: flex; align-items: flex-start; gap: 16px; padding: 18px 20px; border: 1px solid ${T.line}; border-radius: 16px; }
.td-stay::before { content: ''; position: absolute; left: -20px; top: 26px; width: 10px; height: 10px; border-radius: 9999px; background: #fff; border: 2px solid ${T.text}; }
.td-stay .ic { display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius: 12px; background: ${T.text}; color: #fff; flex-shrink: 0; overflow: hidden; }
.td-stay .ic img { width: 100%; height: 100%; object-fit: cover; }
.td-stay .nm { font-size: 16px; font-weight: 600; }
.td-stay .nt { font-size: 14px; color: ${T.muted}; line-height: 1.55; margin-top: 2px; }
.td-stay .tm { margin-left: auto; text-align: right; font-size: 13px; color: ${T.muted}; white-space: nowrap; line-height: 1.7; flex-shrink: 0; }
.td-checkout { display: flex; align-items: center; gap: 8px; font-size: 13px; color: ${T.muted}; margin-top: 12px; }
.td-daymap { margin-top: 24px; }
.td-daymap .lbl { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 16px; font-weight: 600; }
.td-daymap .lbl button { margin-left: auto; }
.td-daymap .map { position: relative; height: 320px; border-radius: 16px; overflow: hidden; border: 1px solid ${T.line2}; }
.td-chatcol { position: sticky; top: 96px; }
.td-chatcard { display: flex; flex-direction: column; border: 1px solid ${T.line}; border-radius: 16px; box-shadow: 0 6px 16px rgba(0,0,0,.08); background: #fff; overflow: hidden; height: calc(100vh - 230px); min-height: 480px; max-height: 760px; }
.td-chatcard .hd { display: flex; align-items: center; gap: 12px; padding: 16px 18px; border-bottom: 1px solid ${T.line2}; }
.td-chatcard .hd .who { min-width: 0; }
.td-chatcard .hd .t { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 600; }
.td-chatcard .hd .s { font-size: 12px; color: ${T.muted}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-chatcard .bd { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.td-chatcard .bd > * { flex: 1; min-height: 0; }
.td-online { display: inline-block; width: 8px; height: 8px; border-radius: 9999px; background: ${T.ok}; }
.td-online.busy { animation: td-pulse 1.4s ease-in-out infinite; }
.td-showmap { position: absolute; left: 50%; bottom: 28px; transform: translateX(-50%); z-index: 35; height: 48px; padding: 0 22px; font-size: 15px; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
.td-toast { position: absolute; left: 50%; bottom: 92px; transform: translateX(-50%); z-index: 36; padding: 10px 16px; border-radius: 12px; background: ${T.text}; color: #fff; font-size: 13px; font-weight: 600; box-shadow: 0 6px 16px rgba(0,0,0,.2); }

/* ── empty state ──────────────────────────────────────────────────────── */
.td-empty { max-width: 720px; margin: 0 auto; padding: 72px 32px 120px; text-align: center; }
.td-empty h1 { margin: 0 0 12px; font-size: 32px; font-weight: 700; letter-spacing: -.01em; }
.td-empty p { margin: 0 0 24px; font-size: 16px; color: ${T.muted}; line-height: 1.6; }
.td-empty .chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-bottom: 28px; }
.td-empty .td-chatcard { height: 520px; text-align: left; }

/* ── map view ─────────────────────────────────────────────────────────── */
.td-mapview { position: absolute; inset: 0; }
.td-mapview .map { position: absolute; inset: 0; z-index: 0; }
.td-mapview .leaflet-top.leaflet-left { margin-top: 128px; }
.td-tiles { filter: saturate(.55) brightness(1.03) contrast(.92); }
.td-ov { position: absolute; z-index: 20; }
.td-ov.tl { top: 20px; left: 20px; display: flex; flex-direction: column; gap: 12px; align-items: flex-start; }
.td-ov.tr { top: 20px; right: 20px; display: flex; gap: 10px; align-items: center; }
.td-ov.br { right: 24px; bottom: 24px; }
.td-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.td-chips .td-pill { height: 38px; }
.td-chips .td-pill .sub { font-weight: 500; opacity: .7; font-size: 12px; }
.td-rail-wrap { position: absolute; left: 0; right: 0; bottom: 0; z-index: 20; padding: 0 20px 20px; pointer-events: none; }
.td-rail-lbl { display: inline-flex; align-items: center; gap: 8px; margin-bottom: 10px; padding: 6px 12px; border-radius: 9999px; background: #fff; font-size: 13px; font-weight: 600; box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 4px 12px rgba(0,0,0,.08); pointer-events: auto; }
.td-rail-lbl span { color: ${T.muted}; font-weight: 500; }
.td-rail { display: flex; gap: 14px; overflow-x: auto; padding: 6px 2px 6px; scroll-snap-type: x proximity; scrollbar-width: none; pointer-events: auto; }
.td-rail::-webkit-scrollbar { display: none; }
.td-card { flex: 0 0 272px; scroll-snap-align: start; background: #fff; border-radius: 16px; padding: 10px; box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 6px 16px rgba(0,0,0,.12); cursor: pointer; transition: transform .18s, box-shadow .18s; border: 2px solid transparent; }
.td-card:hover { transform: translateY(-2px); }
.td-card.on { border-color: ${T.text}; transform: translateY(-4px); box-shadow: 0 10px 24px rgba(0,0,0,.18); }
.td-card .td-photo { width: 100%; height: 150px; }
.td-card .nm { margin-top: 10px; font-size: 15px; font-weight: 600; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-card .nt { margin-top: 3px; font-size: 13px; color: ${T.muted}; line-height: 1.45; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 38px; }
.td-card .ad { margin-top: 6px; display: flex; align-items: center; gap: 5px; font-size: 12px; color: ${T.muted}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-fab { display: inline-flex; align-items: center; justify-content: center; width: 56px; height: 56px; border-radius: 9999px; border: 0; background: ${T.text}; color: #fff; cursor: pointer; box-shadow: 0 6px 16px rgba(0,0,0,.3); transition: transform .15s; }
.td-fab:hover { transform: scale(1.05); }
.td-fab .badge { position: absolute; top: -2px; right: -2px; width: 14px; height: 14px; border-radius: 9999px; background: ${T.ok}; border: 2px solid #fff; }
.td-chatfloat { width: 400px; height: 100%; display: flex; flex-direction: column; overflow: hidden; }
.td-chatfloat .hd { display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-bottom: 1px solid ${T.line2}; }
.td-chatfloat .hd .t { font-size: 15px; font-weight: 600; }
.td-chatfloat .hd .s { font-size: 12px; color: ${T.muted}; display: flex; align-items: center; gap: 6px; }
.td-chatfloat .bd { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.td-chatfloat .bd > * { flex: 1; min-height: 0; }
.td-trip-pill { display: flex; align-items: center; gap: 12px; padding: 10px 14px 10px 16px; max-width: 460px; cursor: pointer; border: 0; text-align: left; }
.td-trip-pill .t { font-size: 15px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-trip-pill .s { font-size: 12px; color: ${T.muted}; }
.td-trip-pill .chev { margin-left: auto; display: inline-flex; width: 32px; height: 32px; border-radius: 9999px; align-items: center; justify-content: center; background: ${T.bg2}; flex-shrink: 0; }

/* ── leaflet pins ─────────────────────────────────────────────────────── */
.td-pin { display: inline-flex; align-items: center; justify-content: center; min-width: 30px; height: 30px; padding: 0 9px; border-radius: 9999px; background: #fff; color: ${T.text}; font: 700 13px/1 ${FONT}; box-shadow: 0 1px 2px rgba(0,0,0,.2), 0 3px 8px rgba(0,0,0,.18); border: 1px solid rgba(0,0,0,.06); white-space: nowrap; transform: translate(-50%, -50%); cursor: pointer; transition: transform .12s; }
.td-pin:hover { transform: translate(-50%, -50%) scale(1.08); z-index: 5; }
.td-pin.on { background: ${T.text}; color: #fff; transform: translate(-50%, -50%) scale(1.12); }
.td-pin.dim { opacity: .55; }
.td-pin.stay { background: ${T.text}; color: #fff; font-weight: 600; }
.td-pin.stay.dim { background: #8a8a8a; }
.leaflet-container.td-leaflet { font-family: ${FONT}; background: #E8EEF2; }
.td-leaflet .leaflet-control-attribution { font-size: 10px; background: rgba(255,255,255,.75); }
.td-leaflet .leaflet-marker-icon { background: transparent; border: 0; }
.td-leaflet .leaflet-bar { border: 0; box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 4px 12px rgba(0,0,0,.08); border-radius: 12px; overflow: hidden; }
.td-leaflet .leaflet-bar a { width: 36px; height: 36px; line-height: 36px; border-bottom-color: ${T.line2}; color: ${T.text}; font-weight: 600; }

/* ── embedded chat ────────────────────────────────────────────────────────
   The host's ChatEmbed is styled with the DASHBOARD's design tokens (Tailwind
   utilities that resolve var(--bg), var(--text), var(--accent), var(--font-body)
   ...). Left alone it paints the dashboard's theme -- dark surfaces, its accent,
   its monospace body font -- inside this white card. Re-declaring every token
   on this wrapper makes the same utilities resolve to THIS page's palette and
   type, with no change to the host component. Element rules below cover the
   few places the host hardcodes a look (user bubble, code, composer). */
.td-embed { display: flex; flex-direction: column; min-height: 0; height: 100%; font-family: ${FONT}; font-size: 14px; color: ${T.text}; color-scheme: light;
  --font-body: ${FONT};
  --bg: #fff; --bg-accent: ${T.bg2}; --bg-elevated: #fff; --bg-hover: #F0F0F0;
  --card: ${T.bg2}; --card-fg: ${T.text}; --card-hl: rgba(0,0,0,.03);
  --panel: #fff; --panel-strong: ${T.bg2}; --chrome: rgba(255,255,255,.95);
  --text: ${T.text}; --text-strong: ${T.text}; --muted: ${T.muted}; --muted-fg: #fff; --muted-strong: #484848;
  --border: ${T.line}; --border-strong: #B0B0B0; --border-hover: ${T.text};
  --accent: ${T.text}; --accent-fg: #fff; --accent-hover: #000; --accent-subtle: rgba(34,34,34,.07); --accent-glow: rgba(34,34,34,.12); --ring: ${T.text};
  --ok: ${T.ok}; --ok-fg: #fff; --ok-subtle: rgba(0,138,5,.1);
  --warn: ${T.warn}; --warn-fg: #fff; --warn-subtle: rgba(193,53,21,.08);
  --danger: ${T.warn}; --danger-fg: #fff; --danger-subtle: rgba(193,53,21,.08);
  --info: #0A6CFF; --info-fg: #fff;
  --aim: #7c3aed; --aim-fg: #fff; --aim-subtle: rgba(124,58,237,.10);
  --clarify: ${T.warn}; --clarify-subtle: rgba(193,53,21,.06);
  --diff-add: rgba(22,163,74,.12); --diff-add-text: #1a7f37; --diff-del: rgba(220,38,38,.12); --diff-del-text: #cf222e;
  --diff-hunk: rgba(34,34,34,.08); --diff-hunk-text: ${T.text}; --diff-meta-text: ${T.text};
  --radius-sm: 8px; --radius-md: 10px; --radius-lg: 14px; --radius-xl: 16px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,.06); --shadow-md: 0 4px 12px rgba(0,0,0,.08); --shadow-lg: 0 12px 28px rgba(0,0,0,.12);
  --search-highlight: rgba(255,167,38,.35); --search-highlight-current: rgba(255,120,0,.7);
}
.td-embed > * { flex: 1; min-height: 0; }
.td-root .td-embed input, .td-root .td-embed textarea, .td-root .td-embed button { font-family: inherit; }
.td-root .td-embed .font-mono { font-family: ${FONT}; }
.td-root .td-embed pre, .td-root .td-embed pre.font-mono, .td-root .td-embed code { font-family: var(--mono); }
.td-root .td-embed .user-bubble { background: ${T.text}; color: #fff; }
.td-root .td-embed .user-bubble a { color: #fff; }
.td-root .td-embed .user-bubble pre { background: rgba(255,255,255,.12); }
.td-root .td-embed .user-bubble :not(pre) > code { background: rgba(255,255,255,.18); color: inherit; }
.td-root .td-embed .msg-content :not(pre) > code { background: rgba(0,0,0,.06); color: inherit; }
.td-root .td-embed .msg-content pre { background: ${T.bg2}; }
.td-root .td-embed .msg-content a { color: ${T.text}; text-decoration: underline; text-decoration-color: rgba(34,34,34,.4); }
.td-root .td-embed .msg-content a:hover { text-decoration-color: ${T.text}; }
.td-root .td-embed input[type="text"] { height: 44px; padding: 0 16px; border-radius: 9999px; background: #fff; border: 1px solid ${T.line}; font-size: 14px; color: ${T.text}; }
.td-root .td-embed input[type="text"]:focus-visible { border-color: ${T.text}; box-shadow: 0 0 0 1px ${T.text}; }
.td-root .td-embed input[type="text"]::placeholder { color: ${T.muted}; }
.td-root .td-embed input[type="text"] + button { width: 44px; height: 44px; padding: 0; border-radius: 9999px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
.td-root .td-embed div:has(> input[type="text"]) { padding: 12px 16px 16px; gap: 10px; border-top: 1px solid ${T.line2}; }

/* ── fresh conversation (the slot does not exist yet) ─────────────────── */
.td-fresh { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.td-fresh .msgs { flex: 1; min-height: 0; overflow: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.td-fresh .from { font-size: 12px; color: ${T.muted}; margin: 0 0 -6px 4px; }
.td-fresh .bubble { max-width: 90%; padding: 10px 14px; border-radius: 16px; font-size: 14px; line-height: 1.55; background: ${T.bg2}; color: ${T.text}; align-self: flex-start; white-space: pre-line; }
.td-fresh .bubble.me { background: ${T.text}; color: #fff; align-self: flex-end; }
.td-fresh .typing { display: inline-flex; gap: 4px; padding: 12px 14px; }
.td-fresh .typing i { width: 6px; height: 6px; border-radius: 9999px; background: ${T.muted}; animation: td-pulse 1.2s ease-in-out infinite; }
.td-fresh .typing i:nth-child(2) { animation-delay: .2s; } .td-fresh .typing i:nth-child(3) { animation-delay: .4s; }
.td-fresh .chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 16px 10px; }
.td-fresh .chips .td-pill { height: 34px; padding: 0 14px; font-size: 13px; font-weight: 500; max-width: 100%; }
.td-fresh .chips .td-pill span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-fresh form { display: flex; align-items: center; gap: 10px; padding: 12px 16px 16px; border-top: 1px solid ${T.line2}; }
.td-fresh input { flex: 1; min-width: 0; height: 44px; padding: 0 16px; border-radius: 9999px; background: #fff; border: 1px solid ${T.line}; font-size: 14px; color: ${T.text}; outline: none; }
.td-fresh input:focus-visible { border-color: ${T.text}; box-shadow: 0 0 0 1px ${T.text}; }
.td-fresh input::placeholder { color: ${T.muted}; }
.td-fresh .send { width: 44px; height: 44px; border-radius: 9999px; border: 0; background: ${T.text}; color: #fff; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }
.td-fresh .send:disabled { opacity: .4; cursor: default; }

/* ── settings page ────────────────────────────────────────────────────── */
.td-settings-bar { position: sticky; top: 0; z-index: 30; display: flex; align-items: center; gap: 16px; height: 72px; padding: 0 32px; background: rgba(255,255,255,.96); backdrop-filter: saturate(180%) blur(8px); border-bottom: 1px solid ${T.line2}; }
.td-back { display: inline-flex; align-items: center; gap: 6px; height: 40px; padding: 0 16px 0 12px; border-radius: 9999px; border: 1px solid ${T.line}; background: #fff; font-size: 14px; font-weight: 600; cursor: pointer; color: ${T.text}; }
.td-back:hover { border-color: ${T.text}; }
.td-settings { max-width: 760px; margin: 0 auto; padding: 36px 32px 120px; }
.td-settings h1 { margin: 0 0 6px; font-size: 28px; font-weight: 700; letter-spacing: -.01em; }
.td-settings .lead { margin: 0 0 28px; font-size: 15px; color: ${T.muted}; line-height: 1.6; }
.td-sec { border: 1px solid ${T.line}; border-radius: 16px; padding: 20px 22px; margin-bottom: 20px; background: #fff; }
.td-sec .hd { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 16px; }
.td-sec .hd .ic { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px; background: ${T.bg2}; color: ${T.text}; flex-shrink: 0; }
.td-sec .hd .t { font-size: 17px; font-weight: 600; }
.td-sec .hd .s { font-size: 13px; color: ${T.muted}; margin-top: 2px; line-height: 1.5; }
.td-choice { display: flex; align-items: center; gap: 14px; width: 100%; padding: 14px 16px; border: 1px solid ${T.line}; border-radius: 12px; background: #fff; cursor: pointer; text-align: left; color: ${T.text}; transition: border-color .15s, box-shadow .15s; }
.td-choice + .td-choice { margin-top: 10px; }
.td-choice:hover { border-color: ${T.text}; }
.td-choice.on { border-color: ${T.text}; box-shadow: 0 0 0 1px ${T.text}; }
.td-choice .t { font-size: 15px; font-weight: 600; }
.td-choice .s { font-size: 13px; color: ${T.muted}; }
.td-choice .radio { margin-left: auto; width: 22px; height: 22px; border-radius: 9999px; border: 2px solid ${T.line}; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; color: #fff; }
.td-choice.on .radio { border-color: ${T.text}; background: ${T.text}; }
.td-kv { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-top: 1px solid ${T.line2}; font-size: 14px; }
.td-kv .k { color: ${T.muted}; min-width: 72px; flex-shrink: 0; }
.td-kv .v { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
.td-kv .v a { color: ${T.text}; }
.td-adv { margin-top: 6px; border-top: 1px solid ${T.line2}; padding-top: 14px; }
.td-adv-toggle { display: inline-flex; align-items: center; gap: 6px; border: 0; background: none; padding: 0; font-size: 14px; font-weight: 600; color: ${T.text}; cursor: pointer; }
.td-adv .note { font-size: 13px; color: ${T.muted}; margin: 10px 0 12px; line-height: 1.5; }
.td-adv .row { display: flex; gap: 10px; flex-wrap: wrap; }

/* ── connect form (setup page + settings) ─────────────────────────────── */
.td-field { display: block; margin-top: 14px; }
.td-field .lbl { font-size: 13px; font-weight: 600; color: ${T.text}; }
.td-field .lbl .hint { margin-left: 6px; font-size: 12px; font-weight: 400; color: ${T.muted}; }
.td-field input { width: 100%; height: 44px; margin-top: 6px; padding: 0 14px; border-radius: 12px; border: 1px solid ${T.line}; background: #fff; font-size: 14px; color: ${T.text}; outline: none; }
.td-field input:focus-visible { border-color: ${T.text}; box-shadow: 0 0 0 1px ${T.text}; }
.td-field input:disabled { background: ${T.bg2}; color: ${T.muted}; }
.td-form-row { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
.td-form-msg { margin-top: 14px; font-size: 13px; line-height: 1.5; }
.td-form-msg.ok { color: ${T.ok}; }
.td-form-msg.bad { color: ${T.warn}; }

/* ── setup page (first run) ───────────────────────────────────────────── */
.td-setup { max-width: 900px; margin: 0 auto; padding: 48px 32px 120px; }
.td-setup-hero { text-align: center; margin-bottom: 28px; }
.td-setup-hero h1 { margin: 0 0 12px; font-size: 34px; font-weight: 700; letter-spacing: -.01em; }
.td-setup-hero p { max-width: 560px; margin: 0 auto; font-size: 16px; color: ${T.muted}; line-height: 1.6; }
.td-setup-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: stretch; }
@media (max-width: 820px) { .td-setup-cards { grid-template-columns: 1fr; } }
.td-setup-card { display: flex; flex-direction: column; border: 1px solid ${T.line}; border-radius: 16px; padding: 24px; background: #fff; }
.td-setup-card h2 { margin: 0 0 4px; font-size: 18px; font-weight: 600; }
.td-setup-card .sub { margin: 0 0 6px; font-size: 13px; color: ${T.muted}; line-height: 1.5; }
.td-setup-card .grow { flex: 1; }
.td-setup .td-setup-card { max-width: 480px; margin: 0 auto; }
.td-setup-card h2 { margin: 4px 0 6px; }
.td-wide { width: 100%; justify-content: center; margin-top: 6px; }
.td-form.primary input { font-size: 15px; }
.td-or { display: flex; align-items: center; gap: 12px; margin: 18px 0 12px; color: ${T.muted}; font-size: 13px; }
.td-or::before, .td-or::after { content: ''; flex: 1; border-top: 1px solid ${T.line2}; }
.td-run.small .td-form-row { margin-top: 0; }
.td-run-note { margin: 10px 0 0; font-size: 13px; color: ${T.muted}; line-height: 1.5; }
.td-linkbtn { border: 0; background: none; padding: 8px 4px; font-size: 13px; color: ${T.muted}; text-decoration: underline; cursor: pointer; }
.td-linkbtn:disabled { cursor: default; opacity: .5; }
.td-adv-title { font-size: 13px; font-weight: 600; margin-bottom: 10px; }
.td-kv-note { font-weight: 400; color: ${T.muted}; margin-left: 8px; font-size: 12px; }
`

export function injectStyles() {
  if (typeof document === 'undefined') return
  let el = document.getElementById(STYLE_ID)
  if (!el) {
    el = document.createElement('style')
    el.id = STYLE_ID
    document.head.appendChild(el)
  }
  if (el.textContent !== CSS) el.textContent = CSS
}

// ─────────────────────────────────────────────────────────────────────────────
// Icons (Lucide-style strokes)
// ─────────────────────────────────────────────────────────────────────────────

const PATHS = {
  pin: ['M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z', 'M12 10m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0'],
  map: ['M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3z', 'M9 3v15', 'M15 6v15'],
  list: ['M8 6h13', 'M8 12h13', 'M8 18h13', 'M3 6h.01', 'M3 12h.01', 'M3 18h.01'],
  external: ['M15 3h6v6', 'M10 14 21 3', 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'],
  share: ['M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8', 'M16 6l-4-4-4 4', 'M12 2v13'],
  more: ['M12 12h.01', 'M19 12h.01', 'M5 12h.01'],
  x: ['M18 6 6 18', 'M6 6l12 12'],
  chat: ['M21 11.5a8.4 8.4 0 0 1-9 8.4 8.6 8.6 0 0 1-3.8-.9L3 21l1.9-5.7A8.4 8.4 0 0 1 3 11.5a8.4 8.4 0 0 1 9-8.4 8.4 8.4 0 0 1 9 8.4z'],
  clock: ['M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0', 'M12 6v6l4 2'],
  bed: ['M2 4v16', 'M2 8h18a2 2 0 0 1 2 2v10', 'M2 17h20', 'M6 8v9'],
  car: ['M19 17H5a2 2 0 0 1-2-2v-3l2-5h14l2 5v3a2 2 0 0 1-2 2Z', 'M7 17v2', 'M17 17v2', 'M7 13h.01', 'M17 13h.01'],
  calendar: ['M8 2v4', 'M16 2v4', 'M3 6h18v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z', 'M3 10h18'],
  users: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M9 11m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0', 'M22 21v-2a4 4 0 0 0-3-3.87', 'M16 3.13a4 4 0 0 1 0 7.75'],
  chevron: ['m6 9 6 6 6-6'],
  refresh: ['M21 12a9 9 0 1 1-3-6.7L21 8', 'M21 3v5h-5'],
  play: ['m6 4 14 8-14 8z'],
  stop: ['M6 6h12v12H6z'],
  archive: ['M21 8v13H3V8', 'M1 3h22v5H1z', 'M10 12h4'],
  check: ['M20 6 9 17l-5-5'],
  ticket: ['M3 9V7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 6v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-6Z', 'M13 5v14'],
  navigate: ['m3 11 19-9-9 19-2-8z'],
  copy: ['M8 8h12v12H8z', 'M4 16V4h12'],
  sun: ['M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0', 'M12 2v2', 'M12 20v2', 'm4.9 4.9 1.4 1.4', 'm17.7 17.7 1.4 1.4', 'M2 12h2', 'M20 12h2', 'm6.3 17.7-1.4 1.4', 'm19.1 4.9-1.4 1.4'],
  back: ['m12 19-7-7 7-7', 'M19 12H5'],
  globe: ['M12 12m-10 0a10 10 0 1 0 20 0a10 10 0 1 0-20 0', 'M2 12h20', 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'],
  gear: ['M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z', 'M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0'],
  database: ['M12 5m-9 0a9 3 0 1 0 18 0a9 3 0 1 0-18 0', 'M3 5v14a9 3 0 0 0 18 0V5', 'M3 12a9 3 0 0 0 18 0'],
  info: ['M12 12m-10 0a10 10 0 1 0 20 0a10 10 0 1 0-20 0', 'M12 16v-4', 'M12 8h.01'],
}

export function Icon({ name, size = 18, stroke = 2, style }) {
  const d = PATHS[name] || []
  return h('svg', {
    xmlns: 'http://www.w3.org/2000/svg', width: size, height: size, viewBox: '0 0 24 24',
    fill: 'none', stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round',
    style: { flexShrink: 0, ...style }, 'aria-hidden': true,
  }, ...d.map((p, i) => h('path', { key: i, d: p })))
}

// ─────────────────────────────────────────────────────────────────────────────
// Small components
// ─────────────────────────────────────────────────────────────────────────────

/** Deterministic pleasant colour for an avatar or a photo fallback. */
export function hue(seed) {
  let x = 0
  for (const ch of String(seed || '')) x = (x * 31 + ch.charCodeAt(0)) >>> 0
  return x % 360
}

export function avatarBg(seed) {
  return `hsl(${hue(seed)} 48% 46%)`
}

export function fallbackGradient(seed) {
  const a = hue(seed)
  return `linear-gradient(135deg, hsl(${a} 55% 62%), hsl(${(a + 40) % 360} 60% 48%))`
}

export function Pill({ children, dark, small, selected, onClick, title, className, style, disabled, shadow }) {
  const cls = ['td-pill', dark ? 'td-dark' : '', small ? 'td-sm' : '', selected ? 'td-selected' : '', shadow ? 'td-shadow-pill' : '', className || ''].join(' ')
  return h('button', { type: 'button', className: cls, onClick, title, style, disabled }, ...[].concat(children))
}

export function IconButton({ name, onClick, title, className, style, size = 18 }) {
  return h('button', { type: 'button', className: ['td-iconbtn', className || ''].join(' '), onClick, title, style, 'aria-label': title },
    h(Icon, { name, size }))
}

export function Avatar({ member, size, showState }) {
  const letter = memberLetter(member)
  const cls = ['td-avatar', size || '', letter.length > 1 ? 'mono' : ''].join(' ')
  return h('span', { className: cls, style: { background: avatarBg(member.id || member.title) }, title: memberTitle(member) },
    letter,
    showState ? h('span', { className: ['dot', member.state || ''].join(' ') }) : null)
}

/** Overlapping team avatars; `max` faces then a "+N" chip. */
export function Avatars({ members, max = 4, onClick, size }) {
  const shown = members.slice(0, max)
  const rest = members.length - shown.length
  return h('button', {
    type: 'button', onClick, className: 'td-avatars', title: t('team_n', { n: members.length }),
    style: { border: 0, background: 'transparent', padding: 0, cursor: onClick ? 'pointer' : 'default' },
  },
  ...shown.map((m) => h(Avatar, { key: m.id || m.title, member: m, size, showState: true })),
  rest > 0 ? h('span', { className: 'more' }, `+${rest}`) : null)
}

/** Map legend: numbered order + the dark "住" pin. */
export function Legend() {
  return h('span', { className: 'td-legend' },
    h('span', { className: 'k' }, '1'), h('span', { className: 'k' }, '2'), t('legend_order'),
    h('span', { className: 'k stay', style: { marginLeft: 6 } }, t('pin_stay')), t('legend_stay'))
}

/** A photo tile with a numbered badge, an optional tag and a gradient fallback. */
export function Photo({ src, alt, num, tag, className, style, seed }) {
  const letter = (String(alt || '').match(/[\u4e00-\u9fff]/) || [String(alt || '?').slice(0, 1)])[0]
  return h('div', { className: ['td-photo', className || ''].join(' '), style },
    src
      ? h('img', { src, alt: alt || '', loading: 'lazy', onError: (e) => { e.currentTarget.style.display = 'none' } })
      : null,
    h('div', { className: 'fallback', style: { background: fallbackGradient(seed || alt), zIndex: src ? -1 : 0 } }, letter),
    num != null ? h('span', { className: 'num' }, String(num)) : null,
    tag ? h('span', { className: 'tag' }, tag) : null)
}
