# DayZ Weapons & Loot — Knowledge Bank (condensed)

> Condensed from Mazemaker (id=571096 loot-architecture cluster, id=824528 modlist,
> id=824542 TPAD cluster, id=229063 dayz-mod-development) + real plate files under
> /home/alca/games/DayZ/. Source of truth for any loot rebalance / VANGUARD anticheat work.

## 1. OpenClaw Loot Masterplan Invariants (HARD — never violate)
File: /home/alca/games/DayZ/masterplan/MASTERPLAN.md (project "Apocalyps3nd")
Models: qwen3:32b planner, gemma3:27b worker, OpenClaw+Ollama.
- NO escalation at Coast/Starter zones.
- Every weapon needs a consistent Ammo + Magazine chain or it is not proposed.
- Disabled Vanilla items get a 1:1 counterpart.
- Starter locations: survival + light self-defense, NO power combos.
- T1/T2/T3/T4/T5 must stay logically separated.
- No production file changed without backup + diff + validator approval.
Workflow roles: Planner -> Retriever -> ConfigEditor -> BalanceValidator -> DiffReviewer -> ApprovalGate.

## 2. A6 Custom Weapon Tree (types_V3_Sehr_stabil/)
Full custom family. nominal=spawn frequency, lifetime/restock=sec, value=Tier, usage=zone.
- Assault: A6_AR15_Carbine/Standard (T3, Police+Military), A6_AK74 (T2+T3, quantmin80/max90),
  A6_AK74N/101/102/105 (T3), A6_AugA1 (T3).
- Sniper: A6_R700/M24 (Town+Village+Hunting, no Tier), A6_SVD/SVD_Tiger/SV98 (T4, Underground_Lopatino),
  A6_Delta5 (T4, Sobor), A6_Delta5_Camo1/2 (T5, Sevorgrad — rarest).
- Shotgun: A6_MP153/Mossberg590 (Hunting+Farm+Village), A6_KSG/Benelli/Spas12 (T2+T3 Military),
  A6_AA12 (T3+T4 Military).
- SMG: A6_PP19Bizon/MP5k/PP19/MP5 (T1+T2 Military), A6_AugPara (T2+T3), A6_Vector (Military).
- Rifle (battle/spec): A6_OPSKS (T2+T3), A6_MK12 (T4, SeaPlatform), A6_MK14 (T4, Ocean+Skalisty),
  A6_M110 (T4, Ocean), A6_AR10/_Forest/_Desert (T4, OilRig).
- Pistol: A6_RugerMarkIV (T1-3, Town+Village), A6_MP9Pro_* (Police/Town), A6_Glock19/_Tan (Police).
- Ammo (category=weapons, usage=Military): Ammo_9x19AP63 (nom12), Ammo_A6_57x28 (6),
  Ammo_A6_46x30 (6), Ammo_545x39* (HP/FMJ/Tgs/PSgs/PPgs/BTgs/BPgs, nom9 each).
- Mags: A6_Mag_RugerMarkIV_10Rnd, A6_Mag_MP9Pro_17Rnd, A6_Mag_Glock19_15Rnd, A6_Mag_M1911_*,
  A6_Mag_MPShield_13Rnd (nom10, mostly Town+Village / Police).
- Attachments: Buttstocks (nominal0 = crafted/trade only, NOT looted), Optics (nom6, Military:
  MRDMount, SigSauerRomeo0/2, RMR — +Tan and +MRDMount variants), PistolGrips (nom4, T1-4).

### Tier -> Zone map
- T1: Vector, MP5k, RugerMarkIV, MP9Pro, Glock19
- T2: AK74, KSG, Benelli, Spas12, AugPara, OPSKS
- T3: AR15 family, AK101/2/105, AugA1, AA12, Optics pool
- T4: ALL SVD/MK/AR10/M110 — ONLY Underground_* (Lopatino, Sobor, Sevorgrad, SeaPlatform, Ocean, Skalisty, OilRig)
- T5: A6_Delta5_Camo1/2 (Underground_Sevorgrad) — top tier, rarest

## 3. Loot Delivery Systems
- Care Packages V2 (@Care Packages V2): Locations(Name,X,Y,Accuracy,AllowedPackageIDs) +
  Packages(object_type CarePackage_typhon, parachute ArmyParachute_typhon, MinWeapons1/Max4,
  MinMisc5/Max10, Items+Attachments e.g. Mag_AKM_Drum75rnd 1-75, FAL+Mag_FAL_20Rnd+Fal_FoldingButtstock+ACOGOptic).
- CJ187-LootChest (publishedid 2345073965) — loot chest mod.
- SpawnerBubaku (SpawnerBubakuV2.json) — zombie spawner (triggerpos, spawnerpos[], bubakProps w/ ZmbF/ZmbM classnames, triggerdelay 3600s), not weapon loot.
- MuchStuffPack (newtypes.xml) — clothes/tools (Msp_Mannequin_Kit, Msp_FlipFlops Town+Coast), no weapons.
- Dogtags, BaseBuildingPlus (BBP_types.xml, cfgeconomycore.xml, BBP_Loot_Types, BBP_Crafted_Types),
  ExpansionMod (Settings/, Market/Vests.json) — economy/crafting.

## 4. Trader Economy (@Trader) — GOTCHA
- Config: Mods/@Trader/extras/Trader/TraderConfig.txt
  ONLY single-line // comments work. /* multiline */ COMMENTS CRASH THE SERVER.
- Currency: MoneyRuble1/5/10/25/50/100.
- Line format: <Category> Item, Quantity(*=max / V=Vehicle / M=Mag / W=Weapon / S=Steak / K=Key), Buyvalue, Sellvalue (-1 = not buyable/sellable).
- TraderObjects.txt: one safezone per central area; <TraderMarkerSafezone> radius;
  <Object> SurvivorF_* + <ObjectAttachment> = vendor inventory.

## 5. Server Deploy (TPAD) — facts for VANGUARD
- TPAD (Garuda Linux 8c/15GB): 43 client mods + 4 server mods, 117 loaded (id=824491).
- NO headless mission-start (id=824506): EnforceScript compiles only on first real player connect.
- Full mod launch args (Proton): -connect -port -name -mod=@CF;@Dabs Framework;@Trader;@Dogtags;
  @CarCover;@BodyBags;@Code Lock;@DrugsPlus;@TruckFixV2;@MuchCarKey;@BuilderItems;@MuchFramework;
  @MuchStuffPack(+Fix);@VPPAdminTools;@Breachingcharge;@CJ187-LootChest;@Care Packages V2;@RaG_Vehicle_Pack;
  @Nehr_Pickup_Lada;@VPPNotifications;@VirtualGarageFull;@MaharlikaPH_Boats;@AdvancedBanking V2;
  @VanillaPlusPlusMap;@Forward Operator Gear;@Inventory Move Sounds;@KeyCard-Rooms Standalone;
  @CannabisPlus Experimental;@A6;@gore;@Toxiczonealarms;@BanditAi;@Autostack;@TJCore;@TJSscreen;
  @Artystrike;@Heli;@VanillaPPMap;@Munghard;@bedrespawn.

## 6. VANGUARD Anticheat cross-refs (weapons/loot)
- Item-Dupe via ScriptRPC is the PRIMARY cheat vector -> @VANGUARD_SERVER must validate GiveItem/Teleport RPCs.
- LootChest / Care-Package / Trader-Ruble are LEGITIMATE high-tier sources -> do NOT flag as cheat;
  only protect spawn logic + admin-give (VPPAdminTools).
- A6 tree is custom content -> PBO whitelist (VANGUARD Layer 1) must know the A6 PBO as signed.
- PBO paths use BACKSLASH (id=824515): verify both slash styles when inspecting deployed PBOs.
