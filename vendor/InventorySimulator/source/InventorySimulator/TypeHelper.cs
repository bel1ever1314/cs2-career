// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Runtime.CompilerServices;

namespace InventorySimulator;

public static class TypeHelper
{
	public static TTo ViewAs<TFrom, TTo>(TFrom value) where TFrom : unmanaged where TTo : unmanaged
	{
		if (Unsafe.SizeOf<TFrom>() != Unsafe.SizeOf<TTo>())
		{
			throw new ArgumentException("Size mismatch");
		}
		return Unsafe.As<TFrom, TTo>(ref value);
	}
}
