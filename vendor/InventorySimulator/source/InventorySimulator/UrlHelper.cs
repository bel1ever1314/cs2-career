// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.CodeDom.Compiler;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Text.RegularExpressions.Generated;

namespace InventorySimulator;

public static class UrlHelper
{
	public static string FormatUrl(string format, string urlString)
	{
		if (!Uri.TryCreate(urlString, UriKind.Absolute, out Uri uri))
		{
			return format;
		}
		return PlaceholderPattern().Replace(format, (Match match) => uri.GetType().GetProperty(match.Groups[1].Value, BindingFlags.Instance | BindingFlags.Public)?.GetValue(uri)?.ToString() ?? match.Value);
	}

	// Generated implementation is already recovered below; do not run the generator again.
	[GeneratedCode("System.Text.RegularExpressions.Generator", "10.0.14.32716")]
	private static Regex PlaceholderPattern()
	{
		return _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__PlaceholderPattern_1.Instance;
	}
}
