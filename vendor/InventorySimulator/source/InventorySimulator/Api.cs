// Source recovered from the supplied DLL using ILSpy 11.0.0.9375; see RECOVERED_SOURCE.md.
using System;
using System.Collections.Concurrent;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace InventorySimulator;

public class Api
{
	private class RateLimitBucket(double capacity, double refillIntervalSeconds)
	{
		private readonly double _capacity = capacity;

		private double _tokens = capacity;

		private DateTime _updatedAt = DateTime.UtcNow;

		public bool TryConsume()
		{
			lock (this)
			{
				DateTime utcNow = DateTime.UtcNow;
				double totalSeconds = (utcNow - _updatedAt).TotalSeconds;
				_tokens = Math.Min(_capacity, _tokens + totalSeconds / refillIntervalSeconds);
				_updatedAt = utcNow;
				if (_tokens < 1.0)
				{
					return false;
				}
				_tokens--;
				return true;
			}
		}
	}

	private static readonly HttpClient _httpClient = new HttpClient
	{
		Timeout = TimeSpan.FromSeconds(30L)
	};

	private const int MaxRetries = 3;

	private const int RetryDelayMs = 100;

	private const double StatTrakIncrementRateLimitCapacity = 50.0;

	private const double StatTrakIncrementRateLimitRefillIntervalSeconds = 3.6;

	private const double SprayConsumeRateLimitCapacity = 1.0;

	private const double SprayConsumeRateLimitRefillIntervalSeconds = 30.0;

	private static volatile bool _isSuspended = false;

	private static readonly ConcurrentDictionary<(ulong, int), RateLimitBucket> _statTrakBuckets = new ConcurrentDictionary<(ulong, int), RateLimitBucket>();

	private static readonly ConcurrentDictionary<(ulong, int), RateLimitBucket> _sprayBuckets = new ConcurrentDictionary<(ulong, int), RateLimitBucket>();

	public static void ResetSuspension()
	{
		_isSuspended = false;
	}

	public static string GetUrl(string pathname = "")
	{
		return ConVars.Url.Value + pathname;
	}

	public static bool HasApiKey()
	{
		return ConVars.ApiKey.Value != "";
	}

	private static string? GetApiKeyOrNull()
	{
		if (!HasApiKey())
		{
			return null;
		}
		return ConVars.ApiKey.Value;
	}

	private static async Task<HttpResponseMessage?> SendPostAsync(string url, object request, bool suspendOnUnauthorized = false)
	{
		try
		{
			JsonContent content = JsonContent.Create(request);
			HttpResponseMessage httpResponseMessage = await _httpClient.PostAsync(url, content);
			if (httpResponseMessage.StatusCode == HttpStatusCode.Unauthorized)
			{
				if (suspendOnUnauthorized)
				{
					_isSuspended = true;
				}
				Runtime.Plugin.Logger.LogError("POST {Url} failed, check your invsim_apikey's value.", url);
				return null;
			}
			if (!httpResponseMessage.IsSuccessStatusCode)
			{
				Runtime.Plugin.Logger.LogError("POST {Url} failed with status code: {StatusCode}", url, httpResponseMessage.StatusCode);
				return null;
			}
			return httpResponseMessage;
		}
		catch (Exception ex)
		{
			Runtime.Plugin.Logger.LogError("POST {Url} failed: {Message}", url, ex.Message);
			return null;
		}
	}

	private static async Task PostAsync(string url, object request)
	{
		await SendPostAsync(url, request);
	}

	private static bool CanSendPublicApiRequest(bool isEnabled, ConcurrentDictionary<(ulong, int), RateLimitBucket> buckets, ulong userId, int targetUid, double capacity, double refillIntervalSeconds)
	{
		if (HasApiKey())
		{
			return true;
		}
		if (!isEnabled)
		{
			return false;
		}
		return buckets.GetOrAdd((userId, targetUid), ((ulong, int) _) => new RateLimitBucket(capacity, refillIntervalSeconds)).TryConsume();
	}

	private static async Task<T?> PostAsync<T>(string url, object request) where T : class
	{
		HttpResponseMessage httpResponseMessage = await SendPostAsync(url, request);
		if (httpResponseMessage == null)
		{
			return null;
		}
		string text = await httpResponseMessage.Content.ReadAsStringAsync();
		return string.IsNullOrEmpty(text) ? null : JsonSerializer.Deserialize<T>(text);
	}

	public static async Task<EquippedV5Response?> FetchEquippedAsync(ulong steamId)
	{
		string url = GetUrl($"/api/equipped/v5/{steamId}.json");
		for (int attempt = 1; attempt <= 3; attempt++)
		{
			try
			{
				HttpResponseMessage obj = await _httpClient.GetAsync(url);
				obj.EnsureSuccessStatusCode();
				return JsonSerializer.Deserialize<EquippedV5Response>(await obj.Content.ReadAsStringAsync());
			}
			catch (Exception ex)
			{
				Runtime.Plugin.Logger.LogError("GET {Url} failed (attempt {Attempt}/{MaxRetries}): {Message}", url, attempt, 3, ex.Message);
				if (attempt == 3)
				{
					return null;
				}
				await Task.Delay(TimeSpan.FromMilliseconds(100 * attempt));
			}
		}
		return null;
	}

	public static async Task SendStatTrakIncrementAsync(ulong userId, int targetUid)
	{
		if (!_isSuspended && CanSendPublicApiRequest(ConVars.IsPublicApiStatTrakIncrement.Value, _statTrakBuckets, userId, targetUid, 50.0, 3.6))
		{
			string url = GetUrl("/api/increment-item-stattrak");
			StatTrakIncrementRequest request = new StatTrakIncrementRequest
			{
				ApiKey = GetApiKeyOrNull(),
				TargetUid = targetUid,
				UserId = userId.ToString()
			};
			await SendPostAsync(url, request, suspendOnUnauthorized: true);
		}
	}

	public static async void SendStatTrakIncrement(ulong userId, int targetUid)
	{
		await SendStatTrakIncrementAsync(userId, targetUid);
	}

	public static async Task SendConsumeItemSprayAsync(ulong userId, int targetUid)
	{
		if (!_isSuspended && CanSendPublicApiRequest(ConVars.IsPublicApiSprayConsume.Value, _sprayBuckets, userId, targetUid, 1.0, 30.0))
		{
			string url = GetUrl("/api/consume-item-spray");
			ConsumeItemSprayRequest request = new ConsumeItemSprayRequest
			{
				ApiKey = GetApiKeyOrNull(),
				TargetUid = targetUid,
				UserId = userId.ToString()
			};
			await SendPostAsync(url, request, suspendOnUnauthorized: true);
		}
	}

	public static async void SendConsumeItemSpray(ulong userId, int targetUid)
	{
		await SendConsumeItemSprayAsync(userId, targetUid);
	}

	public static async Task<SignInUserResponse?> SendSignIn(string userId)
	{
		string url = GetUrl("/api/sign-in");
		SignInRequest request = new SignInRequest
		{
			ApiKey = ConVars.ApiKey.Value,
			UserId = userId
		};
		return await PostAsync<SignInUserResponse>(url, request);
	}
}
