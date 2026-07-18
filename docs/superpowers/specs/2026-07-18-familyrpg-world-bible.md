# familyrpg — World Bible v0 (gazetteer + source map spec)

The foundation for the familyrpg campaign world, drawn from a hand-map by Kyle
and his kids. This is the **text source of truth**; the SVG world map
(`games/familyrpg/content/maps/world-map.svg`) is the **visual source of truth**
derived from it. Everything downstream — the engine node map (`region.yaml`),
points of interest, travel times — is carved from these two.

Continent is **unnamed** for now (working map title: "The Known World") — Kyle
and the kids get to name it. Names marked ★ are Claude-coined placeholders open
to redline. `familyrpg` itself is still a placeholder game name.

## The frame: seas & water

- **North Sea** (north) and **South Sea** (south) bound the continent; open ocean
  wraps the rest.
- ★**Heartmere** — a great **inland lake** at the heart of the continent (an
  island or two dot it). It is a *catchment*: it collects the land's runoff and
  drains to the oceans. (Could be renamed; needn't read as a "sea." Alts: the
  Kettle, Mirrenmere.)
- **Hydrology** (per Kyle): rain/runoff flows *into* Heartmere; Heartmere drains
  *out* to the seas.
  - **North River** — flows *in* to Heartmere from the northern highlands (inflow).
  - **East River** — drains *out* of Heartmere's east side, past **Bridgeton**
    (the Bridge), curving to the east coast near **Eastharbor**.
  - **South River** — drains *out* of Heartmere's south side, past **Ironford**
    (its big bridge), down to the **South Sea**.

## Peoples & holds (who lives where)

| People | Region | Seat(s) | Notes |
|---|---|---|---|
| **Humans** | the Plains (south-center) | Kingsreach · Bridgeton · Eastharbor | Unified *against* the other races but have **no king** — three **free city-states**, each ruled by a **Duke** (Eastharbor by a **Duchess**). |
| **Dwarves** | White Cliff Mountains (SW) | **Ironford** (capital) · Westharbor | Peaceful, inventive, fiercely protective of their land. Big bridge at Ironford over the South River. |
| **Gnomes** | the Tundra (north) | ★Cogwick | The dwarves' magitech partners; tinkerers. |
| **Elves** | the Forest (east) | — | Woodland folk of the eastern forest. |
| **Tieflings** | the Volcano (west) | **Ashhaven** | Fire-touched; now a playable race (CHA/INT, heat-shrugging). Oliver's favorite. |
| **Orcs / half-orcs** | the Orc Camp (central) | Orc Camp | A wilder people on the neck of land by Heartmere. |
| **Dragonborn** | **Dragon Isle** (offshore SW) | ★Emberport | A small dragonborn **fishing town** on the mountain-island where the **dragons** dwell. |
| **Tortle** | the **Turtle Islands** (SE) | ★Shellhaven | Turtle-folk of the southeastern isles. |

**Westharbor** (renamed from the kids' "Port-Town") — a **dwarf-led but
mixed-race** coastal town, SW.

**Unplaced races — deliberate room for possibility** (do NOT force onto the map):
halfling, half-elf, tabaxi, aarakocra, goliath, lizardfolk, firbolg, kenku. Light
future hooks (not canon yet): aarakocra ↔ the storm-isle cliffs; halflings among
the plains humans; goliath ↔ the high White Cliffs; a marsh for lizardfolk TBD.

## Settlements

**Free human city-states (each a Duke's/Duchess's seat):**
- **Kingsreach** — south coast, the plains; a walled castle-city; the lead city
  (keeps the trade road). Duke.
- **Bridgeton** — Heartmere's east-river mouth, guarding the Bridge. Duke.
- **Eastharbor** — east coast. Ruled by *the* **Duchess**.

**Dwarven:**
- **Ironford** — dwarf **capital**, White Cliff Mountains; big bridge over the
  South River.
- **Westharbor** — dwarf-led, mixed-race coastal town.

**Others:**
- **Ashhaven** — tiefling town at the Volcano.
- **Stormhaven** — free port on the main **Storm Isle** (SE); storm-lashed,
  mixed seafarers (aarakocra a candidate majority).
- ★**Emberport** — dragonborn fishing town, Dragon Isle.

**Minor towns (light — just getting ahead of it, don't scope deeply):**
- ★**Greenhollow** — small plains farming village between Kingsreach and Bridgeton
  (reuses the engine skeleton's town name — nice continuity).
- ★**Cogwick** — gnome tinker-town in the tundra.
- ★**Rivergate** — river/logging town on the East River at the forest's edge.
- ★**Shellhaven** — tortle village on the Turtle Islands.

## The Ironline — dwarven magitech railway ★

The dwarves (with gnome tinker-craft) run a **magitech railway** as the spine of
their peaceful, watchful northern frontier:
- From **Ironford** north along the mountains' flank into the **Tundra**,
- across the **North River** (a magitech span),
- anchored by two frontier forts: ★**Wastewall** (a camp/wall guarding against
  the **Wasteland**, NW) and ★**Elfward** (the elf-border fort, E).
- Purpose: move goods and troops, and watch the borders. Defensive, not
  aggressive — the dwarves are protective, not expansionist.

## Roads (major)

- ★**The Free Road** — the human league's trade road linking the three
  city-states: **Kingsreach → Greenhollow → Bridgeton → Eastharbor**.
- ★**The West Road** — Bridgeton around Heartmere's south to **Ironford**, on to
  **Westharbor**.
- ★**The Forest Road** — Eastharbor into the elven forest (via Rivergate).
- (The kids' dashed lines on the original = these roads.)

## Scale

- Continent ≈ **1,100 miles** east–west, ≈ **750 miles** north–south — big, with
  lots of unmapped space left "for possibility."
- Overland travel ≈ **24 miles/day** (wagon/marching) — so crossing the whole
  continent is a multi-week journey; adjacent city-states are a **few days**
  apart. (Used later to set engine node-map edge `hours`.)
- The SVG map carries a **scale bar** (0–100–200 miles) and a **compass**.

---

## MAP LAYOUT SPEC (for the SVG artist — exact placement)

`viewBox="0 0 1600 1080"` (x → right, y → down). Landmass = one irregular blob
roughly x 150→1460, y 150→960, with a western-highland lobe and an eastern-forest
lobe and the plains/lake between (mirror the kids' drawing). Ocean fills the
margins; keep the interior open and uncluttered — leave breathing room.

Feature → approximate center (x, y) and how to render:

- **North Sea** label ~(800, 48); **South Sea** label ~(1150, 1040); ocean tint in margins.
- **Wasteland** ~(360, 255), with a **dashed frontier arc** cutting it off from the settled north (NW).
- **Volcano** peak icon ~(300, 430); **Ashhaven** (town dot + label) ~(365, 520); "Tieflings" ~(345, 470).
- **White Cliff Mountains** range of peaks along ~(230–520, 560–930); label "White Cliff Mountains · Dwarves" ~(300, 955).
- **Ironford** (capital — larger dot/star + label) ~(430, 700); **big bridge** glyph just south over the South River.
- **Westharbor** (town dot + label) ~(320, 890).
- **Tundra** band ~(560–900, 300–430); label "Tundra · Gnomes" ~(760, 330); **Cogwick** (small dot) ~(720, 372).
- **Heartmere** (inland lake — water ellipse) ~(560–780, 500–730) with a **small island** ~(685, 620); label ~(660, 615).
- **North River** — from ~(700, 150) at the north edge flowing *down into* Heartmere's north shore ~(690, 500) (arrow implies inflow).
- **Orc Camp** ~(600, 450) on the neck (small camp glyph + label).
- **Bridgeton** (human city dot + label) ~(815, 655) at Heartmere's east mouth; **Bridge** glyph ~(850, 625).
- **East River** — from Bridgeton ~(830, 650) curving E/NE to the sea near Eastharbor; label "East River" ~(1055, 590).
- **Eastharbor** (human city dot + label, note "Duchess") ~(1315, 560), east coast.
- **Forest** — pine icons filling the east lobe ~(950–1380, 320–540); label "Forest · Elves" ~(1120, 400).
- **Rivergate** (small dot) ~(1010, 585) at the East River/forest edge.
- **Plains** — open ground ~(720–1080, 730–930); label "Plains · Humans" ~(890, 835).
- **Greenhollow** (small dot) ~(880, 872).
- **Kingsreach** (human city — castle glyph + label) ~(720, 950), south coast.
- **South River** — Heartmere south shore ~(600, 720) curving SW past **Ironford** ~(440, 710) down to the South Sea ~(430, 970); label "South River" ~(505, 825).
- **The Ironline** (railway — a distinct ticked/dashed rail line, NOT a road): from Ironford ~(430, 680) north to ~(540, 430), then W–E across the top: west spur to **Wastewall** (fort glyph) ~(465, 335); east across the North River (cross at ~(700, 350)) to **Elfward** (fort glyph) ~(890, 380). Label "the Ironline · dwarven magitech railway".
- **Roads** (dotted lines, distinct from the rail): Free Road Kingsreach→Greenhollow→Bridgeton→Eastharbor; West Road Bridgeton→Ironford→Westharbor; Forest Road Eastharbor→Rivergate.
- **Storm Isles** — scatter of small isles ~(1150–1420, 660–930); **Stormhaven** (town dot) ~(1300, 770); label "Storm Isles / Stormhaven".
- **Turtle Islands** — island group ~(1220–1300, 850–930); **Shellhaven** (small dot) ~(1250, 895); label "Turtle Islands · Tortle".
- **Dragon Isle** — a small mountain-island offshore SW in the South Sea ~(200, 1000); **Emberport** (small dot) ~(210, 992); label "Dragon Isle · Dragons & Dragonborn".
- **Scale bar** bottom-right ~(1230–1450, 1005): "0 — 100 — 200 miles".
- **Compass rose** top-left corner ~(130, 210).
- **Title cartouche** (a corner): "The Known World" + small sub "familyrpg · source map v1".
- **Legend** (small corner box): capital (star) · city (large dot) · town (small dot) · fort · ▬▬ road (dotted) · + + railway · ~ river.
