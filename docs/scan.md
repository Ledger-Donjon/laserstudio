# Scan

Scanning is the key-feature of Laser Studio.
The concept is to synchronize the definition of zones on a spatial
representation of an element to test, and get the connected stage to perform
moving operations in order to position an element of the bench to a point of interest.

Laser Studio permits to define zones to scan and generates random points
within the defined zones that are .

## Defining zones

In order to define a zone to scan, you have to use the Zone definition tool.

Click and drag to define a rectangle that will be the region added to the
active zone. Press the SHIFT key while dragging to specify a rectangle that
will be removed from the active zone.

Each time the active zone is modified, the scan path is re-generated and
updated in the Viewer to show the 10 first points.

## Multiple scan zones

Scanning zones are organised as a list. Each zone has a name, a color and an
enabled flag, and can be created, renamed, recolored, enabled, disabled or
deleted independently.

One zone is _active_ at a time. The drawing tools always target the active
zone: dragging adds to it, and Shift-dragging subtracts from it. Other zones
are never modified by a drawing gesture. Drawing with no zone in the list
creates `Zone 1` first; adding a zone thereafter (via the "+" button or the
Scan tab's "Add zone" button) names it `Zone <n>`, where `<n>` is derived from
the highest existing `Zone <n>` name plus one — not a simple count — so
deleting a zone and adding another never reuses a name still in the list.

Point generation runs on the **union of the enabled zones**. Disabling a zone
excludes it from `go_next` without losing its shape, which makes it easy to try
a subset of the zones and put them back afterwards.

Enabled zones are drawn with a solid outline and a translucent fill in their own
color. A disabled zone is not drawn at all, unless it is the active zone — in
which case it appears as a dashed outline so that drawing into it stays visible.

Select the active zone from the combo box in the Scanning Zones toolbar of the
classic window, or from the zone list of the Scan tab in the new interface. The
zone list also holds the name field, the color swatch, the enable toggle and
the delete button for each zone.

Both windows share the same zone list, as does the {doc}`rest`.

## Scan zones over the API

The zone list is available through the {doc}`rest`:

- `GET /scangeometry/zones` — the zones and the active zone id
- `POST /scangeometry/zones` — create a zone (`name`, `color`, `enabled`,
  `geometry` are all optional); returns `{"id": <zone_id>, "zone": {...}}`
- `PATCH /scangeometry/zones/{zone_id}` — update any subset of those fields;
  returns `{"id": <zone_id>, "zone": {...}}`
- `DELETE /scangeometry/zones/{zone_id}` — delete a zone

Each zone carries a stable integer `id` assigned once at creation — the first
zone gets `id=1`, then `max(existing ids) + 1`. This is **not** a list
position: deleting a zone does not renumber the remaining ones. The `id` field
appears in the body of each zone object returned by `GET /scangeometry/zones`;
the URL path parameter `{zone_id}` refers to that same value.

Colors are returned as `#rrggbb` strings; `#rrggbbaa` is also accepted on
input, but the alpha byte is not persisted, so it will not survive a later
`GET`. `POST` and `PATCH` reject a malformed `color` or `geometry` with a
`400 INVALID_PARAMETER` error; a missing or deleted zone id returns `404
SCAN_ZONE_NOT_FOUND`. `PUT /scangeometry`, by contrast, is the same code path
used to load `settings.yaml`: a malformed zone entry there is skipped and
logged rather than rejected, so a bad entry elsewhere in the payload does not
prevent the rest of the file from loading.

`GET /scangeometry` returns `density`, `active`, the `zones` list and a
`geometry` key holding the flattened union of the enabled zones. `PUT
/scangeometry` accepts either the `zones` form or the historical single
`geometry` form, which loads as one zone.

`DELETE /scangeometry` deletes **every** zone, names and colors included — not
just their shapes. To empty a single zone's shape while keeping the zone, patch
it with `{"geometry": {"geometrycollection": null}}`.

With the {doc}`lsapi` client:

```python
from laserstudio.lsapi import LSAPI

lsapi = LSAPI()

# Create a disabled zone and switch it on later.
# add_scan_zone returns {"id": <zone_id>, "zone": {...}}; the id is stable.
zone_id = lsapi.add_scan_zone(name="Corner pads", color="#ff5300", enabled=False)["id"]
lsapi.update_scan_zone(zone_id, enabled=True)

# Scan only that zone by disabling the others.
# Iterate over the "id" field of each zone — do not use range(), because ids
# are stable integers starting at 1 and may not be contiguous after deletions.
for zone in lsapi.scan_zones()["zones"]:
    if zone["id"] != zone_id:
        lsapi.update_scan_zone(zone["id"], enabled=False)

lsapi.go_next()
```

## Go Next command

The Go Next command can be triggered by hitting the Go Next Button from the main toolbar.

It can also be triggered thanks to the REST API.
