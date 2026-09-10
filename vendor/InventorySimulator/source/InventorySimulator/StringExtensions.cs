// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.CodeDom.Compiler;
using System.Text.RegularExpressions;
using System.Text.RegularExpressions.Generated;

namespace InventorySimulator;

public static class StringExtensions
{
	public static string StripColorTags(this string self)
	{
		return ColorTag().Replace(self, "");
	}

	// Generated implementation is already recovered below; do not run the generator again.
	[GeneratedCode("System.Text.RegularExpressions.Generator", "10.0.14.32716")]
	private static Regex ColorTag()
	{
		return _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__ColorTag_0.Instance;
	}
}
