// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;

namespace InvsimCareer;

public class InvsimCareer : BasePlugin
{
	public override string ModuleName => "InvsimCareer";

	public override string ModuleVersion => "1.0.2";

	public override string ModuleAuthor => "CS2 Career";

	public override void Load(bool hotReload)
	{
		Apply();
		RegisterListener<Listeners.OnMapStart>(delegate
		{
			AddTimer(1f, Apply);
		});
	}

	private void Apply()
	{
		TrySet("Url", "http://127.0.0.1:18768");
		TrySet("IsWsEnabled", true);
		TrySet("IsWsImmediately", false);
		TrySet("IsFallbackTeam", true);
		TrySet("MinModels", 1);
		TrySet("IsSprayEnabled", false);
		TrySet("IsSprayOnUse", false);
		TrySet("IsPublicApiStatTrakIncrement", false);
		TrySet("IsPublicApiSprayConsume", false);
		string text = ReadOwnerSteamId();
		if (text != "")
		{
			TrySet("OnlySteamId", text);
		}
	}

	private static string ReadOwnerSteamId()
	{
		try
		{
			string[] buffer = new string[7];
			buffer[0] = Server.GameDirectory;
			buffer[1] = "csgo";
			buffer[2] = "addons";
			buffer[3] = "counterstrikesharp";
			buffer[4] = "configs";
			buffer[5] = "plugins";
			buffer[6] = "InventorySimulator";
			string path = Path.Combine(buffer);
			string path2 = Path.Combine(path, "owner.txt");
			if (File.Exists(path2))
			{
				string text = new string(File.ReadAllText(path2).Where(char.IsDigit).ToArray());
				if (text.Length >= 10)
				{
					return text;
				}
			}
			string path3 = Path.Combine(path, "inventories.json");
			if (!File.Exists(path3))
			{
				return "";
			}
			using JsonDocument jsonDocument = JsonDocument.Parse(File.ReadAllText(path3));
			foreach (JsonProperty item in jsonDocument.RootElement.EnumerateObject())
			{
				string text2 = new string(item.Name.Where(char.IsDigit).ToArray());
				if (text2.Length >= 10)
				{
					return text2;
				}
			}
		}
		catch
		{
		}
		return "";
	}

	private static void TrySet(string field, object value)
	{
		Assembly[] assemblies = AppDomain.CurrentDomain.GetAssemblies();
		for (int i = 0; i < assemblies.Length; i++)
		{
			Type type = assemblies[i].GetType("InventorySimulator.ConVars");
			if (!(type == null))
			{
				object obj = type.GetField(field, BindingFlags.Static | BindingFlags.Public)?.GetValue(null);
				PropertyInfo propertyInfo = obj?.GetType().GetProperty("Value");
				if (!(propertyInfo == null) && propertyInfo.CanWrite)
				{
					propertyInfo.SetValue(obj, value);
				}
				break;
			}
		}
	}
}
