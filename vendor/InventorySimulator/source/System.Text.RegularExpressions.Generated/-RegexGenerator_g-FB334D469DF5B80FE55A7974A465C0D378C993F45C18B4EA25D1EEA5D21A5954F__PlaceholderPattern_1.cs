// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System.CodeDom.Compiler;
using System.Runtime.CompilerServices;

namespace System.Text.RegularExpressions.Generated;

[GeneratedCode("System.Text.RegularExpressions.Generator", "10.0.14.32716")]
[SkipLocalsInit]
internal sealed class _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__PlaceholderPattern_1 : Regex
{
	private sealed class RunnerFactory : RegexRunnerFactory
	{
		private sealed class Runner : RegexRunner
		{
			protected override void Scan(ReadOnlySpan<char> inputSpan)
			{
				while (TryFindNextPossibleStartingPosition(inputSpan) && !TryMatchAtCurrentPosition(inputSpan) && runtextpos != inputSpan.Length)
				{
					runtextpos++;
					if (_003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__Utilities.s_hasTimeout)
					{
						CheckTimeout();
					}
				}
			}

			private bool TryFindNextPossibleStartingPosition(ReadOnlySpan<char> inputSpan)
			{
				int num = runtextpos;
				if (num <= inputSpan.Length - 3)
				{
					ReadOnlySpan<char> readOnlySpan = inputSpan.Slice(num);
					int num2;
					for (num2 = 0; num2 < readOnlySpan.Length - 2; num2++)
					{
						int num3 = readOnlySpan.Slice(num2).IndexOf('{');
						if (num3 < 0)
						{
							break;
						}
						num2 += num3;
						if ((uint)(num2 + 1) >= (uint)readOnlySpan.Length)
						{
							break;
						}
						if (_003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__Utilities.IsWordChar(readOnlySpan[num2 + 1]))
						{
							runtextpos = num + num2;
							return true;
						}
					}
				}
				runtextpos = inputSpan.Length;
				return false;
			}

			private bool TryMatchAtCurrentPosition(ReadOnlySpan<char> inputSpan)
			{
				int num = runtextpos;
				int start = num;
				int num2 = 0;
				ReadOnlySpan<char> readOnlySpan = inputSpan.Slice(num);
				if (readOnlySpan.IsEmpty || readOnlySpan[0] != '{')
				{
					UncaptureUntil(0);
					return false;
				}
				num++;
				readOnlySpan = inputSpan.Slice(num);
				num2 = num;
				int i;
				for (i = 0; (uint)i < (uint)readOnlySpan.Length && _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__Utilities.IsWordChar(readOnlySpan[i]); i++)
				{
				}
				if (i == 0)
				{
					UncaptureUntil(0);
					return false;
				}
				readOnlySpan = readOnlySpan.Slice(i);
				num += i;
				Capture(1, num2, num);
				if (readOnlySpan.IsEmpty || readOnlySpan[0] != '}')
				{
					UncaptureUntil(0);
					return false;
				}
				Capture(0, start, runtextpos = num + 1);
				return true;
				[MethodImpl(MethodImplOptions.AggressiveInlining)]
				void UncaptureUntil(int capturePosition)
				{
					while (Crawlpos() > capturePosition)
					{
						Uncapture();
					}
				}
			}
		}

		protected override RegexRunner CreateInstance()
		{
			return new Runner();
		}
	}

	internal static readonly _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__PlaceholderPattern_1 Instance = new _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__PlaceholderPattern_1();

	private _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__PlaceholderPattern_1()
	{
		pattern = "\\{(\\w+)\\}";
		roptions = RegexOptions.None;
		Regex.ValidateMatchTimeout(_003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__Utilities.s_defaultTimeout);
		internalMatchTimeout = _003CRegexGenerator_g_003EFB334D469DF5B80FE55A7974A465C0D378C993F45C18B4EA25D1EEA5D21A5954F__Utilities.s_defaultTimeout;
		factory = new RunnerFactory();
		capsize = 2;
	}
}
