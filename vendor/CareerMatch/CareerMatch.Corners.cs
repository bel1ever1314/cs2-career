using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    // Two-site experiment: all positions/targets in an action are paired
    // observations. No legacy averaged peek offsets are used in UpperTunnel.
    private sealed class CornerPack
    {
        [JsonPropertyName("schema_version")] public int Schema { get; set; }
        [JsonPropertyName("map")] public string Map { get; set; }="";
        [JsonPropertyName("settings")] public CornerSettings Settings { get; set; }=new();
        [JsonPropertyName("actions")] public List<CornerAction> Actions { get; set; }=[];
    }
    private sealed class CornerSettings
    {
        [JsonPropertyName("entry_radius")] public float EntryRadius { get; set; }=42;
        [JsonPropertyName("rearm_ms")] public int RearmMs { get; set; }=18000;
        [JsonPropertyName("blocked_ms")] public int BlockedMs { get; set; }=250;
        [JsonPropertyName("recent_clear_ms")] public int RecentClearMs { get; set; }=3500;
        [JsonPropertyName("target_pause_ms")] public int PauseMs { get; set; }=160;
        [JsonPropertyName("alignment_degrees")] public float Alignment { get; set; }=7;
        [JsonPropertyName("footprint_radius")] public float Footprint { get; set; }=15;
        [JsonPropertyName("turn_min_ms")] public int TurnMinMs { get; set; }=70;
        [JsonPropertyName("turn_max_ms")] public int TurnMaxMs { get; set; }=190;
    }
    private sealed class CornerStep
    {
        [JsonPropertyName("position")] public float[] Position { get; set; }=[];
        [JsonPropertyName("target")] public float[] Target { get; set; }=[];
        [JsonPropertyName("lane")] public string Lane { get; set; }="";
    }
    private sealed class CornerAction
    {
        [JsonPropertyName("id")] public string Id { get; set; }="";
        [JsonPropertyName("side")] public string Side { get; set; }="";
        [JsonPropertyName("station")] public string Station { get; set; }="";
        [JsonPropertyName("direction")] public string Direction { get; set; }="";
        [JsonPropertyName("kind")] public string Kind { get; set; }="";
        [JsonPropertyName("start")] public float[] Start { get; set; }=[];
        [JsonPropertyName("return")] public float[] Return { get; set; }=[];
        [JsonPropertyName("lane")] public string Lane { get; set; }="";
        [JsonPropertyName("steps")] public List<CornerStep> Steps { get; set; }=[];
    }
    private sealed class CornerRun(CornerAction action,uint pawn,long move,int health,int tick)
    {
        public CornerAction Action=action;
        public uint Pawn=pawn;
        public long Move=move, Suppression;
        public int Health=health, Started=tick, StateTick=tick, ProgressTick=tick, Step, Stable;
        public string State="approach";
        public bool AimLocked, HoldOnly;
        public float Strength=75;
        public float Best=float.MaxValue, StartYaw, StartPitch;
        public int TurnTicks;
    }
    private CornerPack? _cornerPack;
    private readonly List<CCSNavArea> _cornerNav=[];
    private readonly Dictionary<int,CornerRun> _cornerRuns=[];
    private readonly Dictionary<string,int> _cornerCooldown=[];
    private readonly Dictionary<string,(int Tick,float[] Position)> _cornerObserved=[];
    private readonly Dictionary<int,string> _cornerEntry=[];

    private void LoadCorners(JsonElement style)
    {
        _cornerPack=null; _cornerNav.Clear();
        if(!style.TryGetProperty("corner_path",out var path)) return;
        var file=path.GetString()??"";
        if(!File.Exists(file)||new FileInfo(file).Length>512*1024) throw new Exception("corner_pack_missing_or_oversize");
        var bytes=File.ReadAllBytes(file);
        if(!Convert.ToHexString(SHA256.HashData(bytes)).Equals(style.GetProperty("corner_hash").GetString(),StringComparison.OrdinalIgnoreCase))
            throw new Exception("corner_pack_hash_mismatch");
        var pack=JsonSerializer.Deserialize<CornerPack>(bytes)??throw new Exception("corner_pack_invalid");
        if(pack.Schema!=1||pack.Map!="de_dust2"||pack.Actions.Count is <1 or >128
            ||pack.Actions.Select(a=>a.Id).Distinct().Count()!=pack.Actions.Count)
            throw new Exception("corner_pack_contract_invalid");
        var s=pack.Settings;
        if(!float.IsFinite(s.EntryRadius)||s.EntryRadius is <12 or >48
            ||!float.IsFinite(s.Alignment)||s.Alignment is <2 or >12
            ||!float.IsFinite(s.Footprint)||s.Footprint is <14 or >18
            ||s.RearmMs is <6000 or >60000||s.BlockedMs is <125 or >600
            ||s.RecentClearMs is <500 or >6000||s.PauseMs is <80 or >450
            ||s.TurnMinMs is <50 or >200||s.TurnMaxMs<s.TurnMinMs||s.TurnMaxMs>300)
            throw new Exception("corner_settings_invalid");
        foreach(var a in pack.Actions)
        {
            if(a.Id.Length is <1 or >100||a.Side is not ("ct" or "t")
                ||a.Station is not ("upper_pillar" or "b_exit")||a.Direction is not ("toward_b" or "from_b")
                ||a.Kind is not ("clear" or "shoulder")||!Finite3(a.Start)||!Finite3(a.Return)
                ||!NaturalLanes.Contains(a.Lane)||a.Steps.Count is <1 or >4
                ||a.Steps.Any(p=>!Finite3(p.Position)||!Finite3(p.Target)||!NaturalLanes.Contains(p.Lane)
                    ||CornerDistance(a.Start,p.Position)>60||Math.Abs(a.Start[2]-p.Position[2])>16)
                ||CornerDistance(a.Start,a.Return)>8)
                throw new Exception("corner_action_invalid:"+a.Id);
        }
        _cornerPack=pack;
        NaturalLog("corner_pack_ready",state:$"paired_actions={pack.Actions.Count}");
    }

    private static float CornerDistance(float[] a,float[] b)
        =>MathF.Sqrt(MathF.Pow(a[0]-b[0],2)+MathF.Pow(a[1]-b[1],2));
    private static float[] CornerPoint(Vector p)=>[p.X,p.Y,p.Z];
    private static string CornerKey(string side,CornerAction a)
        =>$"{side}:{a.Station}:{a.Direction}:{a.Lane}:{MathF.Round(a.Start[0]/64)}:{MathF.Round(a.Start[1]/64)}";
    private static bool InCornerRegion(CCSPlayerPawn pawn)=>pawn.LastPlaceName=="UpperTunnel";

    private void ResetCorners()
    {
        foreach(var slot in _cornerRuns.Keys.ToArray()) ReleaseCorner(slot,"round_reset");
        _cornerCooldown.Clear(); _cornerObserved.Clear(); _cornerEntry.Clear();
    }

    private void ReleaseCorner(int slot,string reason)
    {
        if(!_cornerRuns.Remove(slot,out var run)) return;
        try { NaturalNative.CancelMove(slot,run.Move); }
        finally
        {
            // Each owned token gets a release attempt even if another native
            // cancellation fails during immediate player-radio handoff.
            try { if(run.AimLocked) NaturalNative.Unlock(slot,1); }
            finally { if(run.Suppression>0) NaturalNative.CancelSuppression(slot,run.Suppression); }
        }
        _cornerCooldown[$"{slot}:{run.Action.Station}"]=Server.TickCount+NaturalTicks(_cornerPack?.Settings.RearmMs??18000);
        // Time spent observing is not a stalled journey. Resume the original
        // task with a fresh progress window after yielding or completing.
        if(_naturalTasks.TryGetValue(slot,out var task))
        { task.LastProgressTick=Server.TickCount; task.DeadlineTick+=Server.TickCount-run.Started; task.BestDistance=float.MaxValue; }
        NaturalLog("corner_"+reason,slot,run.Action.Id,run.State);
    }

    // A conservative navigation-footprint check, NOT a physics hull trace.
    // The measured-progress watchdog below handles props absent from the nav
    // mesh. Never claim that mesh coverage proves line of sight or cover.
    private bool CornerPathFits(float[] from,float[] to,List<CCSPlayerController> players,int slot)
    {
        if(_cornerPack is null||_cornerNav.Count==0) return false;
        var team=players.FirstOrDefault(p=>p.Slot==slot)?.Team;
        var steps=Math.Max(1,(int)MathF.Ceiling(CornerDistance(from,to)/8));
        var r=_cornerPack.Settings.Footprint;
        for(var i=0;i<=steps;i++)
        {
            var f=i/(float)steps;
            var x=from[0]+(to[0]-from[0])*f; var y=from[1]+(to[1]-from[1])*f;
            var z=from[2]+(to[2]-from[2])*f;
            foreach(var (ox,oy) in new[]{(0f,0f),(r,0f),(-r,0f),(0f,r),(0f,-r),(r,r),(r,-r),(-r,r),(-r,-r)})
            {
                var probe=new Vector(x+ox,y+oy,z);
                if(!_cornerNav.Any(area=>
                {
                    var closest=area.GetClosestPoint(probe);
                    return Math.Abs(closest.Z-z)<=18&&MathF.Pow(closest.X-probe.X,2)+MathF.Pow(closest.Y-probe.Y,2)<=4;
                })) return false;
            }
            if(players.Any(p=>p.Slot!=slot&&p.Team==team&&p.PlayerPawn.Value is {Health:>0} pawn
                &&pawn.AbsOrigin is { } other&&Math.Abs(other.Z-z)<64
                &&MathF.Pow(other.X-x,2)+MathF.Pow(other.Y-y,2)<34*34)) return false;
        }
        return true;
    }

    private bool CornerRecentSafe(CCSPlayerController player,CornerAction a,List<CCSPlayerController> players)
    {
        if(NaturalThreatFor(LiveSide(player),a.Lane) is {Score:>=25}) return false;
        if(!_cornerObserved.TryGetValue(CornerKey(LiveSide(player),a),out var seen)
            ||Server.TickCount-seen.Tick>NaturalTicks(_cornerPack!.Settings.RecentClearMs)) return false;
        return players.Any(p=>p.Slot!=player.Slot&&LiveSide(p)==LiveSide(player)
            &&p.PlayerPawn.Value is {Health:>0} pawn&&pawn.AbsOrigin is { } pos
            &&CornerDistance(seen.Position,CornerPoint(pos))<240);
    }

    private void CornerState(CCSPlayerController player,CornerRun run,string state)
    {
        run.State=state; run.StateTick=run.ProgressTick=Server.TickCount; run.Best=float.MaxValue; run.Stable=0;
        var pawn=player.PlayerPawn.Value!;
        run.StartYaw=pawn.EyeAngles.Y; run.StartPitch=pawn.EyeAngles.X;
        var target=run.Action.Steps[run.Step].Target;
        var desired=NaturalMotion.AimAt(new(pawn.Bot!.EyePosition.X,pawn.Bot.EyePosition.Y,pawn.Bot.EyePosition.Z),
            new(target[0],target[1],target[2]));
        var ms=Math.Clamp(65+Math.Abs(NaturalMotion.Delta(run.StartYaw,desired.Yaw))*1.5f,
            _cornerPack!.Settings.TurnMinMs,_cornerPack.Settings.TurnMaxMs);
        ms=Math.Min(_cornerPack.Settings.TurnMaxMs,ms+(100-run.Strength)*.7f);
        run.TurnTicks=NaturalTicks((int)ms);
        NaturalLog("corner_state",player.Slot,run.Action.Id,state+":"+run.Step);
    }

    private bool CornerMove(CCSPlayerController player,CornerRun run,float[] destination,bool lateral)
    {
        var pawn=player.PlayerPawn.Value!; var pos=pawn.AbsOrigin!;
        var dx=destination[0]-pos.X; var dy=destination[1]-pos.Y;
        var distance=MathF.Sqrt(dx*dx+dy*dy);
        if(distance<5) { NaturalNative.UpdateMove(player.Slot,run.Move,0,0); return true; }
        if(distance+1.5f<run.Best) {run.Best=distance; run.ProgressTick=Server.TickCount;}
        if(Server.TickCount-run.ProgressTick>NaturalTicks(_cornerPack!.Settings.BlockedMs))
        {ReleaseCorner(player.Slot,"blocked"); return false;}
        var input=NaturalMotion.Input(dx/distance,dy/distance,pawn.EyeAngles.Y,1);
        if(lateral&&Math.Abs(input.Forward)>.48f)
        {ReleaseCorner(player.Slot,"angle_mismatch"); return false;}
        // Input is a normalized user command; do not divide by the same speed
        // we just multiplied by (the previous controller canceled its speed).
        var throttle=Math.Clamp(distance/18,.22f,lateral?.95f:.7f);
        if(NaturalNative.UpdateMove(player.Slot,run.Move,input.Forward*throttle,input.Left*throttle)!=0)
            ReleaseCorner(player.Slot,"movement_rejected");
        return false;
    }

    private void TickCornerRun(CCSPlayerController player,CornerRun run,List<CCSPlayerController> players)
    {
        var pawn=player.PlayerPawn.Value!;
        if(run.Pawn!=pawn.EntityHandle.Raw||pawn.Health<run.Health||Server.TickCount-run.Started>5*64)
        {ReleaseCorner(player.Slot,"interrupted"); return;}
        var settings=_cornerPack!.Settings;
        var step=run.Action.Steps[run.Step];
        if(run.AimLocked)
        {
            var eye=pawn.Bot!.EyePosition;
            var aim=NaturalMotion.AimAt(new(eye.X,eye.Y,eye.Z),new(step.Target[0],step.Target[1],step.Target[2]));
            // A finite target switch, followed by a steady world-space hold.
            // No continuously lagging spring and no random camera wobble.
            var progress=Math.Clamp((Server.TickCount-run.StateTick)/(float)Math.Max(1,run.TurnTicks),0,1);
            var blend=progress*progress*(3-2*progress);
            var yaw=run.State=="align"?run.StartYaw+NaturalMotion.Delta(run.StartYaw,aim.Yaw)*blend:aim.Yaw;
            var pitch=run.State=="align"?run.StartPitch+(aim.Pitch-run.StartPitch)*blend:aim.Pitch;
            if(CornerRecentSafe(player,run.Action,players)&&run.State=="align") pitch+=3*(1-blend);
            pawn.Bot.LookYaw=yaw; pawn.Bot.LookPitch=Math.Clamp(pitch,-38,38);
            pawn.Teleport(null,new QAngle(pawn.Bot.LookPitch,yaw,0),null);
        }
        if(run.State=="approach")
        {
            if(!CornerMove(player,run,run.Action.Start,false)) return;
            if(pawn.AbsVelocity.Length2D()>32) return;
            if(NaturalNative.Lock(player.Slot,1,0)!=0) {ReleaseCorner(player.Slot,"aim_rejected"); return;}
            run.AimLocked=true;
            run.Suppression=NaturalNative.StartSuppression(player.Slot,(1UL<<2)|(1UL<<16));
            if(run.Suppression<=0) {ReleaseCorner(player.Slot,"buttons_rejected"); return;}
            CornerState(player,run,"align"); return;
        }
        if(run.State=="align")
        {
            NaturalNative.UpdateMove(player.Slot,run.Move,0,0);
            if(Server.TickCount-run.StateTick<run.TurnTicks) return;
            var eye=pawn.Bot!.EyePosition;
            var aim=NaturalMotion.AimAt(new(eye.X,eye.Y,eye.Z),new(step.Target[0],step.Target[1],step.Target[2]));
            if(Math.Abs(NaturalMotion.Delta(pawn.EyeAngles.Y,aim.Yaw))>settings.Alignment)
            {if(Server.TickCount-run.StateTick>32) ReleaseCorner(player.Slot,"alignment_failed"); return;}
            if(run.HoldOnly) {CornerState(player,run,"guard"); return;}
            var current=CornerPoint(pawn.AbsOrigin!);
            if(!CornerPathFits(current,step.Position,players,player.Slot))
            {ReleaseCorner(player.Slot,"path_occupied"); return;}
            CornerState(player,run,"out"); return;
        }
        if(run.State=="guard")
        {
            NaturalNative.UpdateMove(player.Slot,run.Move,0,0);
            if(Server.TickCount-run.StateTick>64) ReleaseCorner(player.Slot,"guard_finished");
            return;
        }
        if(run.State is "out" or "return")
        {
            var end=run.State=="out"?step.Position:run.Action.Return;
            if(Server.TickCount%8==0&&!CornerPathFits(CornerPoint(pawn.AbsOrigin!),end,players,player.Slot))
            {ReleaseCorner(player.Slot,"path_occupied"); return;}
            if(!CornerMove(player,run,end,true)) return;
            if(run.State=="return") {ReleaseCorner(player.Slot,"returned"); return;}
            CornerState(player,run,"observe"); return;
        }
        if(run.State=="observe")
        {
            NaturalNative.UpdateMove(player.Slot,run.Move,0,0);
            if(pawn.AbsVelocity.Length2D()>30) {run.Stable=0; return;}
            run.Stable++;
            if(run.Stable<NaturalTicks(settings.PauseMs)) return;
            // Fresh observation is deliberately short-lived, conditioned on
            // a living teammate nearby and invalidated by incoming threats.
            _cornerObserved[CornerKey(LiveSide(player),run.Action)]=(Server.TickCount,CornerPoint(pawn.AbsOrigin!));
            if(run.Step+1<run.Action.Steps.Count)
            {run.Step++; CornerState(player,run,"align"); return;}
            if(run.Action.Kind=="shoulder") {CornerState(player,run,"return"); return;}
            ReleaseCorner(player.Slot,"cleared_sequence");
        }
    }

    private bool TickCorners(CCSPlayerController player,BotConfig cfg,List<CCSPlayerController> players)
    {
        if(_cornerPack is null) return false;
        var pawn=player.PlayerPawn.Value!; var pos=pawn.AbsOrigin!;
        if(_cornerRuns.TryGetValue(player.Slot,out var run))
        {TickCornerRun(player,run,players); return true;}
        if(!InCornerRegion(pawn)) {_cornerEntry.Remove(player.Slot); return false;}
        // Prevent the previous generic node controller from competing with a
        // paired action or restarting an unverified averaged peek at a pillar.
        ReleaseNatural(player.Slot,"corner_region");
        if(!_cornerEntry.ContainsKey(player.Slot))
        {
            var heading=pawn.AbsVelocity.Y;
            if(Math.Abs(heading)<20) heading=pawn.Bot!.GoalPosition.Y-pos.Y;
            _cornerEntry[player.Slot]=heading>=0?"toward_b":"from_b";
        }
        if((Server.TickCount+player.Slot)%8!=0) return false;
        var side=LiveSide(player); var origin=CornerPoint(pos);
        var choices=_cornerPack.Actions.Where(a=>a.Side==side&&a.Direction==_cornerEntry[player.Slot]
            &&CornerDistance(origin,a.Start)<=_cornerPack.Settings.EntryRadius&&Math.Abs(pos.Z-a.Start[2])<16
            &&_cornerCooldown.GetValueOrDefault($"{player.Slot}:{a.Station}")<=Server.TickCount
            &&!_cornerRuns.Values.Any(r=>r.Action.Side==side&&CornerDistance(r.Action.Start,a.Start)<100))
            .OrderBy(a=>CornerDistance(origin,a.Start)).Take(8).ToList();
        var action=choices.OrderBy(a=>
        {
            var hot=NaturalThreatFor(side,a.Lane) is {Score:>=80};
            var preferred=hot&&cfg.Role!="entry"?"shoulder":"clear";
            return CornerDistance(origin,a.Start)+(a.Kind==preferred?0:12);
        }).FirstOrDefault(a=>CornerPathFits(origin,a.Start,players,player.Slot)
            &&CornerPathFits(a.Start,a.Steps[0].Position,players,player.Slot));
        if(action is null) return false;
        if(CornerRecentSafe(player,action,players))
        {_cornerCooldown[$"{player.Slot}:{action.Station}"]=Server.TickCount+2*64; return false;}
        if(NaturalNative.IsLocked(player.Slot,0)!=0||NaturalNative.IsLocked(player.Slot,1)!=0) return false;
        var move=NaturalNative.StartMove(player.Slot,0,0);
        if(move<=0) return false;
        ReleaseNaturalRecovery(player.Slot,"corner_start");
        _cornerRuns[player.Slot]=new(action,pawn.EntityHandle.Raw,move,pawn.Health,Server.TickCount)
        {
            Step=action.Kind=="shoulder"?action.Steps.Count-1:0,
            Strength=Math.Clamp(cfg.EffectiveStrength,45,100),
            HoldOnly=cfg.Role=="awp"&&NaturalThreatFor(side,action.Lane) is {Score:>=80}
        };
        NaturalLog("corner_started",player.Slot,action.Id,$"{action.Station}:{action.Direction}:{action.Kind}");
        return true;
    }
}
