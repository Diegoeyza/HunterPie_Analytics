HuntDumper — REFramework mod for Monster Hunter Wilds
=====================================================

At quest end this writes one JSON file to
    <game>\reframework\data\HuntExports\
with quest metadata, monster id + HP curve, per-player damage totals, the 30
quest awards (hunter highlights), CPU-supporter flags, and your local weapon
name. It never modifies game data and never talks to the network.

REQUIREMENTS
------------
- Monster Hunter Wilds
- REFramework for MH Wilds (install dinput8.dll first)

INSTALL (Vortex or manual)
--------------------------
The archive is already laid out for the game folder.

Manual:
  1. Install REFramework if you have not already.
  2. Extract this archive into your game folder so you get
        <game>\reframework\autorun\hunt_dumper.lua
     Default Steam path:
        ...\steamapps\common\MonsterHunterWilds\
  3. Launch the game; open the REFramework menu -> HuntDumper to confirm it is
     enabled. Dumps appear in reframework\data\HuntExports\.

Vortex:
  Install the archive normally; it maps into the game's reframework folder.

NOTES
-----
- Load the script before a quest starts. Reloading scripts mid-hunt resets its
  state, so that hunt is skipped (the next one is fine).
- This mod captures quest awards, the monster HP curve, party HP samples,
  damage totals, quest result, and your local weapon name. Per-player weapon
  classes, DPS curves and buff uptime come from HunterPie.

FULL DASHBOARD
--------------
This mod is one half of a post-hunt analytics dashboard. To graph everything
see the project README / releases page (link in the mod description).

CREDITS
-------
- REFramework by praydog
- HunterPie by the HunterPie team (Apache-2.0)
- This project: Apache-2.0
