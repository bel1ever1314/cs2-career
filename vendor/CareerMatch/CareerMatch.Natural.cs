using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace CareerMatch;

// Dust2 professional node controller. Native AI keeps perception, shooting and
// long-range path choice. This layer coordinates evidence-backed local holds,
// peeks and unsupported CT deep-push protection.
public sealed partial class CareerMatchPlugin
{
    private sealed class NaturalPack
    {
        [JsonPropertyName("schema_version")] public int SchemaVersion { get; set; }
        [JsonPropertyName("map")] public string Map { get; set; } = "";
        [JsonPropertyName("policy")] public NaturalPolicy Policy { get; set; } = new();
        [JsonPropertyName("coverage_rules")] public NaturalCoverageRules Coverage { get; set; } = new();
        [JsonPropertyName("nodes")] public List<NaturalNode> Nodes { get; set; } = [];
        [JsonPropertyName("edges")] public List<NaturalEdge> Edges { get; set; } = [];
        [JsonPropertyName("formations")] public List<NaturalFormation> Formations { get; set; } = [];
    }

    private sealed class NaturalPolicy
    {
        [JsonPropertyName("ct_coordinated_push_chance")] public float CtPushChance { get; set; } = .08f;
        [JsonPropertyName("max_consecutive_push_rounds")] public int MaxConsecutive { get; set; } = 1;
        [JsonPropertyName("combat_handoff_ms")] public int CombatHandoffMs { get; set; } = 150;
        [JsonPropertyName("jump_escape")] public bool JumpEscape { get; set; }
        [JsonPropertyName("minimum_hold_ms")] public int MinimumHoldMs { get; set; } = 800;
        [JsonPropertyName("visual_memory_ms")] public int VisualMemoryMs { get; set; } = 4000;
        [JsonPropertyName("casualty_memory_ms")] public int CasualtyMemoryMs { get; set; } = 6000;
        [JsonPropertyName("sound_memory_ms")] public int SoundMemoryMs { get; set; } = 2000;
        [JsonPropertyName("safe_micro_adjust_units")] public float SafeMicroAdjust { get; set; } = 48;
        [JsonPropertyName("opening_max_ms")] public int OpeningMaxMs { get; set; } = 22000;
        [JsonPropertyName("late_after_ms")] public int LateAfterMs { get; set; } = 75000;
        [JsonPropertyName("strategic_alert_delay_ms")] public int StrategicAlertDelayMs { get; set; } = 750;
        [JsonPropertyName("strategic_memory_ms")] public int StrategicMemoryMs { get; set; } = 2500;
        [JsonPropertyName("task_stall_ms")] public int TaskStallMs { get; set; } = 3000;
        [JsonPropertyName("arrival_distance")] public float ArrivalDistance { get; set; } = 14;
        [JsonPropertyName("arrival_speed")] public float ArrivalSpeed { get; set; } = 28;
        [JsonPropertyName("arrival_stable_ms")] public int ArrivalStableMs { get; set; } = 94;
    }

    private sealed class NaturalCoverageRules
    {
        [JsonPropertyName("ct_critical_lanes")] public List<string> CtCriticalLanes { get; set; } = [];
        [JsonPropertyName("cross_zone_enemy_count")] public int CrossZoneEnemyCount { get; set; } = 2;
        [JsonPropertyName("cross_zone_window_ms")] public int CrossZoneWindowMs { get; set; } = 6000;
    }

    private sealed class NaturalNode
    {
        [JsonPropertyName("id")] public string Id { get; set; } = "";
        [JsonPropertyName("side")] public string Side { get; set; } = "";
        [JsonPropertyName("place")] public string Place { get; set; } = "";
        [JsonPropertyName("zone")] public string Zone { get; set; } = "unknown";
        [JsonPropertyName("position")] public float[] Position { get; set; } = [];
        [JsonPropertyName("radius")] public float Radius { get; set; }
        [JsonPropertyName("safe_radius")] public float SafeRadius { get; set; } = 48;
        [JsonPropertyName("cover_group")] public string CoverGroup { get; set; } = "";
        [JsonPropertyName("territory")] public string Territory { get; set; } = "contested";
        [JsonPropertyName("role_weights")] public Dictionary<string,int> RoleWeights { get; set; } = [];
        [JsonPropertyName("movement")] public string Movement { get; set; } = "stationary";
        [JsonPropertyName("speed")] public float Speed { get; set; }
        [JsonPropertyName("aim_lanes")] public List<NaturalAnchor> Anchors { get; set; } = [];
        [JsonPropertyName("exposure_lanes")] public List<NaturalExposure> Exposures { get; set; } = [];
        [JsonPropertyName("retreat_node_ids")] public List<string> RetreatNodeIds { get; set; } = [];
        [JsonPropertyName("peek_primitives")] public List<NaturalPeek> Peeks { get; set; } = [];
    }

    private sealed class NaturalAnchor
    {
        [JsonPropertyName("id")] public string Id { get; set; } = "";
        [JsonPropertyName("lane")] public string Lane { get; set; } = "";
        [JsonPropertyName("target")] public float[] Target { get; set; } = [];
        [JsonPropertyName("confidence")] public string Confidence { get; set; } = "medium";
    }

    private sealed class NaturalExposure
    {
        [JsonPropertyName("lane")] public string Lane { get; set; } = "";
        [JsonPropertyName("events")] public int Events { get; set; }
    }

    private sealed class NaturalPeek
    {
        [JsonPropertyName("id")] public string Id { get; set; } = "";
        [JsonPropertyName("kind")] public string Kind { get; set; } = "shoulder";
        [JsonPropertyName("lane")] public string Lane { get; set; } = "";
        [JsonPropertyName("offset")] public float[] Offset { get; set; } = [];
        [JsonPropertyName("out_ms")] public int OutMs { get; set; } = 220;
        [JsonPropertyName("hold_ms")] public int HoldMs { get; set; } = 80;
        [JsonPropertyName("back_ms")] public int BackMs { get; set; } = 250;
        [JsonPropertyName("max_checks")] public int MaxChecks { get; set; } = 2;
    }

    private sealed class NaturalEdge
    {
        [JsonPropertyName("from")] public string From { get; set; } = "";
        [JsonPropertyName("to")] public string To { get; set; } = "";
        [JsonPropertyName("movement")] public string Movement { get; set; } = "run";
        [JsonPropertyName("speed")] public float Speed { get; set; }
    }

    private sealed class NaturalFormation
    {
        [JsonPropertyName("id")] public string Id { get; set; } = "";
        [JsonPropertyName("side")] public string Side { get; set; } = "";
        [JsonPropertyName("node_ids")] public List<string> NodeIds { get; set; } = [];
        [JsonPropertyName("weight")] public int Weight { get; set; } = 1;
    }

    private sealed class NaturalRun(NaturalNode node,NaturalAnchor anchor,NaturalPeek? peek,NaturalEdge? edge,
        uint pawn,long move,int tick,int health,float baseX,float baseY,float strength,uint seed)
    {
        public NaturalNode Node=node;
        public NaturalAnchor Anchor=anchor;
        public NaturalPeek? Peek=peek;
        public NaturalEdge? Edge=edge;
        public uint Pawn=pawn, Seed=seed;
        public long Move=move, Buttons;
        public int StateTick=tick, Health=health, Checks, HoldTicks=52+(int)(seed%45);
        public float EntryX=baseX, EntryY=baseY, BaseX=baseX, BaseY=baseY, Strength=strength, YawVelocity, PitchVelocity;
        public float BestDistance=float.MaxValue;
        public int StableTicks, LastProgressTick=tick;
        public bool AimLocked;
        public ulong Mask;
        public string State="settle";
    }

    private sealed class NaturalTask
    {
        public int Slot, AssignedTick, DeadlineTick, LastProgressTick;
        public float BestDistance=float.MaxValue;
        public string Side="", Phase="opening", Kind="deploy", Lane="", TargetNodeId="", Reason="round_start";
    }

    private sealed class NaturalThreat(string lane,string source,int until)
    {
        public string Lane=lane, Source=source;
        public int Until=until, LastTick=Server.TickCount;
        public readonly Dictionary<string,int> Enemies=[];
        public int Score;
    }

    private sealed class NaturalRecovery(uint pawn,long move,int tick,int side)
    {
        public uint Pawn=pawn;
        public long Move=move;
        public int Tick=tick, Side=side;
    }

    private sealed record NaturalJumpBlock(uint Pawn,long Token);

    private NaturalPack? _naturalPack;
    private readonly Dictionary<string,NaturalNode> _naturalNodeById=[];
    private readonly Dictionary<string,List<NaturalEdge>> _naturalEdgesFrom=[];
    private readonly Dictionary<int,NaturalRun> _naturalRuns=[];
    private readonly Dictionary<int,NaturalRecovery> _naturalRecoveries=[];
    private readonly Dictionary<int,NaturalJumpBlock> _naturalJumpBlocks=[];
    private readonly Dictionary<int,string> _naturalAssignments=[];
    private readonly Dictionary<int,NaturalTask> _naturalTasks=[];
    private readonly Dictionary<int,string> _naturalLaneAssignments=[];
    private readonly Dictionary<int,int> _naturalLaneLockUntil=[];
    private readonly Dictionary<string,NaturalThreat> _naturalThreats=[];
    private readonly Dictionary<string,int> _naturalAssistedFirstSeen=[];
    private readonly Dictionary<int,float> _naturalNoiseTimestamps=[];
    private readonly Dictionary<string,int> _naturalCooldowns=[];
    private readonly Dictionary<int,int> _naturalStuckTicks=[], _naturalRecoveryCooldown=[];
    private readonly HashSet<string> _naturalNavValid=[];
    private int _naturalStarted, _naturalAssignmentRound=-1, _naturalPhaseTick, _naturalNavRetryTick;
    private bool _naturalEnabled, _naturalBombPlanted;
    private string _naturalFormationCt="", _naturalFormationT="", _naturalPhaseCt="opening", _naturalPhaseT="opening", _naturalStrategyT="default", _naturalBombLane="";

    private void NaturalLog(string reason,int slot=-1,string node="",string state="")
    {
        Server.PrintToConsole($"[CareerNatural] {reason} slot={slot} node={node} state={state}");
        try
        {
            var row=JsonSerializer.Serialize(new {
                version=ModuleVersion, nonce=_request?.Nonce, map=Server.MapName, round=_liveRounds,
                reason, slot, node, state,
                formation_ct=_naturalFormationCt, formation_t=_naturalFormationT,
                phase_ct=_naturalPhaseCt, phase_t=_naturalPhaseT, strategy_t=_naturalStrategyT,
                assignments=_naturalAssignments,
                tasks=_naturalTasks.ToDictionary(x=>x.Key,x=>new{x.Value.Phase,x.Value.Kind,x.Value.Lane,
                    target=x.Value.TargetNodeId,x.Value.Reason}),
                lane_assignments=_naturalLaneAssignments,
                threats=_naturalThreats.ToDictionary(x=>x.Key,x=>new{x.Value.Source,x.Value.Score,
                    enemies=x.Value.Enemies.Count,remaining_ticks=Math.Max(0,x.Value.Until-Server.TickCount)}),
                active=_naturalRuns.ToDictionary(x=>x.Key,x=>new{x.Value.Node.Id,x.Value.Anchor.Lane,x.Value.State,x.Value.AimLocked}),
                clips=_clipRuns.ToDictionary(x=>x.Key,x=>new{x.Value.Clip.Id,x.Value.Clip.Kind,x.Value.Time,
                    x.Value.Jumped,x.Value.Forward,x.Value.Left,x.Value.Speed,x.Value.ReferenceSpeed}),
                tick=Server.TickCount });
            File.WriteAllText(Path.Combine(ModuleDirectory,"natural_status.json"),row);
            var trace=Path.Combine(ModuleDirectory,"natural_trace.jsonl");
            if(File.Exists(trace)&&new FileInfo(trace).Length>512*1024) File.WriteAllText(trace,row+Environment.NewLine);
            else File.AppendAllText(trace,row+Environment.NewLine);
        }
        catch { }
    }

    private static bool Finite3(float[] values) => values.Length==3&&values.All(float.IsFinite);
    private static bool NaturalAnchorPlausible(NaturalNode node,NaturalAnchor anchor)
    {
        if(!Finite3(anchor.Target)) return false;
        var dx=anchor.Target[0]-node.Position[0]; var dy=anchor.Target[1]-node.Position[1];
        var horizontal=MathF.Sqrt(dx*dx+dy*dy);
        var pitch=MathF.Abs(MathF.Atan2(anchor.Target[2]-(node.Position[2]+64),Math.Max(1,horizontal))*180/MathF.PI);
        return horizontal is >=120 and <=3400&&pitch<=38;
    }
    private static readonly HashSet<string> NaturalLanes=[
        "a_long","a_short","a_site","mid","lower_tunnel","ct_spawn",
        "b_doors","b_hole","b_site","b_tunnels","t_spawn"];

    private void LoadNatural()
    {
        _naturalEnabled=false; _naturalPack=null; _naturalNodeById.Clear(); _naturalEdgesFrom.Clear();
        _naturalNavValid.Clear(); NaturalRoundReset();
        if(_request is not {Active:true,Map:"de_dust2"}||Server.MapName!="de_dust2") return;
        try
        {
            if(_request.MovementStyle is not JsonElement style||!style.TryGetProperty("active",out var active)
                ||active.GetString()!="natural") return;
            var path=style.GetProperty("route_path").GetString()??"";
            if(!File.Exists(path)||new FileInfo(path).Length>2*1024*1024) throw new Exception("node_pack_missing_or_oversize");
            var bytes=File.ReadAllBytes(path);
            if(!Convert.ToHexString(SHA256.HashData(bytes)).Equals(style.GetProperty("route_hash").GetString(),StringComparison.OrdinalIgnoreCase))
                throw new Exception("node_pack_hash_mismatch");
            var pack=JsonSerializer.Deserialize<NaturalPack>(bytes)??throw new Exception("node_pack_json_invalid");
            if(pack.SchemaVersion!=3||pack.Map!="de_dust2"||pack.Nodes.Count is <1 or >800||pack.Edges.Count>4000
                ||pack.Policy.MinimumHoldMs is <650 or >2500||pack.Policy.SafeMicroAdjust is <16 or >48
                ||pack.Policy.OpeningMaxMs is <10000 or >45000||pack.Policy.LateAfterMs is <45000 or >105000
                ||pack.Policy.StrategicAlertDelayMs is <250 or >2500||pack.Policy.StrategicMemoryMs is <1000 or >6000
                ||pack.Policy.TaskStallMs is <1200 or >6000||pack.Policy.ArrivalDistance is <8 or >24
                ||pack.Policy.ArrivalSpeed is <12 or >60||pack.Policy.ArrivalStableMs is <60 or >350
                ||pack.Coverage.CrossZoneEnemyCount is <2 or >5)
                throw new Exception("node_pack_contract_mismatch");
            foreach(var item in pack.Nodes)
            {
                if(item.Id.Length is <1 or >96||item.Side is not ("ct" or "t")||!Finite3(item.Position)
                    ||item.Zone is not ("a" or "b" or "mid" or "spawn" or "unknown")
                    ||item.Radius is <40 or >240||item.SafeRadius is <16 or >48||item.Anchors.Count>6||item.Peeks.Count>2
                    ||item.Anchors.Any(a=>!NaturalAnchorPlausible(item,a)||!NaturalLanes.Contains(a.Lane)
                        ||a.Confidence is not ("high" or "medium"))
                    ||item.Exposures.Any(e=>!NaturalLanes.Contains(e.Lane)||e.Events<1)
                    ||item.Peeks.Any(p=>!NaturalLanes.Contains(p.Lane)||p.Offset.Length!=2
                        ||p.Offset.Any(v=>!float.IsFinite(v)||Math.Abs(v)>48)
                        ||MathF.Sqrt(p.Offset[0]*p.Offset[0]+p.Offset[1]*p.Offset[1])>48
                        ||item.Anchors.All(a=>a.Lane!=p.Lane)))
                    throw new Exception("node_invalid:"+item.Id);
                if(!_naturalNodeById.TryAdd(item.Id,item)) throw new Exception("node_duplicate:"+item.Id);
            }
            if(pack.Edges.Any(e=>!_naturalNodeById.ContainsKey(e.From)||!_naturalNodeById.ContainsKey(e.To)
                    ||!float.IsFinite(e.Speed)||e.Speed is <0 or >300
                    ||NaturalMotion.Distance2(ToPoint(_naturalNodeById[e.From]),ToPoint(_naturalNodeById[e.To]))>280*280)
                ||pack.Formations.Any(f=>f.NodeIds.Any(id=>!_naturalNodeById.ContainsKey(id)))
                ||pack.Nodes.Any(n=>n.RetreatNodeIds.Any(id=>!_naturalNodeById.ContainsKey(id)))
                ||pack.Coverage.CtCriticalLanes.Any(lane=>!NaturalLanes.Contains(lane)))
                throw new Exception("node_reference_invalid");
            foreach(var edge in pack.Edges)
            {
                if(!_naturalEdgesFrom.TryGetValue(edge.From,out var rows)) _naturalEdgesFrom[edge.From]=rows=[];
                rows.Add(edge);
            }
            if(!pack.Nodes.Any(n=>n.Anchors.Count>0)) throw new Exception("no_evidence_aim_anchor");
            LoadCorners(style);
            LoadMotionClips(style);
            NaturalNative.Bind(Path.GetFullPath(Path.Combine(ModuleDirectory,"../../../BotController/bin/win64/BotController.dll")));
            _naturalPack=pack; _naturalEnabled=true;
            // OnMapStart can run before CS2 has published its navigation areas.
            // Validate immediately when possible; otherwise keep classic AI
            // untouched and retry from TickNatural after the map is live.
            if(!RefreshNaturalNav()&&_naturalEnabled)
                NaturalLog("ready_pending_nav",node:$"nodes={pack.Nodes.Count};anchors={pack.Nodes.Sum(n=>n.Anchors.Count)};peeks={pack.Nodes.Count(n=>n.Peeks.Count>0)}");
        }
        catch(Exception ex)
        {
            _naturalEnabled=false; _naturalPack=null; _cornerPack=null; _clipPack=null;
            _naturalNodeById.Clear(); _naturalEdgesFrom.Clear(); _naturalNavValid.Clear();
            // cfg was written before the server launched. If the runtime pack
            // is missing or corrupt, restore every classic value so fallback
            // applies to the whole match rather than only some bots.
            foreach(var command in new[]{
                "nav_smooth_spring_yaw_rotation_speed 999999",
                "nav_smooth_spring_yaw_threshold 359",
                "npcsolve_path_lookahead_const 20",
                "npcsolve_path_lookahead_dist 8000",
                "bot_defense_rush_chance 0"}) Server.ExecuteCommand(command);
            NaturalLog("disabled:"+ex.Message);
        }
    }

    private bool RefreshNaturalNav()
    {
        if(_naturalPack is null) return false;
        var navAreas=CCSNavArea.GetAllNavAreas();
        if(navAreas.Count==0) return false;
        _cornerNav.Clear();
        if(_cornerPack is not null)
            _cornerNav.AddRange(navAreas.Where(area=>_cornerPack.Actions.Any(a=>
                area.GetDistanceToPoint(new Vector(a.Start[0],a.Start[1],a.Start[2]))<120)));
        _naturalNavValid.Clear();
        foreach(var node in _naturalPack.Nodes)
        {
            var point=new Vector(node.Position[0],node.Position[1],node.Position[2]);
            if(navAreas.Any(area=>area.GetDistanceToPoint(point)<=72)) _naturalNavValid.Add(node.Id);
        }
        if(_naturalNavValid.Count<_naturalPack.Nodes.Count*.65f)
        {
            _naturalEnabled=false;
            _naturalNavValid.Clear();
            NaturalLog("disabled:node_nav_coverage_too_low",state:$"areas={navAreas.Count}");
            return false;
        }
        NaturalLog("nav_ready",node:$"nodes={_naturalPack.Nodes.Count};nav={_naturalNavValid.Count};areas={navAreas.Count}");
        return true;
    }

    private void NaturalRoundReset()
    {
        ResetMotionClips();
        ResetCorners();
        _naturalAssignments.Clear(); _naturalTasks.Clear(); _naturalLaneAssignments.Clear(); _naturalLaneLockUntil.Clear();
        _naturalThreats.Clear(); _naturalAssistedFirstSeen.Clear(); _naturalNoiseTimestamps.Clear();
        _naturalCooldowns.Clear(); _naturalStuckTicks.Clear(); _naturalBombPlanted=false; _naturalPhaseTick=0;
        _naturalAssignmentRound=-1; _naturalNavRetryTick=0; _naturalFormationCt=_naturalFormationT="";
        _naturalPhaseCt=_naturalPhaseT="opening"; _naturalStrategyT="default"; _naturalBombLane="";
    }

    private uint NaturalSeed(string value)
    {
        var raw=SHA256.HashData(Encoding.UTF8.GetBytes($"{_request?.Nonce}|{_liveRounds}|{value}"));
        return BitConverter.ToUInt32(raw,0);
    }

    private void StartNaturalRound()
    {
        _naturalStarted=Server.TickCount;
        if(!_naturalEnabled||_naturalPack is null) return;
        // Structured routing starts from a stable default. Coordinated deep
        // pushes are re-enabled only when a complete outward and retreat path
        // is represented by verified navigation nodes.
        NaturalLog("round_policy",state:"structured_default");
    }

    private static string NaturalZone(string place) => place switch
    {
        "ARamp" or "BombsiteA" or "Catwalk" or "ExtendedA" or "LongA" or "LongDoors"
            or "OutsideLong" or "Pit" or "ShortStairs" or "UnderA" => "a",
        "BombsiteB" or "BDoors" or "Hole" or "UpperTunnel" or "TunnelStairs" or "OutsideTunnel" => "b",
        "Middle" or "MidDoors" or "TopofMid" or "LowerTunnel" or "CTSpawn" => "mid",
        "TSpawn" or "TRamp" => "spawn",
        _ => "unknown"
    };

    private static string NaturalLane(string place) => place switch
    {
        "UpperTunnel" or "OutsideTunnel" or "TunnelStairs" => "b_tunnels",
        "BombsiteB" => "b_site", "BDoors" => "b_doors", "Hole" => "b_hole",
        "MidDoors" or "Middle" or "TopofMid" => "mid", "LowerTunnel" => "lower_tunnel",
        "CTSpawn" => "ct_spawn", "Catwalk" or "ShortStairs" or "UnderA" => "a_short",
        "LongDoors" or "OutsideLong" or "LongA" or "Pit" => "a_long",
        "ARamp" or "BombsiteA" or "ExtendedA" => "a_site",
        "TSpawn" or "TRamp" => "t_spawn", _ => ""
    };

    private static string NaturalLaneZone(string lane) => lane switch
    {
        "a_long" or "a_short" or "a_site" => "a",
        "b_doors" or "b_hole" or "b_site" or "b_tunnels" => "b",
        "mid" or "lower_tunnel" or "ct_spawn" => "mid",
        "t_spawn" => "spawn", _ => "unknown"
    };

    private void AddNaturalThreat(string side,string lane,string enemy,string source,int ticks,int score)
    {
        if(!_naturalEnabled||!NaturalLanes.Contains(lane)||side is not ("ct" or "t")) return;
        var key=$"{side}:{lane}";
        if(!_naturalThreats.TryGetValue(key,out var item))
            _naturalThreats[key]=item=new(lane,source,Server.TickCount+ticks);
        if(score>=item.Score) item.Source=source;
        item.Until=Math.Max(item.Until,Server.TickCount+ticks);
        item.LastTick=Server.TickCount; item.Score=Math.Max(item.Score,score);
        if(source!="sound"&&!string.IsNullOrEmpty(enemy)) item.Enemies[enemy]=Server.TickCount+ticks;
    }

    private void NaturalObserveCombat(CCSPlayerController? attacker,CCSPlayerController? victim,bool death)
    {
        if(!_roundLive||attacker is not {IsValid:true}||victim is not {IsValid:true}||attacker==victim) return;
        var attackerSide=LiveSide(attacker); var victimSide=LiveSide(victim);
        if(attackerSide.Length==0||victimSide.Length==0||attackerSide==victimSide) return;
        var attackerPlace=attacker.PlayerPawn.Value?.LastPlaceName??"";
        var victimPlace=victim.PlayerPawn.Value?.LastPlaceName??"";
        var ticks=death?MsTicks(_naturalPack?.Policy.CasualtyMemoryMs??6000):MsTicks(_naturalPack?.Policy.VisualMemoryMs??4000);
        AddNaturalThreat(attackerSide,NaturalLane(victimPlace),ControllerId(victim)??victim.Slot.ToString(),
            death?"enemy_down":"firefight",ticks,death?70:90);
        AddNaturalThreat(victimSide,NaturalLane(attackerPlace),ControllerId(attacker)??attacker.Slot.ToString(),
            death?"defender_down":"firefight",ticks,death?105:90);
    }

    private void NaturalBombPlanted(EventBombPlanted ev)
    {
        if(!_roundLive) return;
        _naturalBombPlanted=true;
        var place=ev.Userid?.PlayerPawn.Value?.LastPlaceName??"";
        var lane=NaturalZone(place)=="b"?"b_site":NaturalZone(place)=="a"?"a_site":ev.Site==1?"b_site":"a_site";
        _naturalBombLane=lane;
        AddNaturalThreat("ct",lane,"bomb","bomb",64*180,250);
        NaturalLog("bomb_planted",state:lane);
    }
    private void NaturalBombCleared() { _naturalBombPlanted=false; _naturalBombLane=""; }

    private void PruneNaturalThreats()
    {
        foreach(var key in _naturalThreats.Keys.ToArray())
        {
            var item=_naturalThreats[key];
            foreach(var enemy in item.Enemies.Where(x=>x.Value<=Server.TickCount).Select(x=>x.Key).ToArray())
                item.Enemies.Remove(enemy);
            if(item.Until<=Server.TickCount) _naturalThreats.Remove(key);
        }
    }

    private NaturalThreat? NaturalThreatFor(string side,string lane)
        => _naturalThreats.GetValueOrDefault($"{side}:{lane}") is { } item&&item.Until>Server.TickCount?item:null;

    private bool NaturalCanRotate(string currentZone,string lane,NaturalThreat? threat)
    {
        return NaturalMotion.CanRotate(currentZone,NaturalLaneZone(lane),threat?.Source??"",
            threat?.Enemies.Count??0,_naturalPack?.Coverage.CrossZoneEnemyCount??2);
    }

    private void ReleaseNatural(int slot,string reason)
    {
        if(!_naturalRuns.Remove(slot,out var run)) return;
        try
        {
            // Radio handoff cannot leave the movement token running just
            // because cancelling one old stance/button token failed.
            try { if(run.Buttons>0) NaturalNative.CancelButtons(slot,run.Buttons); }
            finally { NaturalNative.CancelMove(slot,run.Move); }
        }
        finally { if(run.AimLocked) NaturalNative.Unlock(slot,1); }
        _naturalCooldowns[$"{slot}:{run.Node.Id}"]=Server.TickCount+2*64;
        NaturalLog(reason,slot,run.Node.Id,run.State);
    }

    private void ReleaseNaturalRecovery(int slot,string reason)
    {
        if(!_naturalRecoveries.Remove(slot,out var run)) return;
        NaturalNative.CancelMove(slot,run.Move); _naturalRecoveryCooldown[slot]=Server.TickCount+5*64;
        NaturalLog(reason,slot,state:"unstuck_strafe");
    }

    private void ReleaseNaturalJumpBlock(int slot)
    {
        if(_naturalJumpBlocks.Remove(slot,out var block)) NaturalNative.CancelSuppression(slot,block.Token);
    }

    // Match policy, not an action lock: stop native jump-unsticking even in
    // combat. Explicit clip jump pulses override it in ABI20. Humans, death,
    // round end, classic fallback and unload release this policy separately.
    private void EnsureNaturalJumpBlock(int slot,uint pawn)
    {
        if(_naturalJumpBlocks.ContainsKey(slot)) return;
        var token=NaturalNative.StartSuppression(slot,1UL<<1);
        if(token>0) _naturalJumpBlocks[slot]=new(pawn,token);
    }

    private void StopNatural(string reason)
    {
        foreach(var slot in _clipRuns.Keys.ToArray()) try { ReleaseMotionClip(slot,reason); } catch { }
        foreach(var slot in _cornerRuns.Keys.ToArray()) try { ReleaseCorner(slot,reason); } catch { }
        foreach(var slot in _naturalRuns.Keys.ToArray()) try { ReleaseNatural(slot,reason); } catch { }
        foreach(var slot in _naturalRecoveries.Keys.ToArray()) try { ReleaseNaturalRecovery(slot,reason); } catch { }
        foreach(var slot in _naturalJumpBlocks.Keys.ToArray()) try { ReleaseNaturalJumpBlock(slot); } catch { }
        _naturalStuckTicks.Clear(); _naturalStarted=0;
    }

    public override void Unload(bool hotReload)
    {
        StopTacticalCommands("unload");
        StopNatural("unload");
    }

    private BotConfig? NaturalConfig(int slot)
    {
        if(_request is null||!_slotIds.TryGetValue(slot,out var id)) return null;
        return _request.Ct.Players.Concat(_request.T.Players).FirstOrDefault(x=>x.PlayerId==id);
    }

    private static string LiveSide(CCSPlayerController player)
        => player.Team==CsTeam.CounterTerrorist?"ct":player.Team==CsTeam.Terrorist?"t":"";

    private static float NodeDistance2(NaturalNode node,Vector point)
        => MathF.Pow(node.Position[0]-point.X,2)+MathF.Pow(node.Position[1]-point.Y,2)+2*MathF.Pow(node.Position[2]-point.Z,2);

    private static NaturalMotion.Point3 ToPoint(NaturalNode node)
        => new(node.Position[0],node.Position[1],node.Position[2]);

    private NaturalNode? NearestNode(Vector point,string side,bool aimOnly=false)
        => _naturalPack?.Nodes.Where(n=>n.Side==side&&(!aimOnly||n.Anchors.Count>0)).MinBy(n=>NodeDistance2(n,point));

    private static bool NaturalTransitPlace(string place)
        => place is "CTSpawn" or "TSpawn" or "TRamp";

    private static int NaturalRoleLaneScore(string role,string lane) => role switch
    {
        "awp" when lane is "mid" or "a_long" => 120,
        "entry" when lane is "a_long" or "b_tunnels" => 105,
        "lurk" when lane is "mid" or "lower_tunnel" or "a_short" => 90,
        "igl" when lane is "b_doors" or "a_short" or "mid" => 70,
        _ => 40
    };

    private NaturalNode? NaturalNodeForLane(string side,string lane,string role,
        HashSet<string> usedGroups,bool allowEnemyTerritory=false)
    {
        if(_naturalPack is null) return null;
        return _naturalPack.Nodes.Where(n=>n.Side==side&&_naturalNavValid.Contains(n.Id)
                &&!NaturalTransitPlace(n.Place)&&!usedGroups.Contains(n.CoverGroup)
                &&n.Anchors.Any(a=>a.Lane==lane)
                &&(allowEnemyTerritory||(side=="ct"?n.Territory!="t_home":n.Territory!="ct_home")))
            .MaxBy(n=>NaturalRoleLaneScore(role,lane)*10000+n.RoleWeights.GetValueOrDefault(role)*100
                +n.Anchors.Where(a=>a.Lane==lane).Sum(a=>a.Confidence=="high"?30:10)
                +(n.Territory=="ct_home"?25:0));
    }

    private void SetNaturalTask(CCSPlayerController player,string phase,string kind,string lane,
        NaturalNode node,string reason,int deadlineSeconds=22)
    {
        if (NativeRadioOwnsActor(player) || NativeSafetyOwnsActor(player)) return;
        if(_naturalTasks.TryGetValue(player.Slot,out var old)&&old.TargetNodeId==node.Id
            &&old.Kind==kind&&old.Phase==phase) return;
        ReleaseMotionClip(player.Slot,"task_changed");
        ReleaseCorner(player.Slot,"task_changed");
        ReleaseNatural(player.Slot,"task_changed");
        _naturalAssignments[player.Slot]=node.Id;
        _naturalTasks[player.Slot]=new NaturalTask {Slot=player.Slot,Side=LiveSide(player),Phase=phase,
            Kind=kind,Lane=lane,TargetNodeId=node.Id,Reason=reason,AssignedTick=Server.TickCount,
            LastProgressTick=Server.TickCount,DeadlineTick=Server.TickCount+deadlineSeconds*64};
        NaturalLog("task_assigned",player.Slot,node.Id,$"{phase}:{kind}:{lane}:{reason}");
    }

    private void AssignDefaultTasks(List<CCSPlayerController> players,string side)
    {
        var bots=players.Where(p=>LiveSide(p)==side&&NaturalConfig(p.Slot) is not null
                &&p.PlayerPawn.Value is {Health:>0}).ToList();
        if(bots.Count==0) return;
        string[] lanes;
        if(side=="ct")
            lanes=bots.Count>=5?["a_long","mid","b_tunnels","b_doors","a_short"]
                :["a_long","mid","b_tunnels","b_doors"];
        else
        {
            _naturalStrategyT=(NaturalSeed("t_strategy")%3) switch {0=>"a_control",1=>"b_control",_=>"default_control"};
            lanes=_naturalStrategyT switch
            {
                "a_control"=>["a_long","a_long","a_short","mid","lower_tunnel"],
                "b_control"=>["b_tunnels","b_tunnels","mid","lower_tunnel","a_long"],
                _=>["a_long","a_short","mid","lower_tunnel","b_tunnels"]
            };
        }
        var usedGroups=new HashSet<string>();
        var available=new List<CCSPlayerController>(bots);
        foreach(var lane in lanes.Take(bots.Count))
        {
            var bot=available.MaxBy(p=>NaturalRoleLaneScore(NaturalConfig(p.Slot)!.Role,lane));
            if(bot is null) break;
            var cfg=NaturalConfig(bot.Slot)!;
            var node=NaturalNodeForLane(side,lane,cfg.Role,usedGroups);
            if(node is null) continue;
            SetNaturalTask(bot,"opening",side=="ct"?"deploy_hold":"take_control",lane,node,"default_plan");
            usedGroups.Add(node.CoverGroup); available.Remove(bot);
        }
        if(side=="ct") _naturalFormationCt="structured_default";
        else _naturalFormationT="structured_"+_naturalStrategyT;
    }

    private void EnsureNaturalAssignments(List<CCSPlayerController> players)
    {
        if(_naturalPack is null||_naturalAssignmentRound==_liveRounds) return;
        _naturalAssignmentRound=_liveRounds;
        AssignDefaultTasks(players,"ct");
        AssignDefaultTasks(players,"t");
        NaturalLog("formations_assigned");
    }

    private string NaturalPhaseFor(string side,List<CCSPlayerController> players)
    {
        var ownAlive=players.Count(p=>LiveSide(p)==side&&p.PlayerPawn.Value is {Health:>0});
        var enemyAlive=players.Count(p=>LiveSide(p)!=""&&LiveSide(p)!=side&&p.PlayerPawn.Value is {Health:>0});
        var elapsed=Math.Max(0,Server.TickCount-_naturalStarted);
        var pressure=_naturalThreats.Where(x=>x.Key.StartsWith(side+":",StringComparison.Ordinal)
                &&x.Value.Until>Server.TickCount).Select(x=>x.Value.Score).DefaultIfEmpty(0).Max();
        return NaturalMotion.RoundPhase(elapsed,_naturalBombPlanted,ownAlive,enemyAlive,pressure,
            NaturalTicks(_naturalPack?.Policy.OpeningMaxMs??22000),NaturalTicks(_naturalPack?.Policy.LateAfterMs??75000));
    }

    private NaturalThreat? StrongestNaturalThreat(string side)
        => _naturalThreats.Where(x=>x.Key.StartsWith(side+":",StringComparison.Ordinal)
                &&x.Value.Until>Server.TickCount)
            .Select(x=>x.Value).OrderByDescending(x=>x.Score).ThenByDescending(x=>x.LastTick).FirstOrDefault();

    private void AssignPhaseTasks(List<CCSPlayerController> players,string side,string phase,string reason)
    {
        var bots=players.Where(p=>LiveSide(p)==side&&NaturalConfig(p.Slot) is not null
                &&p.PlayerPawn.Value is {Health:>0}).ToList();
        if(bots.Count==0) return;
        var usedGroups=new HashSet<string>();
        if(phase=="opening") { AssignDefaultTasks(players,side); return; }

        string lane,kind;
        var threat=StrongestNaturalThreat(side);
        if(phase=="late"&&_naturalBombPlanted)
        {
            lane=_naturalBombLane is "a_site" or "b_site"?_naturalBombLane:
                threat?.Lane is "a_site" or "b_site"?threat.Lane:"a_site";
            kind=side=="ct"?"retake":"postplant_hold";
        }
        else if(side=="t")
        {
            lane=_naturalStrategyT=="b_control"?"b_site":_naturalStrategyT=="a_control"?"a_site":
                (NaturalSeed("execute_site")%2==0?"a_site":"b_site");
            kind=phase=="late"?"secure_objective":"execute_site";
        }
        else
        {
            // A single sound is useful for attention, but it cannot move a
            // defender across the map. A defender already in the threatened
            // zone may adjust; confirmed pressure or a fallen anchor can add
            // one cross-zone supporter while the rest retain coverage.
            if(threat is null) return;
            lane=threat.Lane; kind=phase=="late"?"clutch_reposition":"support_defense";
            var canCross=NaturalMotion.AssistedIntelCanRelocate(threat.Source,threat.Enemies.Count);
            var ordered=bots.OrderBy(p=>
            {
                var pos=p.PlayerPawn.Value?.AbsOrigin;
                return pos is null?float.MaxValue:_naturalPack!.Nodes.Where(n=>n.Side==side&&n.Anchors.Any(a=>a.Lane==lane))
                    .Select(n=>NodeDistance2(n,pos)).DefaultIfEmpty(float.MaxValue).Min();
            }).ToList();
            var sameZone=ordered.Where(p=>_naturalTasks.GetValueOrDefault(p.Slot) is { } old
                &&NaturalLaneZone(old.Lane)==NaturalLaneZone(lane)).Take(1).ToList();
            if(canCross)
                sameZone.AddRange(ordered.Where(p=>!sameZone.Contains(p)).Take(phase=="late"?bots.Count-1:1));
            if(sameZone.Count==0) return;
            bots=sameZone;
        }

        foreach(var bot in bots)
        {
            var cfg=NaturalConfig(bot.Slot)!;
            var node=NaturalNodeForLane(side,lane,cfg.Role,usedGroups,
                allowEnemyTerritory:phase=="late"||(side=="t"&&phase=="middle"));
            if(node is null) continue;
            SetNaturalTask(bot,phase,kind,lane,node,reason,phase=="late"?14:20);
            usedGroups.Add(node.CoverGroup);
        }
    }

    private void UpdateNaturalPhases(List<CCSPlayerController> players)
    {
        if(Server.TickCount<_naturalPhaseTick) return;
        _naturalPhaseTick=Server.TickCount+16;
        var ct=NaturalPhaseFor("ct",players); var t=NaturalPhaseFor("t",players);
        if(ct!=_naturalPhaseCt)
        {
            _naturalPhaseCt=ct; AssignPhaseTasks(players,"ct",ct,"phase_change");
            NaturalLog("phase_changed",state:"ct:"+ct);
        }
        else if(ct!="opening"&&StrongestNaturalThreat("ct") is {Score:>=105})
            AssignPhaseTasks(players,"ct",ct,"confirmed_pressure");
        if(t!=_naturalPhaseT)
        {
            _naturalPhaseT=t; AssignPhaseTasks(players,"t",t,"phase_change");
            NaturalLog("phase_changed",state:"t:"+t);
        }
    }

    private NaturalNode? NaturalTaskNode(int slot)
        => _naturalTasks.GetValueOrDefault(slot) is { } task
            &&_naturalNodeById.GetValueOrDefault(task.TargetNodeId) is { } node
            &&_naturalNavValid.Contains(node.Id)?node:null;

    private bool NaturalTaskOccupiedByHuman(NaturalNode node,string side,List<CCSPlayerController> players)
        => players.Any(p=>LiveSide(p)==side&&NaturalConfig(p.Slot) is null
            &&p.PlayerPawn.Value?.AbsOrigin is { } pos&&NodeDistance2(node,pos)<90*90);

    private NaturalNode? MoveTaskAwayFromHuman(CCSPlayerController player,NaturalTask task,
        NaturalNode node,List<CCSPlayerController> players,BotConfig cfg)
    {
        if(!NaturalTaskOccupiedByHuman(node,task.Side,players)) return node;
        var used=_naturalTasks.Where(x=>x.Key!=player.Slot)
            .Select(x=>_naturalNodeById.GetValueOrDefault(x.Value.TargetNodeId)?.CoverGroup)
            .Where(x=>!string.IsNullOrEmpty(x)).Select(x=>x!).ToHashSet();
        used.Add(node.CoverGroup);
        var replacement=NaturalNodeForLane(task.Side,task.Lane,cfg.Role,used,
            allowEnemyTerritory:task.Phase=="late"||(task.Side=="t"&&task.Phase=="middle"));
        if(replacement is null) return null;
        SetNaturalTask(player,task.Phase,task.Kind,task.Lane,replacement,"human_occupied",20);
        return replacement;
    }

    private bool GuideNaturalTask(CCSPlayerController player,CCSBot bot,Vector pos,NaturalTask task,NaturalNode node)
    {
        var distance=MathF.Sqrt(NodeDistance2(node,pos));
        if(distance+10<task.BestDistance)
        {
            task.BestDistance=distance; task.LastProgressTick=Server.TickCount;
        }
        if(NaturalMotion.TaskExpired(Server.TickCount,task.DeadlineTick,task.LastProgressTick,
            NaturalTicks(_naturalPack?.Policy.TaskStallMs??3000)))
        {
            NaturalLog("task_timeout",player.Slot,node.Id,$"{task.Kind}:distance={distance:0}");
            _naturalTasks.Remove(player.Slot); _naturalAssignments.Remove(player.Slot); return false;
        }
        if(distance<=Math.Min(46,node.SafeRadius)) return true;
        // Long travel stays under CS2's pathfinder. Updating its destination
        // gives the task a real effect while preserving doors, stairs, ladders,
        // collision avoidance and teammate yielding.
        bot.GoalPosition.X=node.Position[0]; bot.GoalPosition.Y=node.Position[1]; bot.GoalPosition.Z=node.Position[2];
        return false;
    }

    private void NaturalObserveBotInfo(CCSPlayerController player,CCSBot bot,List<CCSPlayerController> players)
    {
        var side=LiveSide(player);
        try
        {
            if(bot.IsEnemyVisible&&bot.Enemy.Value is {IsValid:true} enemy)
            {
                var enemyController=players.FirstOrDefault(p=>p.PlayerPawn.Value?.EntityHandle.Raw==enemy.EntityHandle.Raw);
                var enemyId=ControllerId(enemyController)??$"pawn:{enemy.EntityHandle.Raw}";
                AddNaturalThreat(side,NaturalLane(enemy.LastPlaceName),enemyId,"visible",
                    MsTicks(_naturalPack?.Policy.VisualMemoryMs??4000),120);
            }
        }
        catch { }
        try
        {
            var stamp=bot.NoiseTimestamp;
            if(stamp>0&&stamp>_naturalNoiseTimestamps.GetValueOrDefault(player.Slot))
            {
                _naturalNoiseTimestamps[player.Slot]=stamp;
                var enemySide=side=="ct"?"t":"ct";
                var node=NearestNode(bot.NoisePosition,enemySide);
                if(node is not null&&NodeDistance2(node,bot.NoisePosition)<700*700)
                    AddNaturalThreat(side,NaturalLane(node.Place),$"sound:{player.Slot}","sound",
                        MsTicks(_naturalPack?.Policy.SoundMemoryMs??2000),25);
            }
        }
        catch { }
    }

    private static string NaturalStrategicIntrusionLane(string observingSide,string place)
    {
        if(observingSide=="ct") return place switch
        {
            "LongA" or "Pit"=>"a_long",
            "Catwalk" or "ShortStairs" or "UnderA"=>"a_short",
            "MidDoors" or "CTSpawn"=>"mid",
            "BDoors"=>"b_doors", "Hole"=>"b_hole",
            "TunnelStairs" or "OutsideTunnel"=>"b_tunnels",
            "BombsiteA" or "ARamp" or "ExtendedA"=>"a_site",
            "BombsiteB"=>"b_site", _=>""
        };
        return place switch
        {
            "TSpawn" or "TRamp"=>"t_spawn",
            "LongDoors" or "OutsideLong"=>"a_long",
            "TopofMid" or "LowerTunnel"=>"mid",
            "UpperTunnel"=>"b_tunnels", _=>""
        };
    }

    private void UpdateAssistedTeamIntel(List<CCSPlayerController> players)
    {
        // This is deliberately coarse strategic help: after a short delay the
        // team learns that an important entrance has been crossed. It never
        // writes an enemy position or angle into the combat bot.
        var observed=new HashSet<string>();
        foreach(var observingSide in new[]{"ct","t"})
        foreach(var enemy in players.Where(p=>LiveSide(p)!=""&&LiveSide(p)!=observingSide
                    &&p.PlayerPawn.Value is {Health:>0}))
        {
            var lane=NaturalStrategicIntrusionLane(observingSide,enemy.PlayerPawn.Value!.LastPlaceName);
            if(string.IsNullOrEmpty(lane)) continue;
            var enemyId=ControllerId(enemy)??$"slot:{enemy.Slot}";
            var key=$"{observingSide}:{enemyId}:{lane}"; observed.Add(key);
            if(!_naturalAssistedFirstSeen.TryGetValue(key,out var first))
            { _naturalAssistedFirstSeen[key]=Server.TickCount; continue; }
            if(Server.TickCount-first>=NaturalTicks(_naturalPack?.Policy.StrategicAlertDelayMs??750))
                AddNaturalThreat(observingSide,lane,enemyId,"assist_region",
                    MsTicks(_naturalPack?.Policy.StrategicMemoryMs??2500),95);
        }
        foreach(var key in _naturalAssistedFirstSeen.Keys.Where(k=>!observed.Contains(k)).ToArray())
            _naturalAssistedFirstSeen.Remove(key);
    }

    private static int NaturalLanePriority(string zone,string lane) => (zone,lane) switch
    {
        ("a","a_long")=>70, ("a","a_short")=>65, ("a","a_site")=>40, ("a","mid")=>20,
        ("b","b_tunnels")=>70, ("b","b_doors")=>65, ("b","b_hole")=>45,
        ("b","b_site")=>35, ("b","mid")=>25,
        ("mid","mid")=>75, ("mid","lower_tunnel")=>60, ("mid","a_short")=>45,
        ("mid","b_doors")=>40, ("mid","ct_spawn")=>25,
        _=>10
    };

    private NaturalAnchor? SelectNaturalAnchor(CCSPlayerController player,NaturalNode node,
        List<CCSPlayerController> players)
    {
        var side=LiveSide(player);
        var activeExposure=node.Exposures.Select(e=>(e.Lane,Threat:NaturalThreatFor(side,e.Lane)))
            .Where(x=>x.Threat is not null&&x.Threat.Score>=80)
            .OrderByDescending(x=>x.Threat!.Score).ThenByDescending(x=>x.Threat!.LastTick).ToArray();
        if(activeExposure.Length>0&&NaturalMotion.ExposureRequiresFallback(activeExposure[0].Lane,node.Anchors.Select(a=>a.Lane)))
        {
            var logKey=$"fallback:{player.Slot}:{node.Id}:{activeExposure[0].Lane}";
            if(_naturalCooldowns.GetValueOrDefault(logKey)<=Server.TickCount)
            {
                _naturalCooldowns[logKey]=Server.TickCount+2*64;
                NaturalLog("fallback_exposed_lane_uncovered",player.Slot,node.Id,activeExposure[0].Lane);
            }
            return null;
        }
        var covered=_naturalLaneAssignments.Where(x=>x.Key!=player.Slot&&_naturalRuns.ContainsKey(x.Key)
                &&players.Any(p=>p.Slot==x.Key&&p.PlayerPawn.Value is {Health:>0}))
            .GroupBy(x=>x.Value).ToDictionary(g=>g.Key,g=>g.Count());
        var current=_naturalLaneAssignments.GetValueOrDefault(player.Slot);
        var locked=_naturalLaneLockUntil.GetValueOrDefault(player.Slot)>Server.TickCount;
        var taskLane=activeExposure.Length>0?activeExposure[0].Lane:_naturalTasks.GetValueOrDefault(player.Slot)?.Lane;
        var tasked=node.Anchors.Where(anchor=>string.IsNullOrEmpty(taskLane)||anchor.Lane==taskLane).ToArray();
        var options=(tasked.Length>0?tasked:node.Anchors.ToArray()).Where(anchor=>
        {
            var threat=NaturalThreatFor(side,anchor.Lane);
            return NaturalCanRotate(node.Zone,anchor.Lane,threat);
        }).ToArray();
        if(options.Length==0) return null;
        var selected=options.MaxBy(anchor=>
        {
            var threat=NaturalThreatFor(side,anchor.Lane);
            var score=NaturalMotion.CoverageScore(NaturalLanePriority(node.Zone,anchor.Lane),threat?.Score??0,
                threat?.Enemies.Count??0,covered.GetValueOrDefault(anchor.Lane),
                (_naturalPack?.Coverage.CtCriticalLanes.Contains(anchor.Lane)??false)&&side=="ct",
                anchor.Confidence=="high",current==anchor.Lane,locked,
                activeExposure.Length>0&&activeExposure[0].Lane==anchor.Lane);
            score+=(int)(NaturalSeed($"lane-jitter:{player.Slot}:{anchor.Id}")%7);
            return score;
        });
        if(selected is null) return null;
        if(current!=selected.Lane)
        {
            _naturalLaneAssignments[player.Slot]=selected.Lane;
            _naturalLaneLockUntil[player.Slot]=Server.TickCount+MsTicks(_naturalPack?.Policy.MinimumHoldMs??800);
            NaturalLog("coverage_assigned",player.Slot,node.Id,$"lane={selected.Lane};threat={NaturalThreatFor(side,selected.Lane)?.Source??"default"}");
        }
        return selected;
    }

    private bool StartNaturalControl(CCSPlayerController player,NaturalNode node,NaturalAnchor anchor,
        NaturalEdge? edge,Vector pos,BotConfig cfg)
    {
        var key=$"{player.Slot}:{node.Id}";
        if(_naturalCooldowns.GetValueOrDefault(key)>Server.TickCount||NaturalNative.IsLocked(player.Slot,0)!=0
            ||NaturalNative.IsLocked(player.Slot,1)!=0) return false;
        var pawn=player.PlayerPawn.Value!; var seed=NaturalSeed(cfg.PlayerId+":"+node.Id+":"+anchor.Lane);
        var peeks=node.Peeks.Where(p=>p.Lane==anchor.Lane).ToArray();
        var peek=peeks.Length==0?null:peeks[(int)((seed>>8)%(uint)peeks.Length)];
        var move=NaturalNative.StartMove(player.Slot,0,0);
        if(move<=0) return false;
        _naturalRuns[player.Slot]=new NaturalRun(node,anchor,peek,edge,
            pawn.EntityHandle.Raw,move,Server.TickCount,pawn.Health,
            pos.X,pos.Y,Math.Clamp(cfg.EffectiveStrength,45,100),seed);
        NaturalLog("node_enter",player.Slot,node.Id,"settle"); return true;
    }

    private static int MsTicks(int value) => Math.Clamp((int)MathF.Round(value*64/1000f),2,160);
    private static int NaturalTicks(int value) => Math.Clamp((int)MathF.Round(value/1000f/Server.TickInterval),1,(int)(120/Server.TickInterval));

    private static float PeekSpeed(NaturalPeek peek,bool returning)
    {
        var distance=MathF.Sqrt(peek.Offset[0]*peek.Offset[0]+peek.Offset[1]*peek.Offset[1]);
        var milliseconds=returning?peek.BackMs:peek.OutMs;
        return Math.Clamp(distance/Math.Max(.08f,milliseconds/1000f),55,170);
    }

    private void SetNaturalButtons(int slot,NaturalRun run,bool walk,bool duck)
    {
        ulong mask=(walk?1UL<<16:0)|(duck?1UL<<2:0);
        if(mask==run.Mask) return;
        if(run.Buttons>0) NaturalNative.CancelButtons(slot,run.Buttons);
        run.Buttons=mask==0?0:NaturalNative.Inject(slot,mask,5000); run.Mask=mask;
    }

    private bool MoveNatural(int slot,NaturalRun run,Vector pos,float x,float y,float speed,float yaw,bool walk=false,bool duck=false)
    {
        var dx=x-pos.X; var dy=y-pos.Y; var length=MathF.Sqrt(dx*dx+dy*dy);
        SetNaturalButtons(slot,run,walk,duck);
        if(length<7) return NaturalNative.UpdateMove(slot,run.Move,0,0)==0;
        var velocity=Utilities.GetPlayerFromSlot(slot)?.PlayerPawn.Value?.AbsVelocity;
        var desired=Math.Min(speed,length*8); // brake on approach; speed no longer cancels itself
        var input=ClipMotion.Command(0,0,dx/length*desired,dy/length*desired,velocity?.X??0,velocity?.Y??0,yaw);
        return NaturalNative.UpdateMove(slot,run.Move,input.Forward,input.Left)==0;
    }

    private bool UpdateNaturalRun(CCSPlayerController player,NaturalRun run,Vector pos)
    {
        var pawn=player.PlayerPawn.Value!; var bot=pawn.Bot!; var age=Server.TickCount-run.StateTick;
        var tune=NaturalMotion.Skill(run.Strength); var liveEye=bot.EyePosition;
        var eye=new NaturalMotion.Point3(liveEye.X,liveEye.Y,liveEye.Z);
        var target=new NaturalMotion.Point3(run.Anchor.Target[0],run.Anchor.Target[1],run.Anchor.Target[2]);
        var desired=NaturalMotion.AimAt(eye,target);
        var noise=(NaturalMotion.Unit(run.Seed+(uint)(run.Checks*97+13))*2-1)*tune.ErrorDegrees;
        var desiredYaw=desired.Yaw+noise; var desiredPitch=Math.Clamp(desired.Pitch+noise*.35f,-35,35);
        var yawStep=NaturalMotion.SmoothAngle(pawn.EyeAngles.Y,desiredYaw,run.YawVelocity,180+run.Strength*1.2f,820+run.Strength*4);
        var pitchStep=NaturalMotion.SmoothAngle(pawn.EyeAngles.X,desiredPitch,run.PitchVelocity,110,480);
        run.YawVelocity=yawStep.Velocity; run.PitchVelocity=pitchStep.Velocity;
        if(run.AimLocked)
        {
            bot.LookYaw=yawStep.Angle; bot.LookPitch=pitchStep.Angle;
            pawn.Teleport(null,new QAngle(pitchStep.Angle,yawStep.Angle,0),null);
        }

        if(run.State=="settle")
        {
            var movement=run.Edge?.Movement??run.Node.Movement;
            var measured=run.Edge?.Speed??run.Node.Speed;
            var travelSpeed=Math.Clamp(measured,movement=="run"?150:65,movement=="run"?250:145);
            var distance=MathF.Sqrt(NodeDistance2(run.Node,pos));
            if(distance+2<run.BestDistance) { run.BestDistance=distance; run.LastProgressTick=Server.TickCount; }
            var arrivalDistance=_naturalPack?.Policy.ArrivalDistance??14;
            var arrivalSpeed=_naturalPack?.Policy.ArrivalSpeed??28;
            if(distance<=arrivalDistance&&pawn.AbsVelocity.Length2D()<arrivalSpeed)
            {
                NaturalNative.UpdateMove(player.Slot,run.Move,0,0); run.StableTicks++;
                if(NaturalMotion.CanLockAim(distance,pawn.AbsVelocity.Length2D(),run.StableTicks,
                    arrivalDistance,arrivalSpeed,NaturalTicks(_naturalPack?.Policy.ArrivalStableMs??94)))
                {
                    if(NaturalNative.Lock(player.Slot,1,0)!=0) return false;
                    run.AimLocked=true; run.BaseX=pos.X; run.BaseY=pos.Y;
                    run.State="hold"; run.StateTick=Server.TickCount;
                    NaturalLog("node_hold",player.Slot,run.Node.Id,run.State);
                }
                return true;
            }
            run.StableTicks=0;
            if(Server.TickCount-run.LastProgressTick>64) return false;
            if(!MoveNatural(player.Slot,run,pos,run.Node.Position[0],run.Node.Position[1],travelSpeed,pawn.EyeAngles.Y,
                movement=="walk",movement=="crouch_move")) return false;
            return true;
        }
        if(run.State=="hold")
        {
            if(NaturalNative.UpdateMove(player.Slot,run.Move,0,0)!=0) return false;
            if(age<run.HoldTicks) return true;
            var usePeek=run.Peek is not null&&run.Checks<run.Peek.MaxChecks
                &&NaturalMotion.Unit(run.Seed+(uint)(run.Checks*31+71))<.68f;
            if(!usePeek)
            {
                run.StateTick=Server.TickCount; run.HoldTicks=50+(int)((run.Seed+(uint)(run.Checks*17+3))%70);
                return true;
            }
            run.State="peek_out"; run.StateTick=Server.TickCount;
            NaturalLog("peek_started",player.Slot,run.Node.Id,run.Peek!.Id); return true;
        }
        if(run.State=="peek_out")
        {
            var peekTarget=NaturalMotion.PeekTarget(new(run.BaseX,run.BaseY,pos.Z),run.Peek!.Offset[0],run.Peek.Offset[1]);
            if(!MoveNatural(player.Slot,run,pos,peekTarget.X,peekTarget.Y,PeekSpeed(run.Peek,false),yawStep.Angle,walk:true)) return false;
            if(age>=MsTicks(run.Peek.OutMs)) { run.State="peek_hold"; run.StateTick=Server.TickCount; }
            return true;
        }
        if(run.State=="peek_hold")
        {
            if(NaturalNative.UpdateMove(player.Slot,run.Move,0,0)!=0) return false;
            if(age>=MsTicks(run.Peek!.HoldMs)) { run.State="peek_back"; run.StateTick=Server.TickCount; }
            return true;
        }
        if(run.State=="peek_back")
        {
            if(!MoveNatural(player.Slot,run,pos,run.BaseX,run.BaseY,PeekSpeed(run.Peek!,true),yawStep.Angle,walk:true)) return false;
            if(age>=MsTicks(run.Peek!.BackMs)||MathF.Pow(pos.X-run.BaseX,2)+MathF.Pow(pos.Y-run.BaseY,2)<12*12)
            {
                run.Checks++; run.State="hold"; run.StateTick=Server.TickCount; run.HoldTicks=36+(int)((run.Seed>>10)%45);
                NaturalLog("peek_returned",player.Slot,run.Node.Id,$"checks={run.Checks}");
            }
            return true;
        }
        return false;
    }

    private void TickNatural()
    {
        if(!_naturalEnabled||_naturalPack is null||_naturalStarted<=0) return;
        if(!_setupDone||!string.IsNullOrEmpty(_contractError)||!_roundLive||_resultWritten||InWarmup()||Server.MapName!="de_dust2")
        { StopNatural("round_inactive"); return; }
        try
        {
            if(_naturalNavValid.Count==0)
            {
                if(Server.TickCount>=_naturalNavRetryTick)
                {
                    _naturalNavRetryTick=Server.TickCount+64;
                    RefreshNaturalNav();
                }
                // Until navigation is available, do not suppress movement,
                // aim or jumping: every bot remains entirely on classic AI.
                return;
            }
            var players=AllSlots().ToList();
            foreach(var slot in _clipRuns.Keys.ToArray())
                if(!players.Any(p=>p.Slot==slot)) ReleaseMotionClip(slot,"disconnect");
            foreach(var slot in _cornerRuns.Keys.ToArray())
                if(!players.Any(p=>p.Slot==slot)) ReleaseCorner(slot,"disconnect");
            PruneNaturalThreats();
            EnsureNaturalAssignments(players);
            if(Server.TickCount%8==0) UpdateAssistedTeamIntel(players);
            UpdateNaturalPhases(players);
            foreach(var slot in _naturalRuns.Keys.ToArray()) if(!players.Any(p=>p.Slot==slot)) ReleaseNatural(slot,"disconnect");
            foreach(var slot in _naturalRecoveries.Keys.ToArray()) if(!players.Any(p=>p.Slot==slot)) ReleaseNaturalRecovery(slot,"disconnect");
            foreach(var slot in _naturalJumpBlocks.Keys.ToArray()) if(!players.Any(p=>p.Slot==slot)) ReleaseNaturalJumpBlock(slot);
            foreach(var slot in _naturalLaneAssignments.Keys.ToArray())
                if(!players.Any(p=>p.Slot==slot&&p.PlayerPawn.Value is {Health:>0}))
                { _naturalLaneAssignments.Remove(slot); _naturalLaneLockUntil.Remove(slot); }
            foreach(var slot in _naturalTasks.Keys.ToArray())
                if(!players.Any(p=>p.Slot==slot&&p.PlayerPawn.Value is {Health:>0}))
                { _naturalTasks.Remove(slot); _naturalAssignments.Remove(slot); }

            foreach(var player in players)
            {
                // A player-issued opening plan owns strategic navigation for
                // this side. Never let natural clips/holds fight that command.
                if (TacticalOwnsActor(player.Slot, LiveSide(player)) || NativeRadioOwnsActor(player) || NativeSafetyOwnsActor(player)) continue;
                var cfg=NaturalConfig(player.Slot); var pawn=player.PlayerPawn.Value;
                // BotHider may clear the engine fake-client flag. The signed
                // career roster + native bot body identify eligibility; IsBot
                // and Utilities.GetPlayers() would exclude synthetic players.
                var careerBot=cfg is not null&&!player.HasBeenControlledByPlayerThisRound
                    &&pawn is {IsValid:true,Health:>0}&&pawn.Bot is not null;
                if(!careerBot)
                {
                    ReleaseMotionClip(player.Slot,"ineligible");
                    ReleaseCorner(player.Slot,"ineligible");
                    ReleaseNatural(player.Slot,"ineligible"); ReleaseNaturalRecovery(player.Slot,"ineligible");
                    ReleaseNaturalJumpBlock(player.Slot); continue;
                }
                var bot=pawn!.Bot!; var pos=pawn.AbsOrigin;
                if(pos is null) { ReleaseMotionClip(player.Slot,"position_missing"); ReleaseCorner(player.Slot,"position_missing"); ReleaseNatural(player.Slot,"position_missing"); ReleaseNaturalJumpBlock(player.Slot); continue; }
                if(_naturalJumpBlocks.TryGetValue(player.Slot,out var block)&&block.Pawn!=pawn.EntityHandle.Raw)
                    ReleaseNaturalJumpBlock(player.Slot);
                var side=LiveSide(player);
                NaturalObserveBotInfo(player,bot,players);
                var weapon=pawn.WeaponServices?.ActiveWeapon.Value?.DesignerName??"";
                var combat=bot.IsEnemyVisible||bot.IsAttacking||pawn.FlashDuration>0||weapon.Contains("grenade")
                    ||weapon.Contains("flashbang")||weapon.Contains("molotov")||weapon.Contains("c4");
                if(combat)
                {
                    ReleaseMotionClip(player.Slot,"combat_handoff");
                    EnsureNaturalJumpBlock(player.Slot,pawn.EntityHandle.Raw);
                    ReleaseCorner(player.Slot,"combat_handoff");
                    // Pre-aim is already mirrored into native LookYaw/LookPitch.
                    // Immediate release is safely inside the 150 ms handoff cap.
                    ReleaseNatural(player.Slot,"combat_handoff"); ReleaseNaturalRecovery(player.Slot,"combat_handoff"); continue;
                }
                if(TickMotionClips(player,cfg!,players)) continue;
                EnsureNaturalJumpBlock(player.Slot,pawn.EntityHandle.Raw);
                // The two-keyframe experiment remains readable for old
                // requests, but must not compete with continuous clips.
                if(_clipPack is null&&TickCorners(player,cfg!,players)) continue;
                var pairedCornerRegion=_cornerPack is not null&&InCornerRegion(pawn);
                if(_naturalRuns.TryGetValue(player.Slot,out var run))
                {
                    if(run.Pawn!=pawn.EntityHandle.Raw||pawn.Health<run.Health)
                    { ReleaseNatural(player.Slot,"pawn_changed_or_hurt"); continue; }
                    var urgent=run.Node.Exposures.Select(e=>(e.Lane,Threat:NaturalThreatFor(side,e.Lane)))
                        .Where(x=>x.Threat is not null&&x.Threat.Score>=80)
                        .OrderByDescending(x=>x.Threat!.Score).FirstOrDefault();
                    if(urgent.Threat is not null&&urgent.Lane!=run.Anchor.Lane)
                    { ReleaseNatural(player.Slot,"exposure_changed"); continue; }
                    if(!UpdateNaturalRun(player,run,pos)) ReleaseNatural(player.Slot,"local_action_complete");
                    continue;
                }
                if(_naturalRecoveries.TryGetValue(player.Slot,out var recovery))
                {
                    if(recovery.Pawn!=pawn.EntityHandle.Raw||Server.TickCount-recovery.Tick>=48)
                    { ReleaseNaturalRecovery(player.Slot,"recovery_finished"); continue; }
                    var move=NaturalMotion.Recovery(Server.TickCount-recovery.Tick,recovery.Side);
                    if(NaturalNative.UpdateMove(player.Slot,recovery.Move,move.Forward,move.Left)!=0)
                        ReleaseNaturalRecovery(player.Slot,"recovery_failed");
                    continue;
                }
                var goalFar=MathF.Pow(bot.GoalPosition.X-pos.X,2)+MathF.Pow(bot.GoalPosition.Y-pos.Y,2)>140*140;
                if(!pairedCornerRegion&&bot.IsStuck&&pawn.AbsVelocity.Length2D()<8&&goalFar)
                {
                    _naturalStuckTicks[player.Slot]=_naturalStuckTicks.GetValueOrDefault(player.Slot)+1;
                    if(_naturalStuckTicks[player.Slot]>=48&&_naturalRecoveryCooldown.GetValueOrDefault(player.Slot)<=Server.TickCount)
                    {
                        var move=NaturalNative.StartMove(player.Slot,0,0);
                        if(move>0)
                        {
                            _naturalRecoveries[player.Slot]=new(pawn.EntityHandle.Raw,move,Server.TickCount,
                                (player.Slot+_liveRounds)%2==0?1:-1);
                            _naturalStuckTicks[player.Slot]=0;
                            NaturalLog("recovery_started",player.Slot,state:"unstuck_strafe"); continue;
                        }
                    }
                }
                else _naturalStuckTicks[player.Slot]=0;

                var task=_naturalTasks.GetValueOrDefault(player.Slot);
                var node=NaturalTaskNode(player.Slot);
                if(task is null||node is null) continue;
                node=MoveTaskAwayFromHuman(player,task,node,players,cfg!);
                if(node is null) continue;
                task=_naturalTasks.GetValueOrDefault(player.Slot)!;
                // Native pathfinding owns the long journey. The local
                // controller starts only inside the verified node radius.
                if(!GuideNaturalTask(player,bot,pos,task,node)) continue;
                if(pairedCornerRegion) continue;
                if((Server.TickCount+player.Slot)%4!=0) continue;
                var anchor=SelectNaturalAnchor(player,node,players);
                if(anchor is null) continue;
                StartNaturalControl(player,node,anchor,null,pos,cfg!);
            }
        }
        catch(Exception ex) { StopNatural("exception"); _naturalEnabled=false; NaturalLog("disabled:"+ex.Message); }
    }
}

// ABI 20 is retained: node control needs only scoped aim, movement and button
// ownership. Replay and native combat are intentionally untouched.
internal static class NaturalNative
{
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate int VersionFn();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate int LockFn(int slot,int kind,int arg);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate int SlotKindFn(int slot,int kind);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate long MoveFn(int slot,float forward,float left);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate int UpdateFn(int slot,long token,float forward,float left);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate int CancelFn(int slot,long token);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate long InjectFn(int slot,ulong mask,int duration);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate long StartSuppressFn(int slot,ulong mask);
    internal static LockFn Lock=null!;
    internal static SlotKindFn Unlock=null!,IsLocked=null!;
    internal static MoveFn StartMove=null!;
    internal static UpdateFn UpdateMove=null!;
    internal static CancelFn CancelMove=null!,CancelButtons=null!,CancelSuppression=null!;
    internal static InjectFn Inject=null!;
    internal static StartSuppressFn StartSuppression=null!;
    private static nint _library;
    internal static void Bind(string path)
    {
        if(_library!=0) return;
        var handle=NativeLibrary.Load(path);
        T Get<T>(string name) where T:Delegate
            => Marshal.GetDelegateForFunctionPointer<T>(NativeLibrary.GetExport(handle,"BotController_"+name));
        try
        {
            if(Get<VersionFn>("GetVersion")()!=20) throw new Exception("BotController requires ABI 20");
            Lock=Get<LockFn>("Lock"); Unlock=Get<SlotKindFn>("Unlock"); IsLocked=Get<SlotKindFn>("IsLocked");
            StartMove=Get<MoveFn>("StartUsercmdMovement"); UpdateMove=Get<UpdateFn>("UpdateUsercmdMovement");
            CancelMove=Get<CancelFn>("CancelUsercmdMovement"); CancelButtons=Get<CancelFn>("CancelUsercmdInjection");
            Inject=Get<InjectFn>("InjectUsercmd"); StartSuppression=Get<StartSuppressFn>("StartUsercmdSuppression");
            CancelSuppression=Get<CancelFn>("CancelUsercmdSuppression"); _library=handle;
        }
        catch { NativeLibrary.Free(handle); throw; }
    }
}
