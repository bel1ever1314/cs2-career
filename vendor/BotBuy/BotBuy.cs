// Derived from ed0ard/CS2-Bot-Improver BotBuy (AGPL-3.0).
// Career patch 2026-09-10: validate delayed players and preserve career sniper roles.
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Core.Attributes.Registration;
using CounterStrikeSharp.API.Modules.Utils;
using CounterStrikeSharp.API.Modules.Cvars;
using CounterStrikeSharp.API.Modules.Timers;
using System.Collections.Generic;
using System.Linq;

namespace BotBuyPatch;

public sealed partial class BotBuyPatch : BasePlugin
{
    public override string ModuleName        => "BotBuyPatch";
    public override string ModuleVersion => "1.0.12-career.5";
    public override string ModuleAuthor      => "ed0ard";
    public override string ModuleDescription => "Enable bots to take more buy options";

    private bool _careerActive, _purchasePhase;
    private int _roundGeneration;
    private string _roundMap = "";
    private readonly Dictionary<ulong, string> _careerRoles = new();
    private readonly Dictionary<int, uint> _roundPawns = new();
    private readonly Dictionary<int, HashSet<uint>> _roundStartWeapons = new();
    private readonly Dictionary<int, Dictionary<string, uint>> _purchasedWeapons = new();
    private readonly HashSet<uint> _refundingWeapons = new();
    private float _emptyPrimaryReadyAt;
    private readonly Dictionary<int, string> _emptyPrimaryDiagnostics = new();

    // Read once per round, not once per item. Synthetic Steam IDs from the
    // generated match request survive BotHider renaming; nicknames never bind jobs.
    private void RefreshCareerContext()
    {
        _careerActive = false; _careerRoles.Clear(); _careerSides.Clear(); _careerNonce = "";
        try
        {
            var path = System.IO.Path.Combine(ModuleDirectory, "..", "CareerMatch", "match_request.json");
            if (!System.IO.File.Exists(path)) return;
            using var doc = System.Text.Json.JsonDocument.Parse(System.IO.File.ReadAllText(path));
            var root = doc.RootElement;
            _careerActive = root.TryGetProperty("active", out var active) && active.GetBoolean();
            if (!_careerActive) return;
            if (!root.TryGetProperty("map", out var map) || map.GetString() != Server.MapName)
            { _careerActive = false; return; } // A leftover request is not a match on another map.
            _careerNonce = root.TryGetProperty("nonce", out var nonce) ? nonce.GetString() ?? "" : "";
            foreach (var side in new[] { "ct", "t" })
            {
                if (!root.TryGetProperty(side, out var team) || !team.TryGetProperty("players", out var players)) continue;
                foreach (var bot in players.EnumerateArray())
                {
                    if (!bot.TryGetProperty("steam_id", out var steam) || !steam.TryGetUInt64(out var id) || id == 0) continue;
                    var role = bot.TryGetProperty("role", out var job) ? job.GetString() ?? "" : "";
                    if (!_careerRoles.TryAdd(id, role))
                    { _careerRoles.Clear(); _careerSides.Clear(); _careerActive = false; return; }
                    _careerSides.Add(id, side);
                }
            }
        }
        catch { _careerRoles.Clear(); _careerSides.Clear(); _careerActive = false; }
    }

    private bool IsCareerMatch() => _careerActive;

    private string CareerRole(CCSPlayerController player) => _careerRoles.GetValueOrDefault(player.SteamID, "");

    private bool IsKnownBot(CCSPlayerController player) => player.IsValid
        && (player.IsBot || _careerRoles.ContainsKey(player.SteamID));

    private bool CanModify(CCSPlayerController player)
    {
        try
        {
            if (!player.IsValid) return false;
            var pawn = player.PlayerPawn.Value;
            if (pawn is null || !pawn.IsValid) return false;
            var original = player.OriginalControllerOfCurrentPawn.Value;
            bool requestBot = _careerRoles.ContainsKey(player.SteamID) && pawn.Bot is not null;
            if (_careerActive && (!_purchasePhase || !requestBot
                || !_roundPawns.TryGetValue(player.Slot, out var expected) || expected != pawn.EntityHandle.Raw)) return false;
            return CareerWeaponPolicy.CanModify(true, player.IsBot, requestBot, player.ControllingBot,
                player.HasBeenControlledByPlayerThisRound, original is null || original.Handle == player.Handle,
                pawn.Health > 0);
        }
        catch { return false; }
    }

    private void AddRoundTimer(float seconds, Action callback)
    {
        var round = _roundGeneration; var map = _roundMap;
        AddTimer(seconds, () =>
        {
            if (round != _roundGeneration || map != Server.MapName || (_careerActive && !_purchasePhase)) return;
            callback();
        }, TimerFlags.STOP_ON_MAPCHANGE);
    }

    [GameEventHandler]
    public HookResult OnItemPurchase(EventItemPurchase ev, GameEventInfo info)
    {
        var player = ev.Userid;
        var weapon = ev.Weapon.StartsWith("weapon_") ? ev.Weapon : "weapon_" + ev.Weapon;
        if (!_careerActive || player is null || !CanModify(player)
            || CareerTactics.TacticalBuyPolicy.PrimaryPrice(weapon) == 0) return HookResult.Continue;
        var generation = _roundGeneration; var pawn = player.PlayerPawn.Value!.EntityHandle.Raw;
        Server.NextFrame(() =>
        {
            if (generation != _roundGeneration || !CanModify(player)
                || player.PlayerPawn.Value?.EntityHandle.Raw != pawn) return;
            var weapons = player.PlayerPawn.Value!.WeaponServices?.MyWeapons
                .Select(h => h.Value).Where(w => w is { IsValid: true } && w.DesignerName == weapon).ToArray();
            if (weapons is not { Length: 1 }) return;
            var entity = weapons[0]!.EntityHandle.Raw;
            if (!_roundStartWeapons.TryGetValue(player.Slot, out var old) || old.Contains(entity)
                || _refundingWeapons.Contains(entity)) return;
            if (!_purchasedWeapons.TryGetValue(player.Slot, out var bought))
                _purchasedWeapons[player.Slot] = bought = new();
            bought[weapon] = entity;
            ApplyCareerPurchases(player);
        });
        return HookResult.Continue;
    }

    private void NormalizePurchasedWeapons(CCSPlayerController player)
    {
        if (!CanCareerPurchase(player) || !_purchasedWeapons.TryGetValue(player.Slot, out var purchases)
            || !_roundStartWeapons.TryGetValue(player.Slot, out var old)) return;
        foreach (var purchase in purchases.ToArray())
        {
            var weapons = player.PlayerPawn.Value!.WeaponServices?.MyWeapons.Select(h => h.Value)
                .Where(w => w is { IsValid: true } && w.DesignerName == purchase.Key).ToArray();
            if (weapons is not { Length: 1 }) continue;
            var entity = weapons[0]!.EntityHandle.Raw;
            if (!CareerWeaponPolicy.ShouldReplacePurchase(_careerActive, CanModify(player), _purchasePhase,
                purchase.Key, entity, purchase.Value, old.Contains(entity), weapons.Length, CanRefund(player, purchase.Key))) continue;
            Swap(player, purchase.Key, CareerWeaponPolicy.Rifle(player.Team == CsTeam.CounterTerrorist,
                player.SteamID % 2 == 0 ? .25f : .75f));
        }
    }

    private Dictionary<int, int> _botUserIdToIndex = new();
    private int _botIndexCounter = 0;

    Dictionary<CsTeam, List<CCSPlayerController>> _poorPlayersByTeam = new();

    private Dictionary<int, List<string>> _prevWeapons = new();
    private Dictionary<int, int> _prevMoney = new();
    private Dictionary<int, int> _prevArmor = new();
//----------------------------------------------------------------------------------------------
    [GameEventHandler]
    public HookResult OnPlayerConnectFull(EventPlayerConnectFull @event, GameEventInfo info)
    {
        var player = @event.Userid;
        if (player != null && player.IsBot) GetBotIndex(player);
        return HookResult.Continue;
    }

    [GameEventHandler]
    public HookResult OnPlayerDisconnect(EventPlayerDisconnect @event, GameEventInfo info)
    {
        var player = @event.Userid;
        if (player != null) RemoveBot(player);
        return HookResult.Continue;
    }

    [GameEventHandler]// Unlock Refund Restriction
    public HookResult OnPlayerDeath(EventPlayerDeath @event, GameEventInfo info)
    {
        var player = @event.Userid;
        if (player != null && IsKnownBot(player))
        {
            ClearPreviousInventory(player);
        }
        return HookResult.Continue;
    }

    [GameEventHandler]
    public HookResult OnRoundEnd(EventRoundEnd @event, GameEventInfo info)
    {
        SavePreviousInventory();
        _purchasePhase = false;
        _tacticalDuties.Clear();
        _roundGeneration++;

        return HookResult.Continue;
    }
//----------------------------------------------------------------------------------------------
    [GameEventHandler]
    public HookResult OnRoundStart(EventRoundStart @event, GameEventInfo info)
    {
        _roundGeneration++; _roundMap = Server.MapName; _purchasePhase = true; _tacticalDuties.Clear();
        RefreshCareerContext(); _roundPawns.Clear(); _roundStartWeapons.Clear(); _purchasedWeapons.Clear(); _refundingWeapons.Clear();
        _emptyPrimaryReadyAt = Server.CurrentTime + .8f;
        _emptyPrimaryDiagnostics.Clear();
        // Don't Buy on Aim_Rush
        if (Server.MapName == "aim_rush") return HookResult.Continue;

        List<CCSPlayerController> allPlayers = new();
        List<CCSPlayerController> allCT = new();
        List<CCSPlayerController> allT = new();
        List<CCSPlayerController> ctBots = new();
        List<CCSPlayerController> tBots = new();

        foreach (var player in Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller"))
        {
            if (!player.IsValid) continue;  
            allPlayers.Add(player);

            var roundPawn = player.PlayerPawn.Value;
            if (roundPawn is { IsValid: true })
            {
                _roundPawns[player.Slot] = roundPawn.EntityHandle.Raw;
                _roundStartWeapons[player.Slot] = roundPawn.WeaponServices?.MyWeapons
                    .Select(h => h.Value).Where(w => w is { IsValid: true })
                    .Select(w => w!.EntityHandle.Raw).ToHashSet() ?? new();
            }

            if (player.Team == CsTeam.CounterTerrorist)
            {
                allCT.Add(player);
                if (player.IsBot) ctBots.Add(player);
            }
            else if (player.Team == CsTeam.Terrorist)
            {
                allT.Add(player);
                if (player.IsBot) tBots.Add(player);
            }
        }
        if (_careerActive)
        {
            allPlayers = allPlayers.Where(CanModify).ToList();
            allCT = allCT.Where(CanModify).ToList(); allT = allT.Where(CanModify).ToList();
            ctBots = allCT.ToList(); tBots = allT.ToList();
        }
        // Drop Weapons
        _poorPlayersByTeam.Clear();
        var poorCT = allPlayers.Where(p => p.IsValid && p.Team == CsTeam.CounterTerrorist && p.InGameMoneyServices?.Account < 2800).ToList();
        var poorT = allPlayers.Where(p => p.IsValid && p.Team == CsTeam.Terrorist && p.InGameMoneyServices?.Account < 2800).ToList();
        _poorPlayersByTeam[CsTeam.CounterTerrorist] = poorCT;
        _poorPlayersByTeam[CsTeam.Terrorist] = poorT;

        ConVar? botLoadout = ConVar.Find("bot_loadout");
        if (botLoadout != null && !string.IsNullOrEmpty(botLoadout.StringValue))
        {
            return HookResult.Continue;
        }
        if (_careerActive)
            foreach (var delay in new[] { .9f, 1.8f, 3.2f,
                Math.Max(.9f, (ConVar.Find("mp_freezetime")?.GetPrimitiveValue<float>() ?? 15f) - .25f) }.Distinct())
                AddRoundTimer(delay, () => {
                    foreach (var player in Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller"))
                        ApplyCareerPurchases(player);
                });
        // Swap HKP2000
        foreach (var player in allPlayers.Where(CanModify))
        {
            // Swap HKP2000
            if (Random.Shared.NextSingle() < 0.8f)
            {
                Swap(player, "weapon_hkp2000", "weapon_usp_silencer");
            }
        }
        // Force Buy
        bool allCtInRange = ctBots.Count > 0 && ctBots.All(p =>
            p.InGameMoneyServices != null && p.InGameMoneyServices.Account > 1000 && p.InGameMoneyServices.Account < 2800);

        bool allTInRange = tBots.Count > 0 && tBots.All(p =>
            p.InGameMoneyServices != null && p.InGameMoneyServices.Account > 1000 && p.InGameMoneyServices.Account < 2800);
        AddRoundTimer(0.4f, () =>
        {
            if (allCtInRange)
            {
                float roll = Random.Shared.NextSingle();
                foreach (var bot in ctBots)
                {
                    if (roll < 0.10f)
                    {
                        Swap(bot, "weapon_usp_silencer", "weapon_fiveseven");
                        Swap(bot, "weapon_hkp2000", "weapon_fiveseven");
                    }
                    else if (roll < 0.20f)
                    {
                        Buy(bot, "weapon_mp9");
                    }
                }
            }

            if (allTInRange)
            {
                float roll = Random.Shared.NextSingle();
                foreach (var bot in tBots)
                {
                    if (roll < 0.10f)
                    {
                        Swap(bot, "weapon_glock", "weapon_tec9");
                    }
                    else if (roll < 0.20f)
                    {
                        Buy(bot, "weapon_mac10");
                    }
                }
            }
        });
        // Don't buy if we have scar20/g3sg1
        foreach (var player in allPlayers.Where(CanModify))
        {
            var pawn = player.PlayerPawn.Value;
            if (pawn == null || !pawn.IsValid || pawn.WeaponServices == null) continue;

            var activeWeapon = pawn.WeaponServices.ActiveWeapon.Value;
            if (activeWeapon == null) continue;

            string initialGun = activeWeapon.DesignerName;
            if (initialGun != "weapon_scar20" && initialGun != "weapon_g3sg1") continue;

            var copyPlayer = player;
            AddRoundTimer(0.5f, () =>
            {
                if (!CanModify(copyPlayer)) return;
                var p2 = copyPlayer.PlayerPawn.Value;
                if (p2 == null || !p2.IsValid || p2.WeaponServices == null) return;

                var currentWeapon = p2.WeaponServices.ActiveWeapon.Value;
                if (currentWeapon == null) return;

                string currentGun = currentWeapon.DesignerName;
                if (currentGun != "weapon_scar20" && currentGun != "weapon_g3sg1")
                {
                    Refund(copyPlayer, currentGun);
                }
            });
        }
        // Swap AUG
        foreach (var player in allPlayers.Where(CanModify))
        {
            // Career normalization requires evidence of this round's purchase.
            // A picked-up or carried AUG must not be stripped/refunded by name.
            if (_careerActive) continue;
            var copyPlayer = player;
            float rand = Random.Shared.NextSingle();

            if (rand < 0.06f)
            {
            }
            else if (rand < 0.53f)
            {
                AddRoundTimer(0.4f, () =>
                {
                    if (!CanModify(copyPlayer)) return;
                    Swap(copyPlayer, "weapon_aug", "weapon_m4a1");
                });
            }
            else
            {
                AddRoundTimer(0.4f, () =>
                {
                    if (!CanModify(copyPlayer)) return;
                    Swap(copyPlayer, "weapon_aug", "weapon_m4a1_silencer");
                });
            }
        }
        // Swap P90
        AddRoundTimer(0.4f, () =>
        {
            foreach (var p in allPlayers)
            {
                if (!CanModify(p)) continue;
                var pawn = p.PlayerPawn.Value;
                if (pawn == null || !pawn.IsValid || pawn.WeaponServices == null) continue;

                var weapon = pawn.WeaponServices.ActiveWeapon.Value;
                if (weapon == null || weapon.DesignerName != "weapon_p90") continue;

                float roll = Random.Shared.NextSingle();
                if (roll < 0.3f) Swap(p, "weapon_p90", "weapon_bizon");
                else if (roll < 0.4f) Swap(p, "weapon_p90", "weapon_mp7");
                else if (roll < 0.5f) Swap(p, "weapon_p90", "weapon_mp5sd");
                else if (roll < 0.6f) Swap(p, "weapon_p90", "weapon_ump45");
            }
        });
        // Swap XM1014
        AddRoundTimer(0.4f, () =>
        {
            foreach (var p in allPlayers)
            {
                if (!CanModify(p)) continue;
                var pawn = p.PlayerPawn.Value;
                if (pawn == null || !pawn.IsValid || pawn.WeaponServices == null) continue;

                var weapon = pawn.WeaponServices.ActiveWeapon.Value;
                if (weapon == null || weapon.DesignerName != "weapon_xm1014") continue;

                float roll = Random.Shared.NextSingle();
                if (roll < 0.5f)
                {
                    Swap(p, "weapon_xm1014", "weapon_negev");
                }
                else if (p.Team == CsTeam.CounterTerrorist && roll < 0.6f)
                {
                    Swap(p, "weapon_xm1014", "weapon_mag7");
                }
                else if (p.Team == CsTeam.Terrorist && roll < 0.65f)
                {
                    Swap(p, "weapon_xm1014", "weapon_sawedoff");
                }
            }
        });
        // Swap SSG08 (disabled only for active career requests: preserve the AWP role)
        AddRoundTimer(0.4f, () =>
        {
            if (IsCareerMatch() || ConVar.Find("sv_gravity")?.GetPrimitiveValue<float>() == 230f) return;
            foreach (var p in allPlayers)
            {
                if (!CanModify(p)) continue;
                var pawn = p.PlayerPawn.Value;
                if (pawn == null || !pawn.IsValid || pawn.WeaponServices == null) continue;

                var weapon = pawn.WeaponServices.ActiveWeapon.Value;
                if (weapon == null || weapon.DesignerName != "weapon_ssg08") continue;

                float roll = Random.Shared.NextSingle();

                if (roll < 0.05f)
                {
                    if (p.Team == CsTeam.CounterTerrorist)
                    {
                        Refund(p, "weapon_usp_silencer");
                        Refund(p, "weapon_hkp2000");
                    }
                    else
                    {
                        Refund(p, "weapon_glock");
                    }
                    Swap(p, "weapon_ssg08", "weapon_deagle");
                }
                else if (roll < 0.45f)
                {
                    if (p.Team == CsTeam.Terrorist)
                        Swap(p, "weapon_ssg08", "weapon_mac10");
                    else
                        Swap(p, "weapon_ssg08", "weapon_mp9");
                }
            }
        });
        // Big Advantage
        AddRoundTimer(0.6f, () =>
        {
            if (_careerActive) return; // Preserve career jobs and ordinary full buys.
            if (!IsFirstRoundOfHalf())  
            {
                foreach (var p in allPlayers)
            {
                if (!CanModify(p)) continue;
                    if (p.InGameMoneyServices == null || p.InGameMoneyServices.Account < 5200)
                        continue;

                    var pawn = p.PlayerPawn.Value;
                    if (pawn == null || !pawn.IsValid)
                        continue;

                    var weaponServices = pawn.WeaponServices;
                    if (weaponServices == null)
                        continue;

                    var activeWeapon = weaponServices.ActiveWeapon.Value;
                    if (activeWeapon == null)
                        continue;

                    var currentWeapon = activeWeapon.DesignerName;
                    if (string.IsNullOrEmpty(currentWeapon))
                        continue;

                    float roll = Random.Shared.NextSingle();

                    if (roll < 0.10f)
                    {
                        string newGun = p.Team == CsTeam.CounterTerrorist ? "weapon_scar20" : "weapon_g3sg1";
                        Swap(p, currentWeapon, newGun);
                    }
                    else if (roll < 0.14f)
                    {
                        Swap(p, currentWeapon, "weapon_m249");
                    }
                }
            }
        });
        // Buy Defuser
        AddRoundTimer(3.0f, () =>
        {
            foreach (var p in allCT)
            {
                if (!CanModify(p)) continue;
                if (p.InGameMoneyServices == null) continue;

                bool isPoor = _poorPlayersByTeam[CsTeam.CounterTerrorist].Contains(p);
                // Don't buy defuser if poor // Exception: pistol round with 500 left
                if (isPoor && !(IsFirstRoundOfHalf() && p.InGameMoneyServices.Account == 500))
                    continue;

                if (p.InGameMoneyServices.Account < 400)
                    continue;

                var pawn = p.PlayerPawn.Value;
                if (pawn == null || !pawn.IsValid || pawn.ItemServices == null || pawn.ItemServices.Handle == nint.Zero)
                    continue;

                var itemServices = new CCSPlayer_ItemServices(pawn.ItemServices.Handle);
                if (itemServices.HasDefuser)
                    continue;

                Buy(p, "item_defuser");
            }
        });
        // Don't buy Armor if it's above 40
        AddRoundTimer(1.0f, () =>
        {
            if (!IsFirstRoundOfHalf())  
            {
                foreach (var p in allPlayers)
            {
                if (!CanModify(p)) continue;
                    if (!p.IsValid || p.PlayerPawn.Value == null) continue;

                    var pawn = p.PlayerPawn.Value;
                    var (_, _, prevArmor) = PreviousInventory(p);

                    if (pawn.ItemServices == null || pawn.ItemServices.Handle == nint.Zero)
                    continue;
                    var itemServices = new CCSPlayer_ItemServices(pawn.ItemServices.Handle);

                    int currentArmor = pawn.ArmorValue;

                    if (prevArmor > 40 && prevArmor <= 99 && currentArmor > 99 && itemServices.HasHelmet)
                    {
                        Refund(p, "item_assaultsuit");
                        p.GiveNamedItem("item_assaultsuit");
                        ref int armorValue = ref pawn.ArmorValue;
                        armorValue = prevArmor;
                        Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_ArmorValue");
                    }
                }
            }
        });
        // Special Rounds Buy Assistant
        AddRoundTimer(0.4f, () =>
        {
            if (IsFirstRoundOfHalf())
            {
                foreach (var p in allPlayers)
            {
                if (!CanModify(p)) continue;
                    if (!p.IsValid || p.InGameMoneyServices == null) continue;
                    int money = p.InGameMoneyServices.Account;
                    float r = Random.Shared.NextSingle();

                    // Comp Pistol Rounds
                    if (money == 800)
                    {
                        if (p.Team == CsTeam.CounterTerrorist)
                        {
                            if (r < 0.50f)  Buy(p, "item_kevlar");    // 50%
                            else if (r < 0.65f) { Swap(p, "weapon_usp_silencer", "weapon_elite"); Swap(p, "weapon_hkp2000", "weapon_elite"); } // 15%
                            else if (r < 0.75f) { Swap(p, "weapon_usp_silencer", "weapon_p250"); Swap(p, "weapon_hkp2000", "weapon_p250"); }   // 10%
                            else if (r < 0.83f) { Swap(p, "weapon_usp_silencer", "weapon_deagle"); Swap(p, "weapon_hkp2000", "weapon_deagle"); } // 8%
                            else if (r < 0.91f) { Swap(p, "weapon_usp_silencer", "weapon_cz75a"); Swap(p, "weapon_hkp2000", "weapon_cz75a"); }   // 8%
                            else if (r < 0.98f) { Swap(p, "weapon_usp_silencer", "weapon_fiveseven"); Swap(p, "weapon_hkp2000", "weapon_fiveseven"); } //7%
                            else if (r < 1.00f) { Swap(p, "weapon_usp_silencer", "weapon_revolver"); Swap(p, "weapon_hkp2000", "weapon_revolver"); } //2%
                        }
                        else
                        {
                            if (r < 0.50f)  Buy(p, "item_kevlar");    // 50%
                            else if (r < 0.65f) Swap(p, "weapon_glock", "weapon_elite"); //15%
                            else if (r < 0.77f) Swap(p, "weapon_glock", "weapon_p250");  //12%
                            else if (r < 0.85f) Swap(p, "weapon_glock", "weapon_deagle");//8%
                            else if (r < 0.87f) Swap(p, "weapon_glock", "weapon_revolver");//2%
                            else if (r < 1.00f) Swap(p, "weapon_glock", "weapon_tec9");//13%
                        }
                    }

                    // Casual Pistol Rounds
                    else if (money == 1000)
                    {
                        if (p.Team == CsTeam.CounterTerrorist)
                        {
                            if (r < 0.20f)  { Swap(p, "weapon_usp_silencer", "weapon_elite"); Swap(p, "weapon_hkp2000", "weapon_elite"); } //20%
                            else if (r < 0.50f) { Swap(p, "weapon_usp_silencer", "weapon_deagle"); Swap(p, "weapon_hkp2000", "weapon_deagle"); } //30%
                            else if (r < 0.65f) { Swap(p, "weapon_usp_silencer", "weapon_cz75a"); Swap(p, "weapon_hkp2000", "weapon_cz75a"); } //15%
                            else if (r < 0.95f) { Swap(p, "weapon_usp_silencer", "weapon_fiveseven"); Swap(p, "weapon_hkp2000", "weapon_fiveseven"); } //30%
                            else if (r < 1.00f) { Swap(p, "weapon_usp_silencer", "weapon_revolver"); Swap(p, "weapon_hkp2000", "weapon_revolver"); } //5%
                        }
                        else
                        {
                            if (r < 0.20f)  Swap(p, "weapon_glock", "weapon_elite"); //20%
                            else if (r < 0.30f) Swap(p, "weapon_glock", "weapon_p250"); //10%
                            else if (r < 0.55f) Swap(p, "weapon_glock", "weapon_deagle");//25%
                            else if (r < 0.60f) Swap(p, "weapon_glock", "weapon_revolver");//5%
                            else if (r < 1.00f) Swap(p, "weapon_glock", "weapon_tec9");//40%
                        }
                    }

                    // First Round in OT
                    else if (money == 10000)
                    {
                        Buy(p, "item_assaultsuit");
                        Buy(p, CareerWeaponPolicy.OvertimeWeapon(_careerActive, PurchaseRole(p),
                            p.Team == CsTeam.CounterTerrorist, r));
                    }
                }
            }
        });
        // Drop Weapons
        AddRoundTimer(2.0f, () =>
        {
            if (!IsFirstRoundOfHalf())  
            {
                foreach (var team in new[] { CsTeam.CounterTerrorist, CsTeam.Terrorist })
                {
                    if (!_poorPlayersByTeam.TryGetValue(team, out var poor))
                        poor = new List<CCSPlayerController>();
                    poor = poor.Where(p => p.IsValid && p.InGameMoneyServices != null
                        && (!_careerActive || CanModify(p))).ToList();

                    var richBots = allPlayers.Where(p => CanModify(p) && p.Team == team && p.InGameMoneyServices?.Account >= 2900
                        && (!_careerActive || (CanCareerPurchase(p) && HasPrimaryWeapon(p)))).ToList();

                    if (poor.Count == 0 || richBots.Count == 0) continue;

                    var giftedPoor = new HashSet<CCSPlayerController>();

                    var shuffledPoor = poor.Where(p => !HasPrimaryWeapon(p)).OrderBy(_ => Random.Shared.Next()).ToList();
                    int poorIndex = 0;

                    foreach (var rich in richBots)
                    {
                        if (poorIndex >= shuffledPoor.Count) break;
                        if (!CanModify(rich) || rich.InGameMoneyServices == null) continue;

                        int richMoney = rich.InGameMoneyServices.Account;
                        int price = CareerTactics.TacticalBuyPolicy.PrimaryPrice(CareerWeaponPolicy.Rifle(team == CsTeam.CounterTerrorist, .25f));
                        int reserve = _careerActive ? PurchaseReserve(rich) : 0;

                        int maxGive = Math.Max(0, richMoney - reserve) / price;
                        if (maxGive > 3) maxGive = 3;
                        if (maxGive <= 0) continue;

                        int given = 0;
                        while (given < maxGive && poorIndex < shuffledPoor.Count)
                        {
                            var poorPlayer = shuffledPoor[poorIndex];
                            poorIndex++;

                            if (!poorPlayer.IsValid || giftedPoor.Contains(poorPlayer) || HasPrimaryWeapon(poorPlayer)
                                || (_careerActive && !CanCareerPurchase(poorPlayer))) continue;

                            string gun = team == CsTeam.CounterTerrorist
                                ? (Random.Shared.Next(2) == 0 ? "weapon_m4a1_silencer" : "weapon_m4a1")
                                : "weapon_ak47";
                            var givenHandle = poorPlayer.GiveNamedItem(gun);
                            if (givenHandle == IntPtr.Zero || !new CEntityInstance(givenHandle).IsValid) continue;
                            giftedPoor.Add(poorPlayer);

                            rich.InGameMoneyServices.Account -= price;
                            if (rich.InGameMoneyServices.Account < 0) rich.InGameMoneyServices.Account = 0;
                            Utilities.SetStateChanged(rich, "CCSPlayerController", "m_pInGameMoneyServices");

                            foreach (var teammate in allPlayers.Where(p => p.IsValid && p.Team == team))
                                teammate.PrintToChat($"{ChatColors.Green}{rich.PlayerName}{ChatColors.Yellow}: {poorPlayer.PlayerName}, I dropped a weapon for ya");
                            given++;
                        }
                    }
                }
            }
        });
        // Armor Gift Cycle: richest non-poor bot buys armor for a random unarmored teammate
        AddRoundTimer(2.5f, () =>
        {
            foreach (var team in new[] { CsTeam.CounterTerrorist, CsTeam.Terrorist })
            {
                _poorPlayersByTeam.TryGetValue(team, out var poor);
                var poorSet = new HashSet<CCSPlayerController>(poor ?? new List<CCSPlayerController>());

                while (true)
                {
                    var needArmor = allPlayers
                        .Where(p => CanModify(p) && p.Team == team
                            && (!_careerActive || CanCareerPurchase(p))
                            && HasPrimaryWeapon(p)
                            && (p.PlayerPawn.Value?.ArmorValue ?? 1) == 0)
                        .ToList();

                    if (needArmor.Count == 0) break;

                    var buyer = allPlayers
                        .Where(p => CanModify(p) && p.Team == team
                            && !poorSet.Contains(p)
                            && p.InGameMoneyServices?.Account >= 650
                            && (!_careerActive || (CanCareerPurchase(p) && HasPrimaryWeapon(p)
                                && p.InGameMoneyServices.Account >= PurchaseReserve(p) + (team == CsTeam.Terrorist ? 1000 : 650))))
                        .OrderByDescending(p => p.InGameMoneyServices!.Account)
                        .FirstOrDefault();
                    // No one has enough money anymore
                    if (buyer == null) break;

                    var target = needArmor[Random.Shared.Next(needArmor.Count)];
                    if (!CanModify(target) || !CanModify(buyer)) continue;

                    int buyerMoney = buyer.InGameMoneyServices!.Account;
                    int spendableMoney = _careerActive ? buyerMoney - PurchaseReserve(buyer) : buyerMoney;
                    // Terrorist bots only buy full armor
                    if (team == CsTeam.Terrorist && spendableMoney < 1000) break;
                    int price = CareerWeaponPolicy.GiftArmorPrice(team == CsTeam.CounterTerrorist,
                        buyerMoney, _careerActive ? PurchaseReserve(buyer) : 0);
                    if (price == 0) break;
                    string item = price == 1000 ? "item_assaultsuit" : "item_kevlar";

                    target.GiveNamedItem(item);
                    buyer.InGameMoneyServices.Account -= price;
                    Utilities.SetStateChanged(buyer, "CCSPlayerController", "m_pInGameMoneyServices");
                }
            }
        });
        return HookResult.Continue;
    }

    [GameEventHandler]
    public HookResult OnRoundFreezeEnd(EventRoundFreezeEnd @event, GameEventInfo info)
    {
        if (_careerActive)
        {
            _purchasePhase = false;
        }
        ConVar? botLoadout = ConVar.Find("bot_loadout");
        if (botLoadout != null && !string.IsNullOrEmpty(botLoadout.StringValue))
        {
            return HookResult.Continue;
        }

        // Don't save money in the last round of each half
        var ecoLimitCvar = ConVar.Find("bot_eco_limit");
        if (ecoLimitCvar != null)
        {
            if (IsSecondToLastRoundOfHalf())
                Server.ExecuteCommand("bot_eco_limit 0");
            else
                Server.ExecuteCommand("bot_eco_limit 2800");
        }

        foreach (var player in Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller"))
        {
            if (!player.IsValid || !player.IsBot)
                continue;

            var pawn = player.PlayerPawn.Value;
            if (pawn == null || !pawn.IsValid)
                continue;

            var bot = pawn.Bot;
            if (bot == null)
                continue;

// Nothing here
        }
        return HookResult.Continue;
    }
//----------------------------------------------------------------------------------------------
    private bool HasPrimaryWeapon(CCSPlayerController player)
    {
        if (!player.IsValid || player.PlayerPawn.Value == null)
            return false;

        var pawn = player.PlayerPawn.Value;
        if (pawn.WeaponServices == null)
            return false;

        return CareerWeaponPolicy.HasPrimary(pawn.WeaponServices.MyWeapons
            .Select(h => h.Value).Where(w => w is { IsValid: true }
                && !_refundingWeapons.Contains(w.EntityHandle.Raw)).Select(w => w!.DesignerName));
    }

//----------------------------------------------------------------------------------------------
    private bool Buy(CCSPlayerController player, string itemName, bool restoringOriginal = false)
    {
        if (!CanModify(player) || player.InGameMoneyServices == null
            || !CareerWeaponPolicy.CanBuy(_careerActive, itemName, PurchaseRole(player), restoringOriginal))
            return false;

        var pawn = player.PlayerPawn.Value;
        if (pawn == null || !pawn.IsValid)
            return false;

        int money = player.InGameMoneyServices.Account;
        bool isCT = player.Team == CsTeam.CounterTerrorist;
        bool isT = player.Team == CsTeam.Terrorist;
        int price = 0;
        bool canBuy = true;
        int armor = pawn.ArmorValue;

        switch (itemName)
        {
            case "item_kevlar":              price = 650; break;
            case "item_assaultsuit":         price = armor > 99 ? 350 : 1000; break;

            case "item_defuser":             price = 400; canBuy = isCT; break;
            case "weapon_taser":             price = 200; break;

            case "weapon_glock":             canBuy = isT; break;
            case "weapon_hkp2000":           canBuy = isCT; break;
            case "weapon_usp_silencer":      canBuy = isCT; break;
            case "weapon_elite":             price = 300;  break;
            case "weapon_p250":              price = 300;  break;
            case "weapon_tec9":              price = 500;  canBuy = isT; break;
            case "weapon_fiveseven":         price = 500;  canBuy = isCT; break;
            case "weapon_deagle":            price = 700;  break;
            case "weapon_cz75a":             price = 500;  break;
            case "weapon_revolver":          price = 600;  break;

            default:
                price = CareerTactics.TacticalBuyPolicy.PrimaryPrice(itemName);
                canBuy = (isCT || isT) && CareerTactics.TacticalBuyPolicy.PrimaryAllowed(isCT, itemName);
                break;
        }

        if (!canBuy)
            return false;

        if (money < price)
            return false;

        var givenHandle = player.GiveNamedItem(itemName);
        if (givenHandle == IntPtr.Zero) return false;
        var given = new CEntityInstance(givenHandle);
        if (!given.IsValid) return false;

        // A valid spawned entity alone does not prove that the bot received a
        // primary. Charge and record it only after it is attached to this pawn.
        if (CareerTactics.TacticalBuyPolicy.PrimaryPrice(itemName) > 0
            && !(pawn.WeaponServices?.MyWeapons.Any(h => h.Value is { IsValid: true } w
                && w.EntityHandle.Raw == given.EntityHandle.Raw && w.DesignerName == itemName) ?? false))
        {
            given.AcceptInput("Kill");
            return false;
        }

        player.InGameMoneyServices.Account -= price;
        Utilities.SetStateChanged(player, "CCSPlayerController", "m_pInGameMoneyServices");

        if (_careerActive && CareerTactics.TacticalBuyPolicy.PrimaryPrice(itemName) > 0)
        {
            if (!_purchasedWeapons.TryGetValue(player.Slot, out var bought))
                _purchasedWeapons[player.Slot] = bought = new();
            bought[itemName] = given.EntityHandle.Raw;
        }

        return true;
    }

    private bool Refund(CCSPlayerController player, string itemName)
    {
        if (!CanModify(player) || player.InGameMoneyServices == null)
        return false;

        var pawn = player.PlayerPawn.Value;
        if (pawn == null || !pawn.IsValid)
            return false;

        if (!CanRefund(player, itemName))
            return false;

        bool hasItem = false;
        int price = 0;
        bool isCT = player.Team == CsTeam.CounterTerrorist;
        bool isT = player.Team == CsTeam.Terrorist;

        if (itemName.StartsWith("weapon_"))
        {
            hasItem = pawn.WeaponServices != null && pawn.WeaponServices.MyWeapons
                .Any(w => w.Value != null && w.Value.DesignerName == itemName);
        }
        else if (itemName == "item_assaultsuit" || itemName == "item_kevlar")
        {
            hasItem = pawn.ArmorValue > 0;
        }

        if (!hasItem)
            return false;

        bool canRefund = true;

        switch (itemName)
        {
            case "item_kevlar":              price = 650; break;
            case "item_assaultsuit":         price = 1000; break;

            case "weapon_taser":             price = 200; break;

            case "weapon_glock":             canRefund = isT; break;
            case "weapon_hkp2000":           canRefund = isCT; break;
            case "weapon_usp_silencer":      canRefund = isCT; break;
            case "weapon_elite":             price = 300;  break;
            case "weapon_p250":              price = 300;  break;
            case "weapon_tec9":              price = 500;  canRefund = isT; break;
            case "weapon_fiveseven":         price = 500;  canRefund = isCT; break;
            case "weapon_deagle":            price = 700;  break;
            case "weapon_cz75a":             price = 500;  break;
            case "weapon_revolver":          price = 600;  break;

            default:
                price = CareerTactics.TacticalBuyPolicy.PrimaryPrice(itemName);
                canRefund = (isCT || isT) && CareerTactics.TacticalBuyPolicy.PrimaryAllowed(isCT, itemName);
                break;
        }

        if (!canRefund)
            return false;
        
        if (itemName.StartsWith("weapon_"))
        {
            var removed = pawn.WeaponServices!.MyWeapons.Select(h => h.Value)
                .Where(w => w is { IsValid: true } && w.DesignerName == itemName)
                .Select(w => w!.EntityHandle.Raw).ToHashSet();
            // CSS 1.0.371 queues Kill after 0.1s; the old entity is still in
            // MyWeapons now. Accept the API's result, then invalidate its buy
            // proof immediately so this pending removal cannot refund twice.
            if (!player.RemoveItemByDesignerName(itemName)) return false;
            _refundingWeapons.UnionWith(removed);
            _purchasedWeapons.GetValueOrDefault(player.Slot)?.Remove(itemName);
        }
        else if (itemName == "item_assaultsuit" || itemName == "item_kevlar")
        {
            pawn.ArmorValue = 0;
            Utilities.SetStateChanged(pawn, "CCSPlayerPawn", "m_ArmorValue");
        }

        player.InGameMoneyServices.Account += price;
        // Cap at mp_maxmoney
        int maxMoney = ConVar.Find("mp_maxmoney")?.GetPrimitiveValue<int>() ?? 16000;
        if (player.InGameMoneyServices.Account > maxMoney)
            player.InGameMoneyServices.Account = maxMoney;
        Utilities.SetStateChanged(player, "CCSPlayerController", "m_pInGameMoneyServices");

        return true;
    }

    private bool CanRefund(CCSPlayerController player, string itemName)
    {
        if (!CanModify(player))
            return false;

        if (_careerActive && CareerTactics.TacticalBuyPolicy.PrimaryPrice(itemName) > 0)
        {
            if (!CanCareerPurchase(player)) return false;
            var weapons = player.PlayerPawn.Value!.WeaponServices?.MyWeapons.Select(h => h.Value)
                .Where(w => w is { IsValid: true } && w.DesignerName == itemName).ToArray();
            if (weapons is not { Length: 1 }) return false;
            uint entity = weapons[0]!.EntityHandle.Raw;
            return _roundStartWeapons.TryGetValue(player.Slot, out var old)
                && CareerWeaponPolicy.ConfirmedNewPrimary(entity,
                    _purchasedWeapons.GetValueOrDefault(player.Slot)?.GetValueOrDefault(itemName) ?? 0,
                    old.Contains(entity), weapons.Length, _refundingWeapons.Contains(entity));
        }

        if (IsFirstRoundOfHalf()) 
            return true;

        // Check refund restrictions
        var (prevWeapons, _, _) = PreviousInventory(player);
        return !prevWeapons.Contains(itemName);
    }

    private bool Swap(CCSPlayerController player, string oldItem, string newItem)
    {
        if (!CanModify(player) || player.InGameMoneyServices == null
            || !CareerWeaponPolicy.CanBuy(_careerActive, newItem, PurchaseRole(player)))
            return false;

        var pawn = player.PlayerPawn.Value;
        if (pawn == null || !pawn.IsValid)
            return false;

        int primaryPrice = CareerTactics.TacticalBuyPolicy.PrimaryPrice(newItem);
        if (primaryPrice > 0 && (!CareerTactics.TacticalBuyPolicy.PrimaryAllowed(player.TeamNum == 3, newItem)
            || Math.Min((long)(ConVar.Find("mp_maxmoney")?.GetPrimitiveValue<int>() ?? 16000),
                (long)player.InGameMoneyServices.Account + CareerTactics.TacticalBuyPolicy.PrimaryPrice(oldItem)) < primaryPrice))
            return false; // Do not remove the old gun for an unaffordable or wrong-side replacement.

        int originalMoney = player.InGameMoneyServices.Account;
        if (!Refund(player, oldItem))
            return false;

        if (!Buy(player, newItem))
        {
            // This restores a verified existing purchase, not a new permission
            // to buy AUG or a second sniper. Restore its original balance too.
            if (Buy(player, oldItem, restoringOriginal: true))
            {
                player.InGameMoneyServices.Account = originalMoney;
                Utilities.SetStateChanged(player, "CCSPlayerController", "m_pInGameMoneyServices");
            }
            else
                Server.PrintToConsole("[BotBuy] Replacement and original weapon restore failed; refund retained.");
            return false;
        }
        return true;
    }

    private bool IsFirstRoundOfHalf()
    {
        try
        {
            var gameRules = Utilities
                .FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules")
                .FirstOrDefault()?.GameRules;

            if (gameRules == null)
                return false;

            int played = gameRules.TotalRoundsPlayed;
            int maxRounds = ConVar.Find("mp_maxrounds")?.GetPrimitiveValue<int>() ?? 24;
            int otMaxRounds = ConVar.Find("mp_overtime_maxrounds")?.GetPrimitiveValue<int>() ?? 6;

            if (maxRounds <= 0) maxRounds = 24;
            if (otMaxRounds <= 0) otMaxRounds = 6;

            int half = maxRounds / 2;
            int otHalf = otMaxRounds / 2;

            return played == 0
                || played == half
                || played == maxRounds
                || (played > maxRounds && (played - maxRounds) % otHalf == 0);
        }
        catch
        {
            return false;
        }
    }

    private bool IsSecondToLastRoundOfHalf()
    {
        try
        {
            var gameRules = Utilities
                .FindAllEntitiesByDesignerName<CCSGameRulesProxy>("cs_gamerules")
                .FirstOrDefault()?.GameRules;

            if (gameRules == null)
                return false;

            int played = gameRules.TotalRoundsPlayed;
            int maxRounds = ConVar.Find("mp_maxrounds")?.GetPrimitiveValue<int>() ?? 24;
            if (maxRounds <= 0) maxRounds = 24;
            int half = maxRounds / 2;

            return played == half - 2 || played == maxRounds - 2;
        }
        catch { return false; }
    }

    private int GetBotIndex(CCSPlayerController player)
    {
        if (!IsKnownBot(player)) return -1;
        int userId = player.UserId ?? -1;
        if (userId == -1) return -1;

        if (_botUserIdToIndex.TryGetValue(userId, out int idx)) return idx;
        int newIdx = ++_botIndexCounter;
        _botUserIdToIndex[userId] = newIdx;
        return newIdx;
    }

    private void RemoveBot(CCSPlayerController player)
    {
        if (player == null) return;
        int userId = player.UserId ?? -1;
        if (userId == -1) return;

        if (_botUserIdToIndex.Remove(userId, out int idx))
        {
            _prevWeapons.Remove(idx);
            _prevMoney.Remove(idx);
            _prevArmor.Remove(idx);
        }
    }

    private void SavePreviousInventory()
    {
        if (IsFirstRoundOfHalf())
        {
            _prevWeapons.Clear();
            _prevMoney.Clear();
            _prevArmor.Clear();
            return;
        }

        foreach (var player in Utilities.FindAllEntitiesByDesignerName<CCSPlayerController>("cs_player_controller"))
        {
            if (!IsKnownBot(player) || player.ControllingBot || player.HasBeenControlledByPlayerThisRound) continue;
            int idx = GetBotIndex(player);
            if (idx == -1) continue;

            var pawn = player.PlayerPawn.Value;
            if (pawn == null || !pawn.IsValid) continue;

            List<string> weapons = new();
            if (pawn.WeaponServices != null)
            {
                foreach (var wHandle in pawn.WeaponServices.MyWeapons)
                {
                    var w = wHandle.Value;
                    if (w == null) continue;
                    string name = w.DesignerName;
                    if (name == "item_kevlar" || name == "item_assaultsuit" || name == "item_defuser") continue;
                    weapons.Add(name);
                }
            }

            int money = player.InGameMoneyServices?.Account ?? 0;
            int armor = pawn.ArmorValue;

            _prevWeapons[idx] = weapons;
            _prevMoney[idx] = money;
            _prevArmor[idx] = armor;
        }
    }

    private void ClearPreviousInventory(CCSPlayerController player)
    {
        if (!IsKnownBot(player))
            return;

        int idx = GetBotIndex(player);
        if (idx == -1) return;

        _prevWeapons.Remove(idx);
        _prevArmor.Remove(idx);
    }

    private (List<string> Weapons, int Money, int Armor) Inventory(CCSPlayerController player)
    {
        List<string> weapons = new();
        int money = 0;
        int armor = 0;

        if (!IsKnownBot(player)) return (weapons, money, armor);
        int idx = GetBotIndex(player);
        if (idx == -1) return (weapons, money, armor);

        var pawn = player.PlayerPawn.Value;
        if (pawn == null || !pawn.IsValid) return (weapons, money, armor);

        money = player.InGameMoneyServices?.Account ?? 0;
        armor = pawn.ArmorValue;

        if (pawn.WeaponServices != null)
        {
            foreach (var wHandle in pawn.WeaponServices.MyWeapons)
            {
                var w = wHandle.Value;
                if (w == null) continue;
                string name = w.DesignerName;
                if (name == "item_kevlar" || name == "item_assaultsuit" || name == "item_defuser") continue;
                weapons.Add(name);
            }
        }

        return (weapons, money, armor);
    }

    private (List<string> Weapons, int Money, int Armor) PreviousInventory(CCSPlayerController player)
    {
        List<string> weapons = new();
        int money = 0;
        int armor = 0;

        if (!IsKnownBot(player)) return (weapons, money, armor);
        int idx = GetBotIndex(player);
        if (idx == -1) return (weapons, money, armor);

        if (IsFirstRoundOfHalf()) return (weapons, money, armor);

        if (_prevWeapons.TryGetValue(idx, out var w)) weapons = w;
        if (_prevMoney.TryGetValue(idx, out int m)) money = m;
        if (_prevArmor.TryGetValue(idx, out int a)) armor = a;

        return (weapons, money, armor);
    }
}
//----------------------------------------------------------------------------------------------
