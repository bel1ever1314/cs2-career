// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.CodeDom.Compiler;
using System.Globalization;
using System.Runtime.CompilerServices;

namespace System.Text.RegularExpressions.Generated;

[GeneratedCode("System.Text.RegularExpressions.Generator", "10.0.14.32716")]
internal static class _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__Utilities
{
	internal static readonly TimeSpan s_defaultTimeout = ((AppContext.GetData("REGEX_DEFAULT_MATCH_TIMEOUT") is TimeSpan timeSpan) ? timeSpan : Regex.InfiniteMatchTimeout);

	internal static readonly bool s_hasTimeout = s_defaultTimeout != Regex.InfiniteMatchTimeout;

	private const int WordCategoriesMask = 262463;

	private static ReadOnlySpan<byte> WordCharBitmap => new byte[16]
	{
		0, 0, 0, 0, 0, 0, 255, 3, 254, 255,
		255, 135, 254, 255, 255, 7
	};

	[MethodImpl(MethodImplOptions.AggressiveInlining)]
	internal static bool IsWordChar(char ch)
	{
		ReadOnlySpan<byte> wordCharBitmap = WordCharBitmap;
		int num = (int)ch >> 3;
		if ((uint)num >= (uint)wordCharBitmap.Length)
		{
			return (0x4013F & (1 << (int)CharUnicodeInfo.GetUnicodeCategory(ch))) != 0;
		}
		return (wordCharBitmap[num] & (1 << (ch & 7))) != 0;
	}
}
