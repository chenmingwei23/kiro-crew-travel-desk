/**
 * mapview.mjs — the immersive map view (design C): the whole panel is the
 * map; the trip switcher, day chips and team sit on top as floating pills; a
 * horizontal rail of photo cards along the bottom is linked to the pins; the
 * leader chat opens from a round button.
 */

import { createElement as h, useState, useEffect, useRef, useCallback } from 'react'
import { Icon, Pill, Photo, Avatars, Legend } from './theme.mjs'
import { TripMap } from './map.mjs'
import { ChatFloat, TeamPopover, TripSwitcher, MoreMenu } from './parts.mjs'
import { tripPoints, fmtShort, timeRange, localizeHost } from './data.mjs'
import { t } from './i18n.mjs'

function railItems(view, day) {
  const pts = tripPoints(view).filter((p) => day == null || p.day === day)
  const stops = pts.filter((p) => p.kind === 'stop').sort((a, b) => (a.day - b.day) || (a.order - b.order))
  const stays = pts.filter((p) => p.kind === 'stay').sort((a, b) => (a.day || 0) - (b.day || 0))
  if (day != null) return [...stops, ...stays]
  // all days: interleave each day's stops then its stay
  const out = []
  for (const d of (view.days || []).map((x) => x.day)) {
    out.push(...stops.filter((p) => p.day === d), ...stays.filter((p) => p.day === d))
  }
  return out
}

function RailCard({ point, selected, onClick, cardRef }) {
  const isStay = point.kind === 'stay'
  const place = isStay ? point.stay : point.place
  const title = isStay ? point.stay.name : point.place.name
  return h('div', { ref: cardRef, className: ['td-card', selected ? 'on' : ''].join(' '), onClick, role: 'button', tabIndex: 0,
    onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } } },
    h(Photo, {
      src: place.photo, alt: title, seed: isStay ? `stay-${point.stay.place_id}` : point.place.id,
      num: isStay ? null : point.order, tag: isStay ? t('stay_tag') : (timeRange(point.time, point.end) ? point.time : null),
    }),
    h('div', { className: 'nm', title }, title),
    h('div', { className: 'nt' }, isStay ? (point.stay.notes || t('stay_inout', { in: point.stay.check_in || '', out: point.stay.check_out || '' })) : (point.place.notes || '')),
    h('div', { className: 'ad' }, h(Icon, { name: 'pin', size: 12 }), h('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis' } }, place.address || '')))
}

export function MapView({ view, trips, hiddenTrips, currentId, onPickTrip, members, status, initialDay = null, initialSelected = null, onBack, onRefresh, onToast, onOpenSettings }) {
  const [day, setDay] = useState(initialDay)
  const [selected, setSelected] = useState(initialSelected)
  const [chatOpen, setChatOpen] = useState(false)
  const [teamOpen, setTeamOpen] = useState(false)
  const cardRefs = useRef(new Map())
  const railRef = useRef(null)

  useEffect(() => { setDay(initialDay); setSelected(initialSelected) }, [initialDay, initialSelected, view && view.trip && view.trip.id])

  const items = view ? railItems(view, day) : []
  const dayLabel = day == null ? t('all') : t('day_n', { n: day })

  const select = useCallback((point) => {
    setSelected(String(point.id))
    if (day != null && point.day != null && point.day !== day) setDay(point.day)
  }, [day])

  // Scroll the selected card into view.
  useEffect(() => {
    if (selected == null) return
    const el = cardRefs.current.get(String(selected))
    if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
  }, [selected, day])

  const trekUrl = view ? view.trip.url : (status && status.trek && status.trek.url)
  const stopsCount = items.filter((p) => p.kind === 'stop').length
  const padding = [150, chatOpen ? 460 : 60, items.length ? 340 : 60, 60]

  return h('div', { className: 'td-mapview' },
    h('div', { className: 'map' },
      view ? h(TripMap, { view, day, selected, onSelect: select, padding, fitKey: `${day}-${chatOpen}` })
        : h('div', { style: { position: 'absolute', inset: 0, background: '#EEF2F4' } })),

    // top-left: trip + day chips
    h('div', { className: 'td-ov tl' },
      h(TripSwitcher, { trips, current: currentId, onPick: onPickTrip, variant: 'map', hidden: hiddenTrips }),
      view ? h('div', { className: 'td-chips' },
        h(Pill, { small: true, shadow: true, selected: day == null, onClick: () => { setDay(null); setSelected(null) } }, t('all')),
        ...(view.days || []).map((d) => h(Pill, { key: d.day, small: true, shadow: true, selected: day === d.day, onClick: () => { setDay(d.day); setSelected(null) } },
          t('day_n', { n: d.day }), h('span', { className: 'sub' }, fmtShort(d.date))))) : null),

    // top-right: team, back, open, more
    h('div', { className: 'td-ov tr' },
      h('div', { style: { position: 'relative' } },
        h('div', { className: 'td-float', style: { display: 'flex', alignItems: 'center', gap: 10, padding: '6px 14px 6px 8px', borderRadius: 9999 } },
          h(Avatars, { members, max: 4, onClick: () => setTeamOpen((v) => !v) }),
          h('span', { style: { fontSize: 13, fontWeight: 600 } }, t('team_pill', { n: members.length }))),
        teamOpen ? h(TeamPopover, { members, onClose: () => setTeamOpen(false), style: { top: 52 } }) : null),
      h(Pill, { dark: true, onClick: onBack, title: t('back_to_trip_title') }, h(Icon, { name: 'list', size: 16 }), t('back_to_trip')),
      trekUrl ? h('a', { className: 'td-pill td-shadow-pill', href: localizeHost(trekUrl), target: '_blank', rel: 'noreferrer', style: { textDecoration: 'none' }, title: t('open_full_title') }, h(Icon, { name: 'external', size: 16 }), t('full_page')) : null,
      h('div', { className: 'td-float', style: { borderRadius: 9999 } }, h(MoreMenu, { trekUrl, onRefresh, onToast, onOpenSettings }))),

    // bottom: photo rail
    view && items.length ? h('div', { className: 'td-rail-wrap' },
      h('div', { className: 'td-rail-lbl' }, t('rail_label', { day: dayLabel, n: stopsCount }), h(Legend, null), h('span', null, t('rail_hint'))),
      h('div', { className: 'td-rail', ref: railRef },
        ...items.map((p) => h(RailCard, {
          key: p.id, point: p, selected: selected != null && String(p.id) === String(selected),
          onClick: () => select(p),
          cardRef: (el) => { if (el) cardRefs.current.set(String(p.id), el); else cardRefs.current.delete(String(p.id)) },
        })))) : null,

    // chat
    h('div', { className: 'td-ov br', style: { bottom: items.length ? 340 : 24, maxHeight: 'calc(100% - 120px)', display: 'flex', flexDirection: 'column', alignItems: 'flex-end' } },
      chatOpen
        ? h('div', { style: { height: `min(560px, calc(100vh - ${items.length ? 480 : 200}px))`, minHeight: 320 } }, h(ChatFloat, { members, onClose: () => setChatOpen(false) }))
        : h('button', { type: 'button', className: 'td-fab', onClick: () => setChatOpen(true), title: t('chat_fab'), 'aria-label': t('chat_fab'), style: { position: 'relative' } },
          h(Icon, { name: 'chat', size: 24 }),
          h('span', { className: 'badge' }))))
}
