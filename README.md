# Numismatics Aeronautics Bridge

A NeoForge addon for Minecraft 1.21.1 that exposes Create Aeronautics (Simulated)
Docking Connectors as buffered item or fluid targets for Create: Numismatics SalePoints.

## Requirements

- Minecraft 1.21.1
- Java 21
- NeoForge 21.1.247 or a compatible 21.1 release
- Create 6.0.10+
- Create: Numismatics 1.1.0+
- Create Aeronautics bundle (includes the Simulated module)
- Sable, as required by Create Aeronautics

## Setup

1. Place and extend two Docking Connectors so that they lock together.
2. Take a fresh SalePoint block item (one without a target selected).
3. Sneak-right-click a Docking Connector with that SalePoint item to switch its mode.
   The default mode is item sales; sneak-right-click switches between items and fluids.
4. With the SalePoint item no longer sneaking, right-click the connector to select it.
5. Place the SalePoint within the normal Numismatics target range.
6. Empty both connector inventories/tanks before enabling the SalePoint, then configure
   the filter and price and supply stock through either end of the connected pair.

## Transfer behavior

While an item SalePoint controls one end of the docked pair, incoming item insertions
through either connector are captured by the SalePoint buffer. Automation cannot
extract that buffered stock. Once a purchase succeeds, the purchased items are
inserted into the paired connector's receiving inventory.

In fluid mode, incoming fluid transfers through either end are redirected into the
SalePoint fluid buffer. The fluid is inserted into the paired connector's tank only
after a successful purchase.

Each Docking Connector can be bound to one SalePoint resource type at a time because
Numismatics exposes a single target behaviour slot per block entity. To sell items and
fluids simultaneously through one connected pair, configure one endpoint for item sales
and the opposite endpoint for fluid sales, then bind a separate SalePoint to each.
Alternatively, use two independent connector pairs.

Changing the mode is blocked while that connector is already bound to a SalePoint.
Shift + right-click with a selected SalePoint item retains Numismatics' normal
clear-selection behavior.

The addon does not add blocks or change docking physics.
