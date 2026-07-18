# familyrpg — World Bible v1 (gazetteer + source map spec)

The foundation for the familyrpg campaign world, drawn from a hand-map by Kyle
and his kids and iterated with him. This is the **text source of truth**; the SVG
world map (`games/familyrpg/content/maps/world-map.svg`) is the **visual source of
truth** derived from it. The engine node map (`region.yaml`), points of interest,
and travel times are carved from these two.

Continent is **unnamed** (Kyle + kids to name it). Names marked ★ are
Claude-coined placeholders open to redline. `familyrpg` is a placeholder game name.

## Shape & frame

- The continent is **vaguely heart-shaped** (two top lobes — NW highlands, NE
  forest — a top-center cleft where the North River enters, tapering to a rounded
  southern point at Kingsreach), per the family's source drawing.
- **North Sea** (north), **South Sea** (south), **Ocean** (east & west) wrap it.
- **Territory shading is contiguous** — each people's land touches the next,
  divided vaguely along biome and river lines. **The Human Plains is the largest
  territory** and the connective tissue bordering all the others.

## Water

- ★**Heartmere** — the great **inland lake** at the center (an island or two dot
  it). Alts: the Kettle, Mirrenmere.
- **North River** — enters at the top-center cleft from the northern highlands and
  runs down to Heartmere. The **Ironline** crosses it at **Cogwick** on a big
  fancy dwarven-gnomish **bridge** (a **gnomish fort**, ★Gearwatch, guards it).
- **East River** — runs from Heartmere/Bridgeton east and **reaches the eastern
  shore**; Rivergate sits on it at the forest's edge.
- **West River** (the river the dwarves own) — runs from Heartmere southwest
  **through the mountains**, past **Ironford** (its big bridge) and **Westharbor**,
  to the western shore. A **mountain pass** follows the river; a dwarven
  **checkpoint** (★Stonewatch) guards the range's mouth.
- (Do NOT annotate inflow/outflow on the map — just draw the rivers naturally.)

## Major territories (contiguous; sizes matter)

| Territory | People | Size | Notes |
|---|---|---|---|
| **The Plains** | Humans | **largest** | Central-south-east body of the heart, down to the southern point. Three free city-states. |
| **White Cliff Mountains** | Dwarves | large | The western/SW arm. West River + pass run through it. |
| **The Forest** | Elves | large | The NE lobe. |
| **The Tundra** | Gnomes | medium | North-center, between the lobes, around the North River. |
| **The Volcano (Ashhaven)** | Tieflings | **small** | A small western patch — the volcano itself. |
| **The Wasteland** | (hostile — Orcs) | medium | NW; **extends to the water**. Holds the Orc Warcamp. Unclaimed/menacing. |
| **East Islands** | Tortle | — | Offshore SE archipelago. |
| **West Island (Dragon Isle)** | Dragons & Dragonborn | — | Offshore west/SW. |

**Half-orcs** are a **sparse, scattered population** with **no town of their own**.
The **Orc Warcamp** is a **hostile, pure-Ork wasteland warcamp** — a threat, not a
friendly settlement.

**Unplaced races — deliberate room for possibility** (don't force onto the map):
halfling, half-elf, tabaxi, aarakocra, goliath, lizardfolk, firbolg, kenku. Light
hooks: aarakocra ↔ the lonely storm-rock port (Stormhaven); halflings among the
plains humans; goliath ↔ the high White Cliffs.

## Settlements

**Free human city-states (each a Duke's/Duchess's seat), the Plains:**
- **Kingsreach** — southern point, coast; walled castle-city; the lead city. Duke.
- **Bridgeton** — Heartmere's SE mouth, guarding the East River bridge. Duke.
- **Eastharbor** — east coast. Ruled by *the* **Duchess**.

**Dwarven, the mountains:**
- **Ironford** — dwarf **capital**, sited right at the mountains/West River/its big
  bridge.
- **Westharbor** — dwarf-led, mixed-race town, up the **West River inside the
  mountains** (on the pass).
- ★**Stonewatch** — dwarven checkpoint at the mountain pass's mouth.

**Others:**
- **Ashhaven** — the **walled tiefling town built into the Volcano**.
- ★**Cogwick** — gnome town on the **Ironline and the North River**, at the fancy
  rail-bridge; ★Gearwatch gnomish fort at the crossing.
- ★**Emberport** — dragonborn fishing town, **Dragon Isle** (west island).
- **Stormhaven** — a lonely storm-lashed rock port in the eastern waters (minor).

**Minor towns (light — getting ahead of it):**
- ★**Millbrook** — a **cute little starter village** on the **West Road**, in the
  plains-to-mountains transition (a natural PC starting point).
- ★**Greenhollow** — small plains farming village (reuses the engine skeleton
  town name).
- ★**Rivergate** — river/logging town on the East River at the forest's edge.
- ★**Shellhaven** — tortle village, East Islands.
- ★**Duskhold** — a **cursed, ruined city and castle** in the SE, with a road to
  it (a dungeon-shaped adventure hook; fallen and shunned).

## The Ironline — dwarven magitech railway ★

The dwarves' (gnome-assisted) magitech rail — the spine of their peaceful,
watchful frontier:
- From **Ironford** (mountains) it runs north and **dives underground through the
  Wasteland** — a magitech **subway** (WoW-deeprun-tram style) — with a
  ★**Wasteland Outpost** stop and the fort ★**Wastewall** at the tunnel mouth.
- It surfaces in the **Tundra**, crosses the **North River at Cogwick** on the big
  fancy bridge (gnomish fort **Gearwatch**),
- and continues east to the fort ★**Elfward** at the elf-forest border.
- Defensive, inventive, protective — not expansionist.

## Roads (major, dotted)

- ★**The Free Road** — human league trade road: **Kingsreach → Greenhollow →
  Bridgeton → Eastharbor**.
- ★**The West Road** — Bridgeton → **Millbrook** → **Ironford** → (mountain pass) →
  Westharbor.
- ★**The Forest Road** — Eastharbor → Rivergate → into the forest.
- ★**The Duskhold Road** — a lonely spur off the Free Road running SE to the cursed
  ruin of Duskhold.

## Scale (assessed for family-play feasibility)

- Continent ≈ **550 miles** east–west, ≈ **430 miles** north–south — a "small
  continent / great island." Lots of unmapped space remains "for possibility."
- Overland ≈ **24 miles/day** (foot/wagon); the **magitech rail ≈ 120 miles/day**.
- Consequences (the point of this scale): neighboring regions are **a few days'
  walk** apart; the **whole world is crossable in ~3 weeks on foot**; the rail is a
  **beloved fast-travel** (a day between forts vs a week walking) — a real
  story-lever the kids will love. (Used later to set node-map edge `hours`.)
- Map carries a **scale bar** (0–50–100 miles) and a small **compass**.

---

## MAP LAYOUT SPEC (for the SVG artist — read literally)

`viewBox="0 0 1600 1080"` (x → right, y → down). Draw the landmass as ONE organic,
**vaguely heart-shaped** continent: two rounded top lobes (NW ~x400,y210 and
NE ~x1150,y210), a top-center cleft ~(760, 300) where the North River enters,
sides bulging out to ~(190, 560) west and ~(1410, 560) east, tapering to a rounded
southern point ~(770, 950). Coastline hand-drawn/organic (not geometric). Ocean
fills the margins. **Territory fills must be contiguous** (touching along biome/
river lines), muted house tints, organic boundaries — NOT rectangular patches.

**Removed from the previous version:** the top-left title/cartouche box (gone
entirely), all river inflow/outflow arrows and drainage text. **Legend** goes in
the OCEAN margin (e.g. lower-right water), never over land. **Compass** top-left,
SMALL (~half the previous size).

Territory fills (contiguous, human largest):
- **The Wasteland** — NW, reaching the NW/W ocean; a **dashed frontier arc** on its
  inland (SE) side; barren tint. Holds **Orc Warcamp** (a hostile camp glyph +
  label) ~(330, 430).
- **The Volcano / Ashhaven** (tiefling) — small W patch ~(300, 570): a volcano with
  a **walled town built into it**; single label "**Ashhaven** · Tieflings".
- **White Cliff Mountains** (dwarf) — SW arm, peaks ~(220–540, 560–900); label
  "White Cliff Mtns · Dwarves".
- **The Tundra** (gnome) — N-center between the lobes ~(560–920, 300–480); label
  "The Tundra · Gnomes".
- **The Forest** (elf) — NE lobe, pines ~(920–1380, 270–560); label "The Forest ·
  Elves".
- **The Plains** (human, LARGEST) — the big central-south-east body ~(560–1320,
  540–940); label "The Plains · Humans".

Settlements & features (place at these centers):
- **Ironford** (capital — ember star + label "dwarf capital") ~(475, 690), sited on
  the mountains at the **West River** with a **bridge glyph** on the river beside it.
- **West River** — from Heartmere's SW ~(650, 690) running SW **through the
  mountains** past Ironford and **Westharbor** ~(365, 770) to the W shore ~(235,
  845); a faint **mountain-pass** line following the river; **Stonewatch**
  (dwarven checkpoint, small fort glyph) ~(560, 720) at the range's mouth.
- **Heartmere** (inland lake, water fill) ~(620–830, 500–700) with a small island
  ~(720, 600); label "Heartmere".
- **North River** — from the cleft ~(760, 300) down to Heartmere ~(735, 500);
  crossed at **Cogwick** ~(775, 405) by the **Ironline** on a **big fancy bridge**
  with **Gearwatch** (gnomish fort glyph) at the crossing.
- **East River** — from Bridgeton ~(845, 640) curving E and **reaching the eastern
  shore** ~(1405, 645); **Rivergate** (small dot) ~(1035, 590) at the forest edge.
- **Bridgeton** (free city — ringed dot + ducal pennant, label "Duke") ~(835, 640)
  at Heartmere's SE, bridge glyph on the East River.
- **Eastharbor** (free city — ringed dot + pennant, label "the Duchess") ~(1330,
  600) on the east coast — **keep the label clear of other elements** (previous
  version had an overlap glitch here).
- **Kingsreach** (free city — castle glyph + label "Duke · lead city") ~(770, 915)
  at the southern point/coast.
- **Greenhollow** (small dot) ~(950, 800), plains.
- **Millbrook** (small dot, label "starter village") ~(600, 820) on the West Road.
- **Duskhold** (a **ruined city + broken castle** glyph, label "cursed ruin")
  ~(1180, 860), SE plains, with the **Duskhold Road** (dotted spur) reaching it.
- **The Ironline** (ticked/crosstied RAILWAY, distinct from dotted roads): from
  Ironford ~(475, 665) north; the stretch **through the Wasteland is UNDERGROUND**
  — render as a **tunnel** (e.g. dashed/hollow rail or a dotted-tunnel style
  clearly different from the surface rail), with **Wastewall** (fort, tunnel mouth)
  ~(430, 500) and **Wasteland Outpost** (small stop glyph) ~(400, 405); it
  surfaces and runs E through the tundra to **Cogwick** ~(775, 405) (fancy North
  River bridge + Gearwatch), then E to **Elfward** (fort) ~(955, 420) at the elf
  border. Label "the Ironline · dwarven magitech railway".
- **Roads** (dotted, clearly distinct from the rail): Free Road (Kingsreach→
  Greenhollow→Bridgeton→Eastharbor); West Road (Bridgeton→Millbrook→Ironford→
  Westharbor, following the pass); Forest Road (Eastharbor→Rivergate→forest);
  Duskhold Road (Free Road→Duskhold).
- **Dragon Isle** (west island) — a small mountain-island offshore W/SW ~(150,
  760); **Emberport** (small dot) ~(160, 752); label "Dragon Isle · Dragons &
  Dragonborn".
- **East Islands** (Tortle) — an archipelago offshore SE ~(1200–1420, 780–960);
  **Shellhaven** (small dot) ~(1300, 870); label "East Islands · Tortle".
- **Stormhaven** — a single lonely storm-rock port ~(1440, 720) in the eastern
  waters (minor dot + label).

Map furniture:
- **Compass rose** — top-left ocean, SMALL ~(140, 200).
- **Scale bar** — an ocean corner (e.g. bottom-left or bottom-right water):
  "0 — 50 — 100 miles".
- **Legend** — in the OCEAN (lower-right water preferred), not over land: capital
  (star) · free city (ringed dot) · town (small dot) · fort · ruin · ▬▬ road
  (dotted) · +++ railway · ═ underground rail · ~ river.
- **Sea labels**: North Sea, South Sea, Ocean (E & W).
- Spelling exact: **Eastharbor**, **Westharbor** (both "-harbor").

---

## v3 REDLINE (applies ON TOP of everything above — these win on conflict)

**Region renames** (region title changes; the "· People ·" subtitle stays):
- "The Forest" → **Deepwoods** (· Elves ·)
- "The Plains" → **Great Plains** (· Humans ·)
- "The Tundra" → **Northland Tundra** (· Gnomes ·)

**Geography / composition fixes:**
1. **Continent bottom = a POINT (heart's bottom point), not two rounded lobes.**
   v2's southern coast reads as a "butt" (two bulges with a dip). Redraw the
   southern coast tapering to a single rounded **point** at the bottom-center,
   with **Kingsreach** at or just above that point. Keep the two TOP lobes + top
   cleft — a proper heart.
2. **Westharbor moves to the COAST** — exactly where the **West River meets the
   sea at the foot of the mountains** (the river's SW sea-mouth). It is a
   harbor, so it must be on the water, not inland. The West River runs from
   Heartmere through the mountains and empties at Westharbor on the SW coast.
3. **The East Islands (Tortle) must read as clearly-separate OFFSHORE islands**
   in the SE water — distinct from **Duskhold**, which is on the **mainland** SE
   coast. In v2 they're jumbled together. Separate them: pull Duskhold onto the
   mainland (with its road), and set the Tortle **East Islands + Shellhaven** as
   their own island group out in the water with clear sea between them and the
   coast. Give the group ONE clean "East Islands · Tortle" label and a Shellhaven
   town dot on an island.
4. **Dragon Isle label** — its text is cramped/overlapping the island's mountain
   in v2. Lay the label cleanly (name + "Dragons & Dragonborn" + Emberport)
   beside/below the island with no overlap on the art.

**Label anti-collision (the reviewer must verify every one of these):**
- **Cogwick** and **Gearwatch** overlap near the rail bridge — separate them so
  both names + the bridge/fort read cleanly.
- **Eastharbor** — nudge the label a bit right / clear so nothing crosses it.
- **Deepwoods "· Elves ·"** subtitle has a **tree glyph drawn on top of it** —
  move the label (or clear the trees behind it) so the text is clean.
- General: no place-name may be crossed by a tree, road, rail, river, or another
  label. Legible at full size is the bar.
