using CounterStrikeSharp.API.Core;

namespace BotBuyPatch;

public sealed partial class BotBuyPatch
{
    // CS2 shares entity classes across some item variants. For example a
    // silenced M4 can have DesignerName weapon_m4a1 but item definition 60.
    // Use the actual item when matching a purchase, not just its entity class.
    private static string WeaponName(CBasePlayerWeapon weapon) =>
        weapon.AttributeManager.Item.ItemDefinitionIndex switch
        {
            16 => "weapon_m4a1",
            60 => "weapon_m4a1_silencer",
            32 => "weapon_hkp2000",
            61 => "weapon_usp_silencer",
            36 => "weapon_p250",
            63 => "weapon_cz75a",
            1 => "weapon_deagle",
            64 => "weapon_revolver",
            33 => "weapon_mp7",
            23 => "weapon_mp5sd",
            _ => weapon.DesignerName
        };
}
