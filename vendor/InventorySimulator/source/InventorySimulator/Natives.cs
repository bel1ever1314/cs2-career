// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Memory;
using CounterStrikeSharp.API.Modules.Memory.DynamicFunctions;
using CounterStrikeSharp.API.Modules.Utils;

namespace InventorySimulator;

public static class Natives
{
	public static readonly MemoryFunctionWithReturn<nint, string, float, int> CAttributeList_SetOrAddAttributeValueByName = new MemoryFunctionWithReturn<nint, string, float, int>(GameData.GetSignature("CAttributeList::SetOrAddAttributeValueByName"));

	private static readonly Lazy<int> _lazyCCSPlayerController_InventoryServices_m_pInventory = new Lazy<int>(() => GameData.GetOffset("CCSPlayerController_InventoryServices::m_pInventory"));

	public static readonly MemoryFunctionWithReturn<nint, nint, int, bool, float> CCSPlayerController_ProcessUsercmds = new MemoryFunctionWithReturn<nint, nint, int, bool, float>(GameData.GetSignature("CCSPlayerController::ProcessUsercmds"));

	public static readonly MemoryFunctionWithReturn<nint, int, int, nint> CCSPlayerInventory_GetItemInLoadout = new MemoryFunctionWithReturn<nint, int, int, nint>(GameData.GetSignature("CCSPlayerInventory::GetItemInLoadout"));

	private static readonly Lazy<int> _lazyCCSPlayerInventory_m_pSOCache = new Lazy<int>(() => GameData.GetOffset("CCSPlayerInventory::m_pSOCache"));

	public static readonly MemoryFunctionWithReturn<nint, nint> CCSPlayerInventory_SendInventoryUpdateEvent = new MemoryFunctionWithReturn<nint, nint>(GameData.GetSignature("CCSPlayerInventory::SendInventoryUpdateEvent"));

	public static readonly MemoryFunctionWithReturn<nint, nint, nint, nint, nint> CCSPlayerPawn_IsAbleToApplySpray = new MemoryFunctionWithReturn<nint, nint, nint, nint, nint>(GameData.GetSignature("CCSPlayerPawn::IsAbleToApplySpray"));

	public static readonly MemoryFunctionVoid<nint> CCSPlayerPawn_SetModelFromClass = new MemoryFunctionVoid<nint>(GameData.GetSignature("CCSPlayerPawn::SetModelFromClass"));

	public static readonly MemoryFunctionWithReturn<nint, nint> CCSPlayerPawn_SetModelFromLoadout = new MemoryFunctionWithReturn<nint, nint>(GameData.GetSignature("CCSPlayerPawn::SetModelFromLoadout"));

	public static readonly MemoryFunctionVoid<nint> CCSPlayer_ItemServices_SetWearables = new MemoryFunctionVoid<nint>(GameData.GetSignature("CCSPlayer_ItemServices::SetWearables"));

	public static readonly MemoryFunctionWithReturn<nint, uint, byte, nint> CEconItemSchema_GetItemDefinition = new MemoryFunctionWithReturn<nint, uint, byte, nint>(GameData.GetSignature("CEconItemSchema::GetItemDefinition"));

	public static readonly MemoryFunctionWithReturn<nint, string, nint> CEconItemSchema_GetItemDefinitionByName = new MemoryFunctionWithReturn<nint, string, nint>(GameData.GetSignature("CEconItemSchema::GetItemDefinitionByName"));

	public static readonly MemoryFunctionWithReturn<nint, nint> CEconItemView_Constructor = new MemoryFunctionWithReturn<nint, nint>(GameData.GetSignature("CEconItemView::CEconItemView"));

	public static readonly MemoryFunctionWithReturn<nint, nint, nint> CEconItemView_OperatorEquals = new MemoryFunctionWithReturn<nint, nint, nint>(GameData.GetSignature("CEconItemView::operator="));

	private static readonly Lazy<int> _lazyCGCClientSharedObjectCache_m_Owner = new Lazy<int>(() => GameData.GetOffset("CGCClientSharedObjectCache::m_Owner"));

	public static readonly MemoryFunctionVoid<nint> CServerSideClientBase_ActivatePlayer = new MemoryFunctionVoid<nint>(GameData.GetSignature("CServerSideClientBase::ActivatePlayer"), Addresses.EnginePath);

	private static readonly Lazy<int> _lazyCServerSideClientBase_m_UserID = new Lazy<int>(() => GameData.GetOffset("CServerSideClientBase::m_UserID"));

	public static readonly MemoryFunctionWithReturn<nint> GetItemSchema = new MemoryFunctionWithReturn<nint>(GameData.GetSignature("GetItemSchema"));

	public static int CCSPlayerController_InventoryServices_m_pInventory => _lazyCCSPlayerController_InventoryServices_m_pInventory.Value;

	public static int CCSPlayerInventory_m_pSOCache => _lazyCCSPlayerInventory_m_pSOCache.Value;

	public static int CGCClientSharedObjectCache_m_Owner => _lazyCGCClientSharedObjectCache_m_Owner.Value;

	public static int CServerSideClientBase_m_UserID => _lazyCServerSideClientBase_m_UserID.Value;

	public static void CCSPlayer_WeaponServices_DropWeapon(nint thisPtr, nint weaponPtr)
	{
		VirtualFunction.CreateVoid<nint, nint, Vector, Vector>(thisPtr, GameData.GetOffset("CCSPlayer_WeaponServices::DropWeapon"))(thisPtr, weaponPtr, null, null);
	}
}
