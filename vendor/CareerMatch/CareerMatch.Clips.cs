using System.Security.Cryptography;
using System.Text.Json;
using CounterStrikeSharp.API;
using CounterStrikeSharp.API.Core;
using CounterStrikeSharp.API.Modules.Utils;

namespace CareerMatch;

public sealed partial class CareerMatchPlugin
{
    private sealed class ClipRun(MotionClip clip,uint pawn,long move,int tick,int health,string task)
    {
        public MotionClip Clip=clip;
        public uint Pawn=pawn;
        public long Move=move, Suppression, Buttons, Jump;
        public int Started=tick, Health=health, NoProgressTick=tick, ViewMismatchTicks;
        public string Task=task;
        public float Time, LastX, LastY, MaxError, MaxViewError, LastYaw, LastPitch, Forward, Left, Speed, ReferenceSpeed;
        public bool AimLocked, Jumped, SawAir;
        public ulong ButtonMask;
    }
    private MotionClipPack? _clipPack;
    private readonly Dictionary<int,ClipRun> _clipRuns=[];
    private readonly Dictionary<int,int> _clipRearm=[];
    private readonly HashSet<string> _clipUsed=[];
    private readonly Dictionary<string,int> _clipDiagnostics=[];

    private void LoadMotionClips(JsonElement style)
    {
        _clipPack=null;
        if(!style.TryGetProperty("clip_path",out var entry)) return; // old requests remain readable
        var path=entry.GetString()??"";
        if(!File.Exists(path)||new FileInfo(path).Length>8*1024*1024)
            throw new InvalidDataException("motion_clip_missing_or_oversize");
        var bytes=File.ReadAllBytes(path);
        if(!style.TryGetProperty("clip_hash",out var hash)
            ||!Convert.ToHexString(SHA256.HashData(bytes)).Equals(hash.GetString(),StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("motion_clip_hash_mismatch");
        var pack=JsonSerializer.Deserialize<MotionClipPack>(bytes)??throw new InvalidDataException("motion_clip_json");
        pack.Validate(); _clipPack=pack;
        NaturalLog("clip_pack_ready",state:$"clips={pack.Clips.Count};physics=live;geometry_review=pending");
    }

    private void ResetMotionClips()
    {
        foreach(var slot in _clipRuns.Keys.ToArray()) ReleaseMotionClip(slot,"round_reset");
        _clipUsed.Clear(); _clipRearm.Clear(); _clipDiagnostics.Clear();
    }

    private void ReleaseMotionClip(int slot,string reason)
    {
        if(!_clipRuns.Remove(slot,out var run)) return;
        // Each token belongs only to this action. Every exit (including a
        // partially initialized run) attempts all releases, even if one fails.
        try { NaturalNative.CancelMove(slot,run.Move); } catch { }
        try { if(run.Buttons>0) NaturalNative.CancelButtons(slot,run.Buttons); } catch { }
        try { if(run.Jump>0) NaturalNative.CancelButtons(slot,run.Jump); } catch { }
        try { if(run.Suppression>0) NaturalNative.CancelSuppression(slot,run.Suppression); } catch { }
        try { if(run.AimLocked) NaturalNative.Unlock(slot,1); } catch { }
        _clipRearm[slot]=Server.TickCount+NaturalTicks(2500);
        if(_naturalTasks.TryGetValue(slot,out var task))
        {
            task.LastProgressTick=Server.TickCount;
            task.DeadlineTick+=Server.TickCount-run.Started;
            task.BestDistance=float.MaxValue;
        }
        NaturalLog("clip_"+reason,slot,run.Clip.Id,
            $"time={run.Time:F3};max_error={run.MaxError:F1};view_error={run.MaxViewError:F1};jump={run.Jumped};air={run.SawAir};cmd={run.Forward:F2},{run.Left:F2};speed={run.Speed:F1}/{run.ReferenceSpeed:F1}");
    }

    private static int ClipWeapon(CCSPlayerPawn pawn)
    {
        var weapon=pawn.WeaponServices?.ActiveWeapon.Value;
        if(weapon is null) return -1;
        var id=(int)weapon.AttributeManager.Item.ItemDefinitionIndex;
        return id is 42 or 59||id is >=500 and <=526?42:id;
    }

    private bool ClipMatchesTask(MotionClip clip,NaturalTask task,NaturalNode node,Vector pos)
    {
        if(clip.Side!=task.Side||clip.Phase!=task.Phase||_naturalBombPlanted) return false;
        if(clip.Kind=="mid_cross")
            return task.Side=="ct"&&task.Phase=="opening"&&task.Lane is "b_doors" or "b_tunnels"
                &&node.Position[0]<-700;
        if(clip.Kind=="b_clear"&&task.Lane is not ("b_tunnels" or "b_site" or "lower_tunnel" or "b_doors")) return false;
        // A corridor clip must advance the assigned goal, not drag a defender
        // toward an unrelated recorded destination. Closed peeks may stay put.
        var a=clip.Frames[0]; var b=clip.Frames[^1];
        var dx=b[1]-a[1]; var dy=b[2]-a[2];
        var gx=node.Position[0]-pos.X; var gy=node.Position[1]-pos.Y;
        var length=MathF.Sqrt(dx*dx+dy*dy); var goal=MathF.Sqrt(gx*gx+gy*gy);
        if(length>24&&(goal<40||MathF.Sqrt(MathF.Pow(gx-dx,2)+MathF.Pow(gy-dy,2))>goal+24)) return false;
        if(length>24&&goal>40&&dx*gx+dy*gy<length*goal*.4f) return false;
        if(clip.Kind=="b_clear"&&Math.Abs(gy)>60
            &&(clip.Direction=="north")!=(gy>0)) return false;
        return true;
    }

    private static bool ClipOccupied(CCSPlayerController player,float[] f,List<CCSPlayerController> players)
        =>players.Any(p=>p.Slot!=player.Slot&&p.Team==player.Team
            &&p.PlayerPawn.Value is {Health:>0} pawn&&pawn.AbsOrigin is { } pos
            &&Math.Abs(pos.Z-f[3])<62&&MathF.Pow(pos.X-f[1],2)+MathF.Pow(pos.Y-f[2],2)<32*32);

    private void ClipGateLog(int slot,string kind,string reason)
    {
        var key=$"{slot}:{kind}:{reason}";
        if(_clipDiagnostics.GetValueOrDefault(key)>Server.TickCount) return;
        _clipDiagnostics[key]=Server.TickCount+NaturalTicks(12000);
        NaturalLog("clip_not_selected",slot,kind,reason);
    }

    private bool TickMotionClips(CCSPlayerController player,BotConfig cfg,List<CCSPlayerController> players)
    {
        if(_clipPack is null) return false;
        if(_clipRuns.TryGetValue(player.Slot,out var running))
        { UpdateMotionClip(player,running,players); return true; }
        if(_clipRearm.GetValueOrDefault(player.Slot)>Server.TickCount||(Server.TickCount+player.Slot)%2!=0) return false;
        var pawn=player.PlayerPawn.Value!; var pos=pawn.AbsOrigin!;
        var task=_naturalTasks.GetValueOrDefault(player.Slot); var node=NaturalTaskNode(player.Slot);
        if(task is null||node is null) return false;
        if(players.Count(p=>p.Team==player.Team&&p.PlayerPawn.Value is {Health:>0})<3
            ||players.Count(p=>p.Team!=player.Team&&p.Team is CsTeam.Terrorist or CsTeam.CounterTerrorist
                &&p.PlayerPawn.Value is {Health:>0})<3) return false;
        var near=_clipPack.Clips.Where(c=>c.Side==task.Side&&Math.Abs(c.Frames[0][3]-pos.Z)<16
            &&MathF.Pow(c.Frames[0][1]-pos.X,2)+MathF.Pow(c.Frames[0][2]-pos.Y,2)<40*40).ToList();
        if(near.Count==0) return false;
        var weapon=ClipWeapon(pawn);
        var eligible=near.Where(c=>c.WeaponId==weapon&&c.Scoped==pawn.IsScoped
            &&!_clipUsed.Contains($"{cfg.PlayerId}:{c.Id}")&&ClipMatchesTask(c,task,node,pos)).ToList();
        var clip=eligible.Where(c=>ClipMotion.EntryFits(c.Frames[0],pos.X,pos.Y,pos.Z,
            pawn.AbsVelocity.X,pawn.AbsVelocity.Y,pawn.EyeAngles.Y,pawn.EyeAngles.X,(pawn.Flags&1)!=0,
            pawn.MovementServices is { } movement?new CCSPlayer_MovementServices(movement.Handle).DuckAmount:0))
            .OrderBy(c=>MathF.Pow(c.Frames[0][1]-pos.X,2)+MathF.Pow(c.Frames[0][2]-pos.Y,2))
            .ThenBy(c=>NaturalSeed(cfg.PlayerId+":"+c.Id)).FirstOrDefault();
        if(clip is null)
        { ClipGateLog(player.Slot,near[0].Kind,eligible.Count==0?"task_or_weapon":"entry_pose_or_speed"); return false; }
        if(ClipOccupied(player,clip.Sample(.12f),players)) return false;
        ReleaseNatural(player.Slot,"clip_owner"); ReleaseCorner(player.Slot,"clip_owner");
        ReleaseNaturalRecovery(player.Slot,"clip_owner"); ReleaseNaturalJumpBlock(player.Slot);
        if(NaturalNative.IsLocked(player.Slot,0)!=0||NaturalNative.IsLocked(player.Slot,1)!=0) return false;
        var move=NaturalNative.StartMove(player.Slot,0,0);
        if(move<=0) return false;
        var run=new ClipRun(clip,pawn.EntityHandle.Raw,move,Server.TickCount,pawn.Health,task.TargetNodeId)
        {LastX=pos.X,LastY=pos.Y,LastYaw=pawn.EyeAngles.Y,LastPitch=pawn.EyeAngles.X};
        _clipRuns[player.Slot]=run;
        // Lock from the first movement command, not only after arrival.
        if(NaturalNative.Lock(player.Slot,1,0)!=0) {ReleaseMotionClip(player.Slot,"aim_lock_failed"); return true;}
        run.AimLocked=true;
        run.Suppression=NaturalNative.StartSuppression(player.Slot,(1UL<<1)|(1UL<<2)|(1UL<<16));
        if(run.Suppression<=0) {ReleaseMotionClip(player.Slot,"suppression_failed"); return true;}
        _clipUsed.Add($"{cfg.PlayerId}:{clip.Id}");
        NaturalLog("clip_start",player.Slot,clip.Id,$"{clip.Kind}:{clip.Side}:{task.Kind};weapon={weapon};duration={clip.Duration:F2}");
        UpdateMotionClip(player,run,players);
        return true;
    }

    private void UpdateMotionClip(CCSPlayerController player,ClipRun run,List<CCSPlayerController> players)
    {
        var pawn=player.PlayerPawn.Value!; var pos=pawn.AbsOrigin!; var bot=pawn.Bot!;
        var task=_naturalTasks.GetValueOrDefault(player.Slot);
        var dt=Server.TickInterval;
        if(pawn.EntityHandle.Raw!=run.Pawn||pawn.Health<run.Health||task?.TargetNodeId!=run.Task
            ||ClipWeapon(pawn)!=run.Clip.WeaponId||pawn.IsScoped!=run.Clip.Scoped||_naturalBombPlanted
            ||players.Count(p=>p.Team==player.Team&&p.PlayerPawn.Value is {Health:>0})<3
            ||players.Count(p=>p.Team!=player.Team&&p.Team is CsTeam.Terrorist or CsTeam.CounterTerrorist
                &&p.PlayerPawn.Value is {Health:>0})<3)
        {ReleaseMotionClip(player.Slot,"context_changed"); return;}
        if((Server.TickCount-run.Started)*dt>run.Clip.Duration+1.5f)
        {ReleaseMotionClip(player.Slot,"timeout"); return;}
        var f=run.Clip.Sample(run.Time);
        var dx=f[1]-pos.X; var dy=f[2]-pos.Y;
        var error=MathF.Sqrt(dx*dx+dy*dy); run.MaxError=Math.Max(run.MaxError,error);
        var grounded=(pawn.Flags&1)!=0;
        if(!grounded) run.SawAir=true;
        if(error>48||Math.Abs(pos.Z-f[3])>44)
        {ReleaseMotionClip(player.Slot,"trajectory_deviation"); return;}
        var expectedSpeed=MathF.Sqrt(f[6]*f[6]+f[7]*f[7]);
        run.Speed=pawn.AbsVelocity.Length2D(); run.ReferenceSpeed=expectedSpeed;
        if(MathF.Pow(pos.X-run.LastX,2)+MathF.Pow(pos.Y-run.LastY,2)>2*2||expectedSpeed<20)
        {run.LastX=pos.X;run.LastY=pos.Y;run.NoProgressTick=Server.TickCount;}
        if((Server.TickCount-run.NoProgressTick)*dt>.25f&&expectedSpeed>40)
        {ReleaseMotionClip(player.Slot,"blocked"); return;}
        if(ClipOccupied(player,run.Clip.Sample(Math.Min(run.Time+.12f,run.Clip.Duration)),players))
        {ReleaseMotionClip(player.Slot,"teammate_obstruction"); return;}
        // Validate last tick's actual view. A successful Lock call alone does
        // not prove that the optional native angle hook is installed/working.
        if(Server.TickCount>run.Started+2)
        {
            var viewError=Math.Max(Math.Abs(NaturalMotion.Delta(run.LastYaw,pawn.EyeAngles.Y)),Math.Abs(run.LastPitch-pawn.EyeAngles.X));
            run.MaxViewError=Math.Max(run.MaxViewError,viewError);
            run.ViewMismatchTicks=viewError>12?run.ViewMismatchTicks+1:0;
            if(run.ViewMismatchTicks*dt>.08f)
            {ReleaseMotionClip(player.Slot,"view_ownership_lost"); return;}
        }
        // Linear sampling preserves recorded pauses and sharp angle switches;
        // only entry blends briefly to avoid an immediate camera snap.
        var entryBlend=Math.Clamp((Server.TickCount-run.Started)*dt/.10f,0,1);
        var yaw=pawn.EyeAngles.Y+NaturalMotion.Delta(pawn.EyeAngles.Y,f[4])*entryBlend;
        var pitch=pawn.EyeAngles.X+(f[5]-pawn.EyeAngles.X)*entryBlend;
        bot.LookYaw=yaw; bot.LookPitch=pitch;
        pawn.Teleport(null,new QAngle(pitch,yaw,0),null); // ANGLES ONLY, never position/velocity
        run.LastYaw=yaw; run.LastPitch=pitch;
        var mask=(f[10]==1?1UL<<16:0)|(f[11]>.5f?1UL<<2:0);
        if(mask!=run.ButtonMask)
        {
            if(run.Buttons>0) NaturalNative.CancelButtons(player.Slot,run.Buttons);
            run.Buttons=mask==0?0:NaturalNative.Inject(player.Slot,mask,8000); run.ButtonMask=mask;
            if(mask!=0&&run.Buttons<=0) {ReleaseMotionClip(player.Slot,"stance_failed"); return;}
        }
        var jumpAt=run.Clip.JumpTime;
        if(jumpAt>=0&&!run.Jumped&&run.Time+dt>=jumpAt)
        {
            if(!ClipMotion.CanJump(run.Jumped,grounded,error,pawn.AbsVelocity.Length2D(),expectedSpeed))
            {ReleaseMotionClip(player.Slot,"jump_entry_failed"); return;}
            // Suppression runs before explicit injection in ABI20. A short
            // pulse authorizes exactly this jump, not native jump-unsticking.
            run.Jump=NaturalNative.Inject(player.Slot,1UL<<1,Math.Max(20,(int)(dt*2000)));
            if(run.Jump<=0) {ReleaseMotionClip(player.Slot,"jump_input_failed"); return;}
            run.Jumped=true; NaturalLog("clip_jump",player.Slot,run.Clip.Id,$"speed={pawn.AbsVelocity.Length2D():F1};error={error:F1}");
        }
        if(run.Jumped&&!run.SawAir&&run.Time>jumpAt+.15f)
        {ReleaseMotionClip(player.Slot,"jump_no_liftoff"); return;}
        var input=ClipMotion.Command(dx,dy,f[6],f[7],pawn.AbsVelocity.X,pawn.AbsVelocity.Y,yaw);
        run.Forward=input.Forward; run.Left=input.Left;
        if(NaturalNative.UpdateMove(player.Slot,run.Move,input.Forward,input.Left)!=0)
        {ReleaseMotionClip(player.Slot,"input_failed"); return;}
        // A little drift slows the reference, rather than looking around the
        // next corner before the live pawn gets there. Larger drift aborts.
        run.Time=Math.Min(run.Clip.Duration,run.Time+dt*(error>20?.5f:1));
        if(run.Time>=run.Clip.Duration&&error<20&&grounded)
            ReleaseMotionClip(player.Slot,"completed");
    }
}
