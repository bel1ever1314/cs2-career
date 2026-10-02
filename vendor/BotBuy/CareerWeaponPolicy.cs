// Pure purchase rules. Native pickups and a human's inventory are not loadouts.
namespace BotBuyPatch;

internal static class CareerWeaponPolicy
{
    internal static bool IsForbidden(string weapon) => weapon is
        "weapon_aug" or "weapon_scar20" or "weapon_g3sg1";

    internal static bool CanModify(bool valid, bool nativeBot, bool requestBot,
        bool controlling, bool wasControlled, bool originalPawnIsSelf, bool alive) =>
        valid && (nativeBot || requestBot) && !controlling && !wasControlled
        && originalPawnIsSelf && alive;

    internal static bool CanBuy(bool active, string weapon, string role) =>
        !active || (!IsForbidden(weapon) && (weapon != "weapon_awp" || role == "awp"));

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

    internal static bool ShouldReplacePurchase(bool active, bool eligible, bool purchasePhase,
        string weapon, uint entity, uint purchasedEntity, bool existedAtRoundStart,
        int matchingItems, bool refundable) => active && eligible && purchasePhase
        && IsForbidden(weapon) && entity != 0 && entity == purchasedEntity
        && !existedAtRoundStart && matchingItems == 1 && refundable;
}
