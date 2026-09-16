/**
 * map.mjs — TripMap: a Leaflet map that draws a trip's stops as white
 * capsule pins (Airbnb price-pill style), the night's stay as a dark pin, and
 * one route per day. Prop-driven: pass the trip view, an optional day filter
 * and the selected point; get clicks back through onSelect.
 */

import { createElement as h, useEffect, useRef } from 'react'
import { useLeaflet, tripPoints, dayRoute, TILE_URL, TILE_ATTR } from './data.mjs'
import { T } from './theme.mjs'
import { t, useLang } from './i18n.mjs'

function pinHtml(point, opts) {
  const cls = ['td-pin', point.kind === 'stay' ? 'stay' : '', opts.selected ? 'on' : '', opts.dim ? 'dim' : ''].join(' ')
  const label = point.kind === 'stay' ? t('pin_stay') : String(point.order)
  return `<span class="${cls}">${label}</span>`
}

/**
 * @param {object} p
 * @param {object} p.view      trip view from GET /trip
 * @param {number|null} p.day  only this day is emphasised (others dimmed); null = all
 * @param {string|null} p.selected  point id ("26" for a stop, "stay-40" for a stay)
 * @param {function} p.onSelect(point)
 * @param {boolean} p.interactive  scroll/drag; false for the small day maps
 * @param {Array} p.padding   [top, right, bottom, left] px kept clear when fitting
 * @param {string} p.fitKey   change to re-fit bounds
 */
export function TripMap({ view, day = null, selected = null, onSelect, interactive = true, padding = [40, 40, 40, 40], fitKey, zoomControl = true, className, style }) {
  const elRef = useRef(null)
  const mapRef = useRef(null)
  const layerRef = useRef(null)
  const markersRef = useRef(new Map())
  const { L, failed } = useLeaflet()
  const lang = useLang() // the stay pin's label is text inside a divIcon; redraw on switch

  // Create the map once Leaflet is here.
  useEffect(() => {
    if (!L || !elRef.current || mapRef.current) return undefined
    const map = L.map(elRef.current, {
      zoomControl: false,
      attributionControl: true,
      scrollWheelZoom: interactive,
      dragging: interactive,
      touchZoom: interactive,
      doubleClickZoom: interactive,
      boxZoom: false,
      keyboard: interactive,
      zoomSnap: 0.5,
    })
    map.getContainer().classList.add('td-leaflet')
    if (zoomControl && interactive) L.control.zoom({ position: 'topleft' }).addTo(map)
    L.tileLayer(TILE_URL, { attribution: TILE_ATTR, maxZoom: 19, className: 'td-tiles' }).addTo(map)
    layerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map
    map.setView([0, 0], 2)
    const ro = new ResizeObserver(() => { try { map.invalidateSize({ pan: false }) } catch (err) { /* torn down */ } })
    ro.observe(elRef.current)
    return () => {
      ro.disconnect()
      try { map.remove() } catch (err) { /* already gone */ }
      mapRef.current = null
      layerRef.current = null
      markersRef.current = new Map()
    }
  }, [L]) // eslint-disable-line react-hooks/exhaustive-deps

  // Draw pins + routes whenever data, day filter or selection changes.
  useEffect(() => {
    const map = mapRef.current; const layer = layerRef.current
    if (!L || !map || !layer || !view) return
    layer.clearLayers()
    markersRef.current = new Map()

    const days = (view.days || []).map((d) => d.day)
    for (const dn of days) {
      const route = dayRoute(view, dn)
      if (route.length < 2) continue
      const active = day == null || day === dn
      L.polyline(route, {
        color: active ? T.text : '#9a9a9a',
        weight: active ? 3 : 2,
        opacity: active ? 0.85 : 0.45,
        dashArray: active ? null : '5 7',
        lineJoin: 'round',
      }).addTo(layer)
    }

    const pts = tripPoints(view)
    // stays first so numbered stops sit above them when they overlap
    pts.sort((a, b) => (a.kind === 'stay' ? -1 : 1) - (b.kind === 'stay' ? -1 : 1))
    for (const p of pts) {
      const dim = day != null && p.day !== day
      const isSel = selected != null && String(p.id) === String(selected)
      const icon = L.divIcon({ html: pinHtml(p, { selected: isSel, dim }), className: '', iconSize: [0, 0], iconAnchor: [0, 0] })
      const m = L.marker([p.lat, p.lng], { icon, zIndexOffset: isSel ? 1000 : (p.kind === 'stay' ? 0 : 100), riseOnHover: true })
      const title = p.kind === 'stay' ? p.stay.name : p.place.name
      m.bindTooltip(title, { direction: 'top', offset: [0, -18], opacity: 0.95, className: 'td-tip' })
      if (onSelect) m.on('click', () => onSelect(p))
      m.addTo(layer)
      markersRef.current.set(String(p.id), m)
    }
  }, [L, view, day, selected, onSelect, lang])

  // Fit to the emphasised day (or everything) when asked.
  useEffect(() => {
    const map = mapRef.current
    if (!L || !map || !view) return
    const pts = tripPoints(view).filter((p) => day == null || p.day === day)
    if (!pts.length) return
    const [pt, pr, pb, pl] = padding
    if (pts.length === 1) {
      map.setView([pts[0].lat, pts[0].lng], 13, { animate: false })
      return
    }
    const bounds = L.latLngBounds(pts.map((p) => [p.lat, p.lng]))
    map.fitBounds(bounds, { paddingTopLeft: [pl, pt], paddingBottomRight: [pr, pb], maxZoom: 13, animate: false })
  }, [L, view && view.trip && view.trip.id, day, fitKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // Bring a newly selected pin into view.
  useEffect(() => {
    const map = mapRef.current
    if (!L || !map || selected == null) return
    const m = markersRef.current.get(String(selected))
    if (!m) return
    const ll = m.getLatLng()
    if (!map.getBounds().pad(-0.15).contains(ll)) map.panTo(ll, { animate: true, duration: 0.6 })
  }, [L, selected])

  return h('div', { className, style: { position: 'relative', width: '100%', height: '100%', ...style } },
    h('div', { ref: elRef, style: { position: 'absolute', inset: 0 } }),
    !L && !failed ? h('div', { style: { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.muted, fontSize: 13, background: '#EEF2F4' } }, t('map_loading')) : null,
    failed ? h('div', { style: { position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.muted, fontSize: 13, background: '#EEF2F4', padding: 24, textAlign: 'center' } }, t('map_failed')) : null)
}
