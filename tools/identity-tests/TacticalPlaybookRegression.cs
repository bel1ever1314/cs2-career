using System.Text.Json;
using CareerMatch;

internal static class TacticalPlaybookRegression
{
    public static void Run()
    {
        int count = 0;
        void Check(bool value, string label) { count++; if (!value) throw new Exception(label); }
        string Valid() => JsonSerializer.Serialize(new TacticalPlaybook { Version = 1, Map = "de_dust2",
            Tactics = [new() { Id = "short_split", Name = "沙二分路", Side = "t",
                Slots = Enumerable.Range(1, 5).Select(s => new CustomTacticSlot { Slot = s,
                    Steps = s == 1 ? [] : [new() { Position = [10*s, 100], Wait = 2, Level = "auto" }] }).ToList() }] },
            new JsonSerializerOptions { Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });
        var json = Valid(); var playbook = TacticalPlaybook.Parse(json);
        Check(playbook.Tactics.Count == 1 && playbook.Tactics[0].Slots.Count == 5, "strict five-slot round trip");
        var sample = TacticalPlaybook.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "tactical_playbook.json")));
        Check(sample.Tactics.Count == 2 && sample.Tactics.Any(t => t.Id == "split_test")
            && sample.Tactics.Any(t => t.Id == "defend_test"), "actual shipped split and defense playbooks parse");
        void Reject(string source, string label)
        {
            var rejected = false;
            try { TacticalPlaybook.Parse(source); } catch (Exception) { rejected = true; }
            Check(rejected, label);
        }
        Check(TacticalPlaybook.Parse(json.Replace(",\"movement\":\"run\"", "")).Tactics[0].Slots[1].Steps[0].Movement == "run",
            "old waypoint without movement defaults to running");
        Check(TacticalPlaybook.Parse(json.Replace("\"movement\":\"run\"", "\"movement\":\"walk\""))
            .Tactics[0].Slots[1].Steps[0].Movement == "walk", "explicit walk survives parse");
        foreach (var invalidMovement in new[] { "null", "true", "0", "{}", "[]", "\"sprint\"", "\"W\"", "\"\"" })
            Reject(json.Replace("\"movement\":\"run\"", "\"movement\":"+invalidMovement), "invalid movement " + invalidMovement);
        Reject(json.Replace("\"schema_version\":1", "\"schema_version\":2"), "unknown schema");
        Reject(json.Replace("de_dust2", "de_unknown"), "unsupported map");
        Reject(json.Replace("\"map\":\"de_dust2\"", "\"map\":null"), "null map rejected as invalid header");
        Check(!TacticalMapCatalog.IsSupported(null), "null map support check is safe");
        Check(TacticalMapCatalog.MapIds.Count() == 10, "ten official radar maps in shared registry");
        foreach (var map in TacticalMapCatalog.MapIds)
            Check(TacticalPlaybook.Parse(json.Replace("de_dust2", map)).Map == map,
                "schema one map-specific library parses " + map);
        Check(TacticalMapCatalog.Matches("de_nuke", "nuke") && TacticalMapCatalog.Matches("de_nuke", "de_nuke"),
            "request short name and live canonical map both match");
        Check(!TacticalMapCatalog.Matches("de_dust2", "de_mirage")
            && !TacticalMapCatalog.Matches("de_unknown", "de_unknown")
            && !TacticalMapCatalog.Matches("de_dust2", "workshop/123/de_dust2"), "cross-map or unknown live map cannot consume library");
        var mirage = json.Replace("de_dust2", "de_mirage").Replace("\"position\":[20,100]", "\"position\":[-3000,100]");
        Check(TacticalPlaybook.Parse(mirage).Map == "de_mirage", "Mirage uses own coarse coordinate bounds");
        Reject(mirage.Replace("de_mirage", "de_dust2"), "foreign coordinates not valid just by relabelling map");
        CheckMapBoundariesAndLevels(json, Check);
        Reject(json.Replace("short_split", "UPPER"), "uppercase ID");
        Reject(json.Replace("short_split", "a;quit"), "command characters rejected");
        Reject(json.Replace("short_split", new string('a', 33)), "ID bound");
        Reject(json.Replace("沙二分路", new string('x', 41)), "name bound");
        Reject(json.Replace("沙二分路", "abc\\u200b"), "name format category rejected");
        Reject(json.Replace("沙二分路", "abc\\ue000"), "name private-use category rejected");
        Reject(json.Replace("\"side\":\"t\"", "\"side\":\"spectator\""), "unknown side");
        Reject(json.Replace("\"wait\":2", "\"wait\":31"), "wait bound");
        Reject(json.Replace("\"wait\":2", "\"wait\":-1"), "negative wait");
        Reject(json.Replace("\"level\":\"auto\"", "\"level\":\"roof\""), "unknown floor");
        Reject(json.Replace("\"slot\":5", "\"slot\":4"), "duplicate/missing team slot");
        Reject(json.Replace("\"position\":[20,100]", "\"position\":[20,100,0]"), "three-dimensional input rejected");
        Reject(json.Replace("\"position\":[20,100]", "\"position\":[40000,100]"), "coordinate bound");
        Reject(json.Replace("\"look_at\":null", "\"look_at\":[0]"), "look direction shape");
        Reject(json.Replace(",\"look_at\":null", ""), "missing explicit look field rejected");
        Reject("{\"schema_version\":1,\"map\":\"de_dust2\"}", "missing tactics rejected");
        Reject(json[..^1] + ",\"enemy_id\":\"e1\"}", "unknown root field");
        Reject(json[..^1] + ",\"schema_version\":1}", "duplicate JSON key");
        Reject(new string(' ', TacticalPlaybook.MaximumBytes) + json, "byte bound");
        var many = TacticalPlaybook.Parse(json);
        many.Tactics = Enumerable.Range(1, 21).Select(i => new CustomTactic { Id = "id"+i, Name = "n", Side = "t",
            Slots = Enumerable.Range(1,5).Select(s => new CustomTacticSlot { Slot = s }).ToList() }).ToList();
        Reject(JsonSerializer.Serialize(many), "library count bound");
        var steps = TacticalPlaybook.Parse(json);
        steps.Tactics[0].Slots[1].Steps = Enumerable.Range(1,13).Select(_ => new CustomTacticStep { Position = [0,0] }).ToList();
        Reject(JsonSerializer.Serialize(steps), "per-slot step count bound");
        var tactic = playbook.Tactics[0];
        var roster = new[] { "human", "b1", "b2", "b3", "b4" };
        TacticalBotCandidate[] candidates = [new("b4","t",true,true,true),new("b2","t",true,true,true),
            new("human","t",true,true,true),new("b1","t",true,true,true),new("b3","t",true,true,true),
            new("enemy","ct",true,true,true)];
        var bindings = TacticalRosterSlots.Bind(tactic, roster, "human", candidates, "t");
        Check(bindings.Select(b => b.PlayerId).SequenceEqual(new[] { "b1", "b2", "b3", "b4" }), "request order ignores entity order");
        Check(bindings.Select(b => b.TacticSlot).SequenceEqual(new[] {2,3,4,5}), "human is unowned slot one");
        var death = candidates.Select(c => c.Id == "b2" ? c with { Alive = false } : c);
        Check(TacticalRosterSlots.Bind(tactic, roster, "human", death, "t").Select(b => b.TacticSlot)
            .SequenceEqual(new[] {2,4,5}), "dead slot never compresses later assignments");
        var takeover = candidates.Select(c => c.Id == "b1" ? c with { HumanControlled = true } : c);
        Check(TacticalRosterSlots.Bind(tactic, roster, "human", takeover, "t").All(b => b.PlayerId != "b1"), "takeover excluded");
        tactic.Slots[3].Steps.Clear();
        Check(TacticalRosterSlots.Bind(tactic, roster, "human", candidates, "t").All(b => b.TacticSlot != 4), "empty slot native");
        var ctTactic = TacticalPlaybook.Parse(json).Tactics[0]; ctTactic.Side = "ct";
        Check(TacticalRosterSlots.Bind(ctTactic, roster, "human", candidates.Select(c => c with { Side = "ct" }), "ct")
            .Select(b => b.PlayerId).SequenceEqual(new[] {"b1","b2","b3","b4"}), "halftime retains original team slot IDs");
        var invalidRoster = false;
        try { TacticalRosterSlots.Bind(tactic, ["b1","b2","b3","b4"], "human", candidates, "t"); }
        catch (InvalidDataException) { invalidRoster = true; }
        Check(invalidRoster, "missing human fails closed");
        var context = new TacticalCommandContext { MatchNonce = "n", Round = 1, SpeakerId = "human", Side = "t",
            AuthorizedMatch = true, AuthorizedHuman = true, SpeakerValid = true, Preparation = true };
        foreach (var text in new[] { "tactic short_split", "战术 short_split", "\"tactic short_split\"", "/tactic short_split" })
            Check(TacticalCommands.Parse("say_team", text) is { Order: TacticalOrder.Playbook, TacticId: "short_split" }, "custom whole message "+text);
        foreach (var text in new[] { "tactic", "tactic x y", "tactic x;quit", "tactic 中文", "战术 x!" })
            Check(TacticalCommands.Parse("say", text) is null, "custom malformed message "+text);
        var queue = new TacticalCommandQueue();
        Check(queue.Submit("say", "tactic short_split", context).Accepted && queue.Pending?.TacticId == "short_split", "custom queues with same auth");
        Check(!queue.Submit("say", "tactic short_split", context with { Preparation = false }).Accepted, "custom freeze gate");
        queue.Submit("say", "default", context); Check(queue.Pending is null, "default cancels custom pending");

        TacticNavPoint[] nav = [new(1,0,0,-80), new(2,0,0,120),new(3,500,500,800)];
        Check(TacticalNavProjection.Select(0,0,"upper",-80,nav).Area == 2, "upper floor at clicked XY");
        Check(TacticalNavProjection.Select(0,0,"lower",120,nav).Area == 1, "lower floor at clicked XY");
        Check(TacticalNavProjection.Select(0,0,"upper",0, [new(1,0,0,0),new(2,0,0,30)]).Area == 2,
            "upper selects explicit overlapping layer even at 30 units separation");
        Check(TacticalNavProjection.Select(0,0,"lower",30, [new(1,0,0,0),new(2,0,0,30)]).Area == 1,
            "lower selects explicit overlapping layer even at 30 units separation");
        Check(TacticalNavProjection.Select(0,0,"auto",-75,nav).Area == 1, "auto nearest prior navigation height");
        Check(TacticalNavProjection.Select(0,0,"upper",0, [new(1,0,0,10),new(2,40,0,120)]).Area == 1,
            "floor selector cannot snap through nearby wall away from containing NAV");
        var tooFar = false;
        try { TacticalNavProjection.Select(1000,1000,"auto",0,nav); } catch (InvalidDataException) { tooFar = true; }
        Check(tooFar, "far from NAV rejected");
        var clock = new TacticalStepClock([2,1]);
        Check(clock.Tick(0,false,false) == TacticStepAction.Move && clock.Remaining == 2, "travel starts no wait");
        Check(clock.Tick(50,false,false) == TacticStepAction.Move && clock.Remaining == 2, "travel time never spends wait");
        Check(clock.Tick(55,true,false) == TacticStepAction.Wait && clock.Remaining == 2, "arrival starts full wait");
        for (var i=1;i<=4;i++) clock.Tick(55+i*.25f,true,false);
        Check(clock.Remaining == 1, "wait elapsed only after reaching");
        Check(clock.Tick(56.1f,true,true) == TacticStepAction.Paused && clock.Remaining == 1, "explicit interruption preserves remaining wait");
        Check(clock.Tick(100,false,false) == TacticStepAction.Move && clock.Remaining == 1, "interrupted displacement navigates back");
        clock.Tick(110,true,false);
        Check(clock.Remaining == 1, "return arrival resumes remaining duration");
        for (var i=1;i<=4;i++) clock.Tick(110+i*.25f,true,false);
        Check(clock.Stage == 1 && clock.Remaining == 1, "remaining wait completes into next full step");
        clock.Tick(150,true,false);
        for (var i=1;i<=4;i++) clock.Tick(150+i*.25f,true,false);
        Check(clock.Stage == 2 && clock.Tick(152,true,false) == TacticStepAction.Completed, "last step completes once");
        var zero = new TacticalStepClock([0]);
        Check(zero.Tick(20,true,false) == TacticStepAction.Completed, "zero wait arrival completes immediately");
        int moveStarts = 0, moveRenews = 0;
        bool startAllowed = true, renewAllowed = true;
        string startResult = "move_started", renewResult = "rush_intent_renewed";
        bool StartMove(out string reason)
        { moveStarts++; reason = startResult; return startAllowed; }
        bool RenewMove(out string reason)
        { moveRenews++; reason = renewResult; return renewAllowed; }
        Check(TacticalMoveMaintenance.Tick(false, StartMove, RenewMove, out var moveReason)
            && moveReason == startResult && moveStarts == 1 && moveRenews == 0,
            "first unowned goal starts native movement once");
        for (var i = 0; i < 3; i++)
            Check(TacticalMoveMaintenance.Tick(true, StartMove, RenewMove, out moveReason)
                && moveReason == renewResult && moveStarts == 1 && moveRenews == i + 1,
                "same owned goal renews intent without restarting native movement");
        Check(TacticalMoveMaintenance.Tick(false, StartMove, RenewMove, out moveReason)
            && moveReason == startResult && moveStarts == 2 && moveRenews == 3,
            "lost native goal resumes through a fresh start");
        renewAllowed = false;
        foreach (var refusal in new[] { "native_combat_or_objective_retained", "loaded_navigation_code_changed" })
        {
            var beforeRenew = moveRenews; renewResult = refusal;
            Check(!TacticalMoveMaintenance.Tick(true, StartMove, RenewMove, out moveReason)
                && moveReason == refusal && moveStarts == 2 && moveRenews == beforeRenew + 1,
                "renew refusal passes through without forcing a new native start: " + refusal);
        }
        startAllowed = false; startResult = "native_combat_or_objective_retained";
        Check(!TacticalMoveMaintenance.Tick(false, StartMove, RenewMove, out moveReason)
            && moveReason == startResult && moveStarts == 3 && moveRenews == 5,
            "start combat refusal passes through without invoking renewal");
        const string currentDll = "8645168D4BB6A55CE8A8AC4246BCE394496E4EECF4F56C2F2A7932A98EB75D61";
        const string legacyDll = "E3D0424CE253B11CFFA714B03D53580EA2F176C0A53D4FA06FF1B9DE4C46DCE8";
        Check(TacticalHoldControls.AuditedAbiForHash(currentDll) == 22, "installed v0.7.0 pinned to ABI22, not ABI20");
        Check(TacticalHoldControls.ValidateAbi(currentDll, 22) == 22, "audited current ABI22 hold exports accepted");
        Check(TacticalHoldControls.ValidateAbi(legacyDll, 20) == 20, "audited legacy ABI20 remains supported");
        foreach (var pair in new[] { (Hash:currentDll, Abi:20), (Hash:legacyDll, Abi:22),
                                    (Hash:currentDll, Abi:23), (Hash:new string('0',64), Abi:22) })
        {
            var rejected = false;
            try { TacticalHoldControls.ValidateAbi(pair.Hash,pair.Abi); } catch (InvalidDataException) { rejected = true; }
            Check(rejected, "unknown hash or mismatched ABI fails closed: "+pair.Abi);
        }
        var holdApi = new HoldApi(); var lease = new TacticalHoldControls.Lease(holdApi, 4);
        lease.Keep(); lease.Keep();
        Check(lease.Active && holdApi.Starts == 1 && holdApi.Updates == 2, "hold renews own token without repeatedly acquiring");
        Check((holdApi.Mask & ((1UL<<0)|(1UL<<5)|(1UL<<11))) == 0, "hold never suppresses attack/use/secondary action");
        lease.Release(); lease.Release();
        Check(!lease.Active && holdApi.Cancelled.SequenceEqual(new long[] {11,22}), "hold cancellation is owned and idempotent");
        CheckTimedHolds(Check);
        CheckTravelProgress(Check);
        CheckDirectPaths(Check);
        CheckTransitWaypoints(Check);
        var blockedApi = new HoldApi { Locked = true }; var blockedLease = new TacticalHoldControls.Lease(blockedApi, 5);
        var blocked = false;
        try { blockedLease.Keep(); } catch (InvalidOperationException) { blocked = true; }
        Check(blocked && blockedApi.Starts == 0 && blockedApi.Cancelled.Count == 0, "another owner leaves its lease untouched");
        var failedApi = new HoldApi { SuppressionRejected = true }; var failedLease = new TacticalHoldControls.Lease(failedApi, 6);
        var failed = false;
        try { failedLease.Keep(); } catch (InvalidOperationException) { failed = true; }
        Check(failed && !failedLease.Active && failedApi.Cancelled.SequenceEqual(new long[] {11}), "partial hold acquisition cleans movement token");
        var cancelApi = new HoldApi { CancelRejected = true }; var cancelLease = new TacticalHoldControls.Lease(cancelApi, 7);
        cancelLease.Keep(); var cancelFailed = false;
        try { cancelLease.Release(); } catch (InvalidOperationException) { cancelFailed = true; }
        Check(cancelFailed && cancelApi.Cancelled.SequenceEqual(new long[] {11,22}), "movement cancellation error still releases button suppression");
        Console.WriteLine($"{count} tactical-playbook checks passed (strict data, stable five slots, NAV floors, custom chat, 64-tick positional waits, direct path commits, zero-wait transit, native travel yield, detour progress).");
    }

    private static void CheckMapBoundariesAndLevels(string valid, Action<bool,string> check)
    {
        using var stream = typeof(TacticalPlaybook).Assembly.GetManifestResourceStream("CareerMatch.TacticalMaps")
            ?? throw new Exception("shared map registry is missing");
        using var registry = JsonDocument.Parse(stream);
        foreach (var property in registry.RootElement.GetProperty("maps").EnumerateObject())
        {
            var map = property.Name; var meta = property.Value;
            var x = meta.GetProperty("pos_x").GetDouble(); var y = meta.GetProperty("pos_y").GetDouble();
            var scale = meta.GetProperty("scale").GetDouble();
            var maxX = x+meta.GetProperty("width").GetInt32()*scale;
            var minY = y-meta.GetProperty("height").GetInt32()*scale;
            float middleX = (float)((x+maxX)/2), middleY = (float)((y+minY)/2);
            float[][] edges = [[(float)x,middleY], [(float)maxX,middleY],
                [middleX,(float)minY], [middleX,(float)y]];
            for (var index = 0; index < edges.Length; index++)
            {
                var point = edges[index];
                check(TacticalMapCatalog.ContainsPoint(map, point), $"editor's finished boundary accepted {map}:{index}");
                var library = TacticalPlaybook.Parse(valid); library.Map = map;
                var step = library.Tactics[0].Slots[1].Steps[0];
                step.Position = point; step.LookAt = point;
                check(TacticalPlaybook.Parse(JsonSerializer.Serialize(library)).Map == map,
                    $"boundary position and look_at survive full JSON playbook {map}:{index}");
            }
            float[][] outside = [[(float)x-1,middleY], [(float)maxX+1,middleY],
                [middleX,(float)minY-1], [middleX,(float)y+1]];
            foreach (var point in outside)
                check(!TacticalMapCatalog.ContainsPoint(map, point), "one unit outside map stays rejected " + map);

            var layers = meta.GetProperty("layers").EnumerateArray().ToArray();
            var lower = layers.FirstOrDefault(layer => layer.GetProperty("id").GetString() == "lower");
            if (lower.ValueKind == JsonValueKind.Undefined)
            {
                check(TacticalMapCatalog.IsLevelAllowed(map, "upper", -1000)
                    && TacticalMapCatalog.IsLevelAllowed(map, "lower", 1000),
                    "single-layer map preserves relative NAV floors " + map);
                continue;
            }
            var upper = layers.Single(layer => layer.GetProperty("id").GetString() == "upper");
            var upperMin = upper.GetProperty("altitude_min").GetSingle();
            var lowerMax = lower.GetProperty("altitude_max").GetSingle();
            check(TacticalMapCatalog.IsLevelAllowed(map, "upper", upperMin)
                && !TacticalMapCatalog.IsLevelAllowed(map, "upper", upperMin-1), "upper radar section cutoff " + map);
            check(TacticalMapCatalog.IsLevelAllowed(map, "lower", lowerMax)
                && !TacticalMapCatalog.IsLevelAllowed(map, "lower", lowerMax+1), "lower radar section cutoff " + map);
            check(TacticalMapCatalog.IsLevelAllowed(map, "auto", upperMin+100)
                && TacticalMapCatalog.IsLevelAllowed(map, "auto", lowerMax-100), "auto keeps both radar floors " + map);
            TacticNavPoint[] nav = [new(1,0,0,lowerMax-100), new(2,0,0,upperMin+100)];
            foreach (var level in new[] { "upper", "lower" })
            {
                var allowed = nav.Where(point => TacticalMapCatalog.IsLevelAllowed(map, level, point.Z));
                check(TacticalNavProjection.Select(0,0,level,upperMin,allowed).Area == (level == "upper" ? 2u : 1u),
                    "explicit level only projects its official section " + map + ":" + level);
                var otherFloorOnly = nav.Where(point => point.Area == (level == "upper" ? 1u : 2u))
                    .Where(point => TacticalMapCatalog.IsLevelAllowed(map, level, point.Z));
                var refused = false;
                try { TacticalNavProjection.Select(0,0,level,upperMin,otherFloorOnly); }
                catch (InvalidDataException) { refused = true; }
                check(refused, "missing selected radar floor never falls back to other floor " + map + ":" + level);
            }
        }
        check(!TacticalMapCatalog.IsLevelAllowed("de_unknown", "auto", 0), "unknown map cannot allow a NAV level");
        check(!TacticalMapCatalog.IsLevelAllowed("de_nuke", "roof", 0), "unknown NAV level is refused");
        check(!TacticalMapCatalog.IsLevelAllowed("de_nuke", "auto", float.NaN), "nonfinite NAV altitude is refused");
    }

    private static void CheckTimedHolds(Action<bool,string> check)
    {
        check(TacticalWaitPolicy.ShouldHold(15, true, false), "positive wait acquires hold only after arrival");
        check(!TacticalWaitPolicy.ShouldHold(15, false, false), "travel before arrival does not acquire wait movement");
        check(TacticalWaitPolicy.ShouldHold(15, false, true), "existing hold survives arrival-radius jitter");
        check(TacticalWaitPolicy.InHoldBounds(72*72, 0, 40), "40-unit arrival radius retains hold exactly at its 72-unit XY bound");
        check(!TacticalWaitPolicy.InHoldBounds(72*72+1, 0, 40), "hold releases beyond the expanded XY boundary");
        check(!TacticalWaitPolicy.InHoldBounds(7200, 0, 40), "physical push to distance squared 7200 is outside the hold area");
        check(TacticalWaitPolicy.InHoldBounds(0, 48-1f/64, 40)
            && TacticalWaitPolicy.InHoldBounds(0, -48+1f/64, 40), "hold retains either height immediately inside 48 units");
        check(!TacticalWaitPolicy.InHoldBounds(0, 48, 40)
            && !TacticalWaitPolicy.InHoldBounds(0, -48, 40), "hold releases at either 48-unit height boundary");
        check(!TacticalWaitPolicy.ShouldHold(20, false, TacticalWaitPolicy.InHoldBounds(7200, 0, 40)),
            "active lease outside hold bounds cannot retain zero movement indefinitely");
        foreach (var wait in new[] {0f, -1f})
            check(!TacticalWaitPolicy.ShouldHold(wait, true, true), "nonpositive wait never retains hold: " + wait);
        check(TacticalWaitPolicy.YieldToNative(false, true), "travel yields to native combat and objective actions");
        check(!TacticalWaitPolicy.YieldToNative(false, false), "travel with no native action remains owned");
        check(!TacticalWaitPolicy.YieldToNative(true, true), "positional wait retains movement during native action");
        check(!TacticalWaitPolicy.YieldToNative(true, false), "quiet positional wait also retains movement");

        foreach (var seconds in new[] {15, 20})
        {
            const int ticksPerSecond = 64;
            const float arrivedAt = 512;
            var deadline = seconds*ticksPerSecond;
            var clock = new TacticalStepClock([seconds]);
            var api = new HoldApi();
            var lease = new TacticalHoldControls.Lease(api, 8);
            check(clock.Tick(arrivedAt-30, false, false) == TacticStepAction.Move
                && clock.Remaining == seconds, seconds + "s hold excludes travel time");

            // Native perception/firing/utility stays active throughout the wait.
            // Repeated jump intent and radius jitter at tick 21 must not release
            // the positional lease or turn elapsed wait time into a combat pause.
            for (var tick = 0; tick <= deadline; tick++)
            {
                var reached = tick == 0 || tick%ticksPerSecond != 21;
                var holdingInBounds = lease.Active && TacticalWaitPolicy.InHoldBounds(reached ? 100 : 2500, reached ? 0 : 24, 40);
                var hold = TacticalWaitPolicy.ShouldHold(seconds, reached, holdingInBounds);
                var yield = TacticalWaitPolicy.YieldToNative(hold, nativeAction: true);
                check(hold && !yield, $"{seconds}s wait retains native combat/jump intent at tick {tick}");
                lease.Keep();
                var action = clock.Tick(arrivedAt+tick/(float)ticksPerSecond, reached || holdingInBounds, yield);
                if (tick < deadline)
                {
                    check(action == TacticStepAction.Wait && clock.Stage == 0
                        && clock.Remaining == seconds-tick/(float)ticksPerSecond,
                        $"{seconds}s wait spends actual 64-tick elapsed time at tick {tick}");
                    check(lease.Active && api.Starts == 1 && api.Suppressions == 1
                        && api.Updates == tick+1 && api.Cancelled.Count == 0,
                        $"{seconds}s wait keeps the same lease beyond tick 21: {tick}");
                }
                else
                {
                    check(action == TacticStepAction.Completed && clock.Stage == 1 && clock.Remaining == 0,
                        seconds + "s wait completes exactly at the requested deadline");
                    lease.Release();
                }
            }
            check(!lease.Active && api.Starts == 1 && api.Suppressions == 1 && api.Updates == deadline+1
                && api.Cancelled.SequenceEqual(new long[] {11,22}),
                seconds + "s completed hold releases each owned token once");
            check((api.Mask & (1UL<<1)) != 0 && (api.Mask & (1UL<<2)) != 0,
                seconds + "s hold suppresses native jump/duck intent");
            check((api.Mask & ((1UL<<0)|(1UL<<5)|(1UL<<11)|(1UL<<13))) == 0,
                seconds + "s held combat retains attack/use/secondary/reload controls");
            for (var tick = 1; tick <= ticksPerSecond; tick++)
            {
                check(clock.Tick(arrivedAt+seconds+tick/(float)ticksPerSecond, true, false)
                    == TacticStepAction.Completed, seconds + "s completed step never restarts");
                lease.Release();
            }
            check(api.Cancelled.SequenceEqual(new long[] {11,22}) && api.Starts == 1,
                seconds + "s later ticks cannot release or reacquire completed hold");
        }

        var displacedClock = new TacticalStepClock([20]);
        var displacedApi = new HoldApi();
        var displacedLease = new TacticalHoldControls.Lease(displacedApi, 9);
        displacedLease.Keep();
        displacedClock.Tick(0, true, false);
        for (var tick = 1; tick <= 64; tick++)
            check(displacedClock.Tick(tick/64f, true, false) == TacticStepAction.Wait,
                "pre-displacement hold counts actual 64-tick time: " + tick);
        var displacedInBounds = displacedLease.Active && TacticalWaitPolicy.InHoldBounds(7200, 0, 40);
        var displacedHold = TacticalWaitPolicy.ShouldHold(20, false, displacedInBounds);
        check(!displacedHold && displacedLease.Active, "physical displacement requests release even with an active lease");
        if (!displacedHold) displacedLease.Release();
        check(displacedClock.Tick(2, false, TacticalWaitPolicy.YieldToNative(displacedHold, false))
            == TacticStepAction.Move && displacedClock.Remaining == 19,
            "displacement resumes navigation without spending the remaining wait");
        check(!displacedLease.Active && displacedApi.Cancelled.SequenceEqual(new long[] {11,22}),
            "displacement releases both owned tokens once for return movement");
        for (var tick = 3; tick < 12; tick++)
            check(displacedClock.Tick(tick, false, false) == TacticStepAction.Move && displacedClock.Remaining == 19,
                "return travel does not spend displaced hold duration: " + tick);
        check(TacticalWaitPolicy.ShouldHold(20, true, false), "return arrival can reacquire hold after physical displacement");
        displacedLease.Keep();
        check(displacedClock.Tick(12, true, false) == TacticStepAction.Wait && displacedClock.Remaining == 19
            && displacedApi.Starts == 2 && displacedApi.Suppressions == 2,
            "return arrival resumes the saved wait using a fresh owned lease");
        check(displacedClock.Tick(12.25f, true, false) == TacticStepAction.Wait && displacedClock.Remaining == 18.75f,
            "only time actually held after return resumes the countdown");
        displacedLease.Release();
    }

    private static void CheckTravelProgress(Action<bool,string> check)
    {
        var detour = new TacticalTravelProgress();
        detour.Reset(0);
        check(!detour.IsStalled(0, 100, 100, MathF.Sqrt(20000)), "detour records its initial world checkpoint");
        // A native NAV route can run away from the destination to go around a
        // wall. Sample at the same four checks/second as the live travel loop.
        for (var sample = 1; sample <= 120; sample++)
        {
            var x = 100+sample*8;
            var y = 100+MathF.Sin(sample*.08f)*120;
            var distance = MathF.Sqrt(x*x+y*y);
            check(!detour.IsStalled(sample*.25f, x, y, distance),
                "world travel along a wide detour cannot stall despite increasing goal distance: " + sample);
        }

        var motionBoundary = new TacticalTravelProgress();
        motionBoundary.Reset(0);
        motionBoundary.IsStalled(0, 0, 0, 500);
        check(!motionBoundary.IsStalled(9, 24, 0, 524), "exactly 24 world units renews travel progress");
        check(!motionBoundary.IsStalled(19, 24, 0, 524), "stationary bot has its full ten-second grace after world progress");
        check(motionBoundary.IsStalled(19+1f/64, 24, 0, 524), "stationary bot stalls only after the progress grace expires");

        var approach = new TacticalTravelProgress();
        approach.Reset(0);
        approach.IsStalled(0, 0, 0, 200);
        check(!approach.IsStalled(9, 21, 0, 179), "goal improvement can renew progress before 24 world units");
        check(!approach.IsStalled(19, 21, 0, 179), "goal-distance progress renews the full stationary grace");
        check(approach.IsStalled(19+1f/64, 21, 0, 179), "goal improvement does not disable later stationary fallback");

        var noise = new TacticalTravelProgress();
        noise.Reset(0);
        noise.IsStalled(0, 1000, 500, 300);
        for (var sample = 1; sample <= 48; sample++)
        {
            var now = sample*.25f;
            var x = 1000+MathF.Sin(sample)*2;
            var y = 500+MathF.Cos(sample)*2;
            var distance = 300-sample%4;
            check(noise.IsStalled(now, x, y, distance) == (now > 10),
                "stationary position/distance noise cannot hide the ten-second stall: " + sample);
        }

        var reset = new TacticalTravelProgress();
        reset.Reset(0);
        reset.IsStalled(0, 0, 0, 0);
        check(reset.IsStalled(11, 0, 0, 0), "first travel can reach a stalled near-goal state");
        reset.Reset(100);
        check(!reset.IsStalled(100, 0, 0, 200), "reset begins a fresh travel attempt without inheriting the expired timer");
        check(!reset.IsStalled(109, 21, 0, 179), "reset forgets the previous step's near-zero best goal distance");
        check(!reset.IsStalled(110.25f, 21, 0, 179), "new goal improvement after reset actually renews the timer");
        check(!reset.IsStalled(119, 21, 0, 179), "reset travel retains the new progress grace");
        check(reset.IsStalled(119+1f/64, 21, 0, 179), "reset travel still detects a genuine later stall");
    }

    private static void CheckDirectPaths(Action<bool,string> check)
    {
        var path = new TacticalDirectMove();
        var owns = false; var starts = 0; var commits = 0; var renews = 0;
        var startReason = "move_to_issued_arrival_unverified";
        var commitReason = "navigation_path_rate_limited";
        var renewReason = "short_native_rush_intent_renewed";
        bool Start(out string reason)
        {
            starts++; reason = startReason;
            if (reason != "move_to_issued_arrival_unverified") return false;
            owns = true; return true;
        }
        bool Commit(out string reason)
        { commits++; reason = commitReason; return reason == "shortest_native_path_accepted_arrival_unverified"; }
        bool Renew(out string reason)
        { renews++; reason = renewReason; return reason == "short_native_rush_intent_renewed"; }
        TacticalPathAction Tick(float now, out string reason) => path.Tick(now, owns, Start, Commit, Renew, out reason);

        check(Tick(0, out var why) == TacticalPathAction.Pending && why == commitReason
            && starts == 1 && commits == 1 && renews == 0 && owns,
            "accepted MoveTo with rate-limited ComputePath is NOT movement-ready");
        for (var sample = 1; sample <= 3; sample++)
            check(Tick(sample*.25f, out why) == TacticalPathAction.Pending && why == commitReason
                && starts == 1 && commits == sample+1 && renews == 0,
                "pending owned goal retries only native path, not MoveTo/OnEnter: " + sample);
        commitReason = "shortest_native_path_accepted_arrival_unverified";
        check(Tick(1, out why) == TacticalPathAction.Moving && why == commitReason
            && starts == 1 && commits == 5 && renews == 0,
            "native accepted fresh shortest path releases preparation exactly once");
        check(!path.NeedsPreparation(true) && path.NeedsPreparation(false),
            "only an uncommitted or displaced goal needs the preparation movement lease");
        for (var sample = 1; sample <= 4; sample++)
            check(Tick(1+sample, out why) == TacticalPathAction.Moving && why == renewReason
                && starts == 1 && commits == 5 && renews == sample,
                "committed path only renews hurry, no repeated full NAV search: " + sample);

        owns = false;
        check(Tick(6, out why) == TacticalPathAction.Moving && starts == 2 && commits == 6 && renews == 4,
            "native task replacing a goal requires a fresh MoveTo plus path commit");
        path.Reset();
        check(path.NeedsPreparation(true), "reset needs preparation even if the old MoveTo goal still matches");
        check(Tick(7, out why) == TacticalPathAction.Moving && starts == 2 && commits == 7,
            "stage/combat reset cannot treat an old matching goal as a fresh accepted path");
        renewReason = "native_combat_or_objective_retained";
        check(Tick(8, out why) == TacticalPathAction.Yielded && why == renewReason,
            "combat refusal after commitment yields and resets route preparation");
        renewReason = "short_native_rush_intent_renewed";
        check(Tick(12, out why) == TacticalPathAction.Moving && commits == 8,
            "combat time does not exhaust later route preparation; resumption recommits");

        path.Reset(); owns = false; startReason = "native_combat_or_objective_retained";
        var beforeCommit = commits;
        check(Tick(13, out why) == TacticalPathAction.Yielded && commits == beforeCommit,
            "combat refusing MoveTo never calls ComputePath in a different native state");
        startReason = "loaded_navigation_code_changed";
        check(Tick(14, out why) == TacticalPathAction.Failed && why == startReason && commits == beforeCommit,
            "native code guard refusal cannot be bypassed through the path call");
        startReason = "move_to_issued_arrival_unverified";
        path.Reset(); commitReason = "navigation_goal_changed";
        check(Tick(20, out why) == TacticalPathAction.Pending && why == commitReason,
            "goal lost between enter and ComputePath does not claim movement success");
        owns = false; commitReason = "shortest_native_path_accepted_arrival_unverified";
        check(Tick(20.25f, out why) == TacticalPathAction.Moving,
            "lost goal can re-enter the intended target and establish its actual path");
        foreach (var refusal in new[] { "navigation_path_unavailable", "navigation_path_result_invalid", "loaded_navigation_code_changed" })
        {
            path.Reset(); commitReason = refusal;
            check(Tick(30, out why) == TacticalPathAction.Failed && why == refusal,
                "native path rejection is visible, not reported as issued success: " + refusal);
        }
        path.Reset(); commitReason = "navigation_path_rate_limited";
        check(Tick(40, out why) == TacticalPathAction.Pending, "bounded preparation starts anew");
        check(Tick(40+TacticalDirectMove.MaximumPreparation, out why) == TacticalPathAction.Pending,
            "preparation tolerates its exact three-second limit");
        var beforeTimeout = commits;
        check(Tick(40+TacticalDirectMove.MaximumPreparation+1f/64, out why) == TacticalPathAction.Failed
            && why == "custom_path_preparation_timeout" && commits == beforeTimeout,
            "expired preparation stops without repeated path calls or unbounded standing");
        path.Reset();
        check(Tick(50, out why) == TacticalPathAction.Pending,
            "reset removes the previous preparation timeout");

        // Couple preparation with the very same zero-movement lease and wait
        // clock used live. No arrival token is inferred from a path-hold token.
        path.Reset(); owns = false;
        var api = new HoldApi(); var lease = new TacticalHoldControls.Lease(api, 9);
        var clock = new TacticalStepClock([15]);
        for (var tick = 0; tick <= 64; tick++)
        {
            var now = 100+tick/64f;
            if (path.NeedsPreparation(owns)) lease.Keep(); // BEFORE native state/path calls.
            var action = tick%16 == 0 ? Tick(now, out why) : TacticalPathAction.Pending;
            if (action == TacticalPathAction.Pending) lease.Keep();
            check(lease.Active && api.Starts == 1 && api.Cancelled.Count == 0,
                "pending path holds old movement at 64 ticks, without reacquiring: " + tick);
            check(clock.Tick(now, reached: false, interrupted: false) == TacticStepAction.Move
                && clock.Remaining == 15 && !TacticalWaitPolicy.ShouldHold(15, false, false),
                "preparation token never spends the destination's wait: " + tick);
        }
        commitReason = "shortest_native_path_accepted_arrival_unverified";
        check(Tick(101.25f, out why) == TacticalPathAction.Moving, "coupled preparation commits its actual route");
        lease.Release();
        check(!lease.Active && api.Cancelled.SequenceEqual(new long[] {11,22})
            && clock.Remaining == 15, "movement opens only after route acceptance, not by spending positional wait");
        check(clock.Tick(110, true, false) == TacticStepAction.Wait && clock.Remaining == 15,
            "actual arrival after path preparation starts the full destination wait");

        path.Reset(); owns = false;
        var blockedApi = new HoldApi { Locked = true };
        var blockedLease = new TacticalHoldControls.Lease(blockedApi, 10);
        var previousStarts = starts; var previousCommits = commits;
        var refusedOwner = false;
        try
        {
            if (path.NeedsPreparation(owns)) blockedLease.Keep();
            Tick(120, out why);
        }
        catch (InvalidOperationException ex) when (ex.Message == "hold_other_owner") { refusedOwner = true; }
        check(refusedOwner && starts == previousStarts && commits == previousCommits && blockedApi.Starts == 0,
            "another owner refuses BEFORE native goal/path changes, even with an immediately successful path");
    }

    private static void CheckTransitWaypoints(Action<bool,string> check)
    {
        check(TacticalWaypointPolicy.IsTransit(TacticStepAction.Advanced, 0),
            "intermediate zero-wait waypoint continues its route without native release");
        check(!TacticalWaypointPolicy.IsTransit(TacticStepAction.Completed, 0),
            "final zero-wait waypoint retains normal native release");
        check(!TacticalWaypointPolicy.IsTransit(TacticStepAction.Advanced, 2),
            "completed positive wait retains normal settled-step release");
        foreach (var action in new[] { TacticStepAction.Move, TacticStepAction.Wait, TacticStepAction.Paused })
            check(!TacticalWaypointPolicy.IsTransit(action, 0),
                "only an actually advanced waypoint is transit: " + action);
        for (var tick = 1; tick <= 16; tick++)
        {
            check(TacticalWaypointPolicy.ShouldCheckMovement(tick, true),
                "transit prepares the next single goal in every tick phase: " + tick);
            check(TacticalWaypointPolicy.ShouldCheckMovement(tick, false) == (tick == 16),
                "ordinary movement preserves its existing tick schedule: " + tick);
            check(!TacticalWaypointPolicy.ShouldCheckMovement(tick, true, nextGoalReached: true),
                "overlapping transit point is evaluated next tick without forcing an empty native path: " + tick);
        }

        var overlapping = new TacticalStepClock([0,0,0]);
        var releases = 0;
        for (var tick = 65; tick <= 67; tick++)
        {
            var completed = overlapping.Tick(tick/64f, true, false);
            var transit = TacticalWaypointPolicy.IsTransit(completed, 0);
            if (!transit) releases++;
            check(overlapping.Stage == tick-64,
                "overlapping route remains bounded to exactly one waypoint per tick: " + tick);
            check(!transit || !TacticalWaypointPolicy.ShouldCheckMovement(tick, transit, true),
                "overlapping intermediate arrival never requests an unnecessary new path: " + tick);
        }
        check(releases == 1 && overlapping.Stage == 3,
            "overlapping zero-wait route releases only once at its final point");

        // Couple the production transit decision with the real clock, fresh
        // path gate and zero-input lease. An old accepted goal cannot make the
        // next unarrived goal movement-ready.
        var clock = new TacticalStepClock([0,0,2]);
        var path = new TacticalDirectMove();
        var api = new HoldApi();
        var lease = new TacticalHoldControls.Lease(api, 12);
        var owns = true;
        var commits = 0;
        var commitAllowed = true;
        bool Start(out string reason) { owns = true; reason = "move_to_issued_arrival_unverified"; return true; }
        bool Commit(out string reason)
        {
            commits++;
            reason = commitAllowed ? "shortest_native_path_accepted_arrival_unverified" : "navigation_path_rate_limited";
            return commitAllowed;
        }
        bool Renew(out string reason) { reason = "short_native_rush_intent_renewed"; return true; }
        check(path.Tick(0, owns, Start, Commit, Renew, out _) == TacticalPathAction.Moving,
            "old transit goal starts with an accepted native path");
        var advance = clock.Tick(1, true, false);
        check(TacticalWaypointPolicy.IsTransit(advance, 0) && clock.Stage == 1,
            "one clock tick advances exactly one zero-wait waypoint");
        path.Reset(); owns = false; commitAllowed = false;
        check(path.NeedsPreparation(owns), "transit invalidates the old path commitment before the next goal");
        lease.Keep();
        check(TacticalWaypointPolicy.ShouldCheckMovement(65, true)
            && path.Tick(1, owns, Start, Commit, Renew, out var reason) == TacticalPathAction.Pending
            && reason == "navigation_path_rate_limited" && lease.Active && api.Cancelled.Count == 0,
            "same off-phase tick prepares transit with movement held, never blindly opens the old path");
        check(path.Tick(1.25f, owns, Start, Commit, Renew, out _) == TacticalPathAction.Pending && lease.Active,
            "transit preparation preserves the quarter-second path retry and hold");
        commitAllowed = true;
        check(path.Tick(1.5f, owns, Start, Commit, Renew, out _) == TacticalPathAction.Moving && commits == 4,
            "only the fresh accepted transit path allows movement");
        lease.Release();
        check(!lease.Active && api.Cancelled.SequenceEqual(new long[] {11,22}),
            "transit path releases only its own input tokens after acceptance");
        advance = clock.Tick(2, true, false);
        check(TacticalWaypointPolicy.IsTransit(advance, 0) && clock.Stage == 2 && clock.Remaining == 2,
            "second transit reaches the positional wait without spending its duration");
        check(clock.Tick(100, false, false) == TacticStepAction.Move && clock.Remaining == 2,
            "travel from transit still does not spend the next wait");
        check(clock.Tick(101, true, false) == TacticStepAction.Wait && clock.Remaining == 2,
            "positive wait starts only at its own settled arrival");
        for (var sample = 1; sample <= 8; sample++) clock.Tick(101+sample*.25f, true, false);
        check(clock.Stage == 3 && !TacticalWaypointPolicy.IsTransit(TacticStepAction.Completed, 2),
            "final positive wait finishes once through normal release semantics");

        path.Reset(); owns = false; commitAllowed = false;
        check(path.Tick(200, owns, Start, Commit, Renew, out _) == TacticalPathAction.Pending,
            "transit path preparation begins its own bounded timeout");
        check(path.Tick(200+TacticalDirectMove.MaximumPreparation+1f/64, owns, Start, Commit, Renew, out reason)
            == TacticalPathAction.Failed && reason == "custom_path_preparation_timeout",
            "transit pending native path cannot hold indefinitely");
    }

    private sealed class HoldApi : ITacticalHoldApi
    {
        internal bool Locked, SuppressionRejected, CancelRejected;
        internal int Starts, Updates, Suppressions;
        internal ulong Mask;
        internal readonly List<long> Cancelled = [];
        public int IsLocked(int slot,int kind) => Locked ? 1 : 0;
        public long StartMove(int slot) { Starts++; return 11; }
        public int UpdateMove(int slot,long token) { Updates++; return token == 11 ? 0 : -1; }
        public int CancelMove(int slot,long token) { Cancelled.Add(token); return CancelRejected ? -1 : 0; }
        public long Suppress(int slot,ulong mask) { Suppressions++; Mask = mask; return SuppressionRejected ? -1 : 22; }
        public int CancelSuppression(int slot,long token) { Cancelled.Add(token); return 0; }
    }
}
