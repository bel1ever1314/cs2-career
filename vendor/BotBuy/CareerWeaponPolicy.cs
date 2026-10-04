// Pure purchase rules. Native pickups and a human's inventory are not loadouts.
namespace BotBuyPatch;

using CareerTactics;

internal static class CareerWeaponPolicy
{
    internal static bool IsForbidden(string weapon) => weapon is
        "weapon_aug" or "weapon_scar20" or "weapon_g3sg1";

    internal static bool CanModify(bool valid, bool nativeBot, bool requestBot,
        bool controlling, bool wasControlled, bool originalPawnIsSelf, bool alive) =>
        valid && (nativeBot || requestBot) && !controlling && !wasControlled
        && originalPawnIsSelf && alive;

    internal static bool CanBuy(bool active, string weapon, string role, bool restoringOriginal = false) =>
        restoringOriginal || !active || (!IsForbidden(weapon) && (weapon != "weapon_awp" || role == "awp"));

    internal static string OvertimeWeapon(bool active, string role, bool ct, float roll)
    {
        if (active)
            return role == "awp" ? "weapon_awp" : Rifle(ct, roll);
        if (ct)
            return roll < .35f ? "weapon_m4a1" : roll < .70f ? "weapon_m4a1_silencer"
                : roll < .90f ? "weapon_awp" : "weapon_scar20";
        return roll < .70f ? "weapon_ak47" : roll < .90f ? "weapon_awp" : "weapon_g3sg1";
    }

    internal static string Rifle(bool ct, float roll) => !ct ? "weapon_ak47"
        : roll < .5f ? "weapon_m4a1" : "weapon_m4a1_silencer";

    internal static bool HasPrimary(IEnumerable<string> weapons) =>
        weapons.Any(weapon => TacticalBuyPolicy.PrimaryPrice(weapon) > 0);

    internal static string[] EmptyPrimaryCandidates(bool active, bool eligible, bool buying,
        bool pistolRound, bool hasPrimary, bool ct, string role, int money, int reserve, float rifleRoll)
    {
        // Keep native pistol/eco decisions, and leave the armor/utility reserve intact.
        if (!active || !eligible || !buying || pistolRound || hasPrimary || money < 2800 || reserve < 0)
            return [];

        string rifle = Rifle(ct, rifleRoll);
        string alternateRifle = rifle == "weapon_m4a1" ? "weapon_m4a1_silencer" : "weapon_m4a1";
        string economyRifle = ct ? "weapon_famas" : "weapon_galilar";
        var candidates = new List<string>();
        if (role == "awp") candidates.Add("weapon_awp");
        candidates.Add(rifle);
        if (ct) candidates.Add(alternateRifle);
        candidates.Add(economyRifle);
        // A sniper who cannot afford an AWP still prefers an ordinary rifle.
        if (role == "awp") candidates.Add("weapon_ssg08");
        return candidates.Where(weapon => CanBuy(active, weapon, role)
            && TacticalBuyPolicy.PrimaryAllowed(ct, weapon)
            && TacticalBuyPolicy.PrimaryPrice(weapon) <= (long)money - reserve)
            .Distinct(StringComparer.Ordinal).ToArray();
    }

    // A Scout is a valid economical sniper choice, not a cheap rifle to undo.
    internal static bool IsEconomyPrimary(bool ct, string weapon) => weapon is
        "weapon_mp7" or "weapon_mp5sd" or "weapon_ump45" or "weapon_bizon" or "weapon_p90"
        or "weapon_nova" or "weapon_xm1014" or "weapon_negev"
        || (ct ? weapon is "weapon_famas" or "weapon_mp9" or "weapon_mag7"
               : weapon is "weapon_galilar" or "weapon_mac10" or "weapon_sawedoff");

    internal static int ArmorReserve(bool ct, int armor, bool helmet) =>
        armor <= 40 ? (!ct && !helmet ? 1000 : 650)
        : !ct && !helmet ? (armor >= 100 ? 350 : 1000) : 0;

    internal static int GiftArmorPrice(bool ct, int money, int reserve)
    {
        if (money < 0 || reserve < 0) return 0;
        int spendable = money - reserve;
        return spendable >= 1000 ? 1000 : ct && spendable >= 650 ? 650 : 0;
    }

    internal static bool ConfirmedNewPrimary(uint entity, uint bought, bool existedAtStart, int matchingItems,
        bool pendingRemoval = false) =>
        entity != 0 && entity == bought && !existedAtStart && matchingItems == 1 && !pendingRemoval;

    internal static bool CanUpgradeEconomyPrimary(bool active, bool eligible, bool buying,
        bool ct, string role, string weapon, int money, int reserve, int maxMoney,
        uint entity, uint bought, bool existedAtStart, int primaryCount, bool refundable) =>
        active && eligible && buying && role != "awp" && IsEconomyPrimary(ct, weapon)
        && money >= 0 && reserve >= 0 && maxMoney > 0
        && Math.Min((long)maxMoney, (long)money + TacticalBuyPolicy.PrimaryPrice(weapon))
            >= TacticalBuyPolicy.PrimaryPrice(Rifle(ct, .25f)) + (long)reserve
        && entity != 0 && entity == bought && !existedAtStart && primaryCount == 1 && refundable;

    internal static bool ShouldReplacePurchase(bool active, bool eligible, bool purchasePhase,
        string weapon, uint entity, uint purchasedEntity, bool existedAtRoundStart,
        int matchingItems, bool refundable) => active && eligible && purchasePhase
        && IsForbidden(weapon) && entity != 0 && entity == purchasedEntity
        && !existedAtRoundStart && matchingItems == 1 && refundable;
}
