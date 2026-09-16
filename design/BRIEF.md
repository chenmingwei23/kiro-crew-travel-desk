# Trip page — design brief

The Travel Desk page is where the user reads a trip, sees it on a map, and talks
to the Tour Leader. This brief records the two decisions that shaped it.

## Why the app draws the trip page itself

The trip data lives in a self-hosted trip planner (TREK). The obvious shortcut
is to embed the planner's own web UI in an iframe next to a chat panel. We do
not do that, for three reasons:

- Look and feel. The planner's UI is built for editing, not for reading a
  finished trip. Embedded, it does not match the dashboard and reads as a
  bolted-on tool rather than part of the app.
- Reliability. An iframe couples the page to whatever the planner renders and to
  its cross-origin and framing rules; when the planner is slow, restarting, or
  refuses to be framed, the page shows an empty box.
- Control. The interesting content — photos, a clean day-by-day timeline, a map
  with the day's route — is ours to compose. Reading it out of the planner's API
  and drawing it ourselves gives a page we can make calm and photo-first, in
  both interface languages, without fighting someone else's layout.

So the page reads the trip from the planner's REST API and renders its own view.
The planner remains the system of record and stays directly usable for editing;
"open the full itinerary" is a secondary action that hands off to it.

## Layout families considered

Three layouts were prototyped before settling on the current page.

1. List and map. A scrollable list of stops grouped by day on one side, a sticky
   map on the other. Strong for scanning and for a self-drive route, but the map
   competes with the list for space and the page reads as a search result.
2. Editorial detail page. A full-width hero, then a centred long read: day
   sections with large photo cards in a timeline, a small "today's route" map per
   day, and a sticky chat card. Reads like a magazine feature; the map is a
   supporting element. This is the family the current page follows.
3. Map-first. The whole page is a map with a floating card rail along the bottom
   and floating controls. Immersive and low on text, better for looking than for
   reading a plan in detail.

The page keeps operational controls (start, stop, restart, backup the trip
service) out of the main view and behind Settings, so the reading experience
stays uncluttered.
