# Numismatics Aeronautics Bridge

A small NeoForge addon for Minecraft 1.21.1 that exposes the Create Aeronautics
(Simulated) Docking Connector as an item target for Create: Numismatics SalePoints.

## Requirements

- Minecraft 1.21.1
- Java 21
- NeoForge 21.1.247 or a compatible 21.1 release
- Create 6.0.10+
- Create: Numismatics 1.1.0+
- Create Aeronautics bundle (includes the Simulated module)
- Sable, as required by Create Aeronautics

## How to use

1. Place and extend two Docking Connectors so they lock together.
2. Hold the Numismatics SalePoint block item and right-click the Docking Connector
   that should receive purchased items.
3. Place the SalePoint within the normal Numismatics target range.
4. Configure the item filter and price, then stock the SalePoint.
5. A purchase is accepted only while both Docking Connectors report a locked link.
   The sold items are inserted into the paired Docking Connector's inventory.

The addon does not add blocks or change docking physics; it adds the Numismatics
target behaviour to the existing Docking Connector block entity.
