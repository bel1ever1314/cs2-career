namespace CareerMatch;

// Pure geometry used by the live adapter; view and travel are independent.
internal static class NaturalMotion
{
    internal readonly record struct Point3(float X,float Y,float Z);
    internal readonly record struct SkillTuning(float ErrorDegrees,int ReactionTicks);

    internal static float Delta(float from,float to) => (to-from+540)%360-180;

    internal static float Turn(float from, float to, float step)
    {
        var delta = Delta(from,to);
        return (from + Math.Clamp(delta, -step, step) + 540) % 360 - 180;
    }

    internal static (float Forward, float Left) Input(float vx, float vy, float yaw, float speed)
    {
        var rad=yaw*MathF.PI/180;
        var forward=(vx*MathF.Cos(rad)+vy*MathF.Sin(rad))/speed;
        var left=(-vx*MathF.Sin(rad)+vy*MathF.Cos(rad))/speed;
        var scale=Math.Max(1,MathF.Sqrt(forward*forward+left*left));
        return (forward/scale,left/scale);
    }

    // Rebase the shape of a recorded route onto the bot's live entry and a
    // safe live exit. Only the curve residual comes from the recording: the
    // absolute GOTV coordinates are deliberately not replayed.
    internal static float Curve(float liveStart, float liveEnd, float demoStart,
        float demoEnd, float demoNow, float progress, float residualLimit)
    {
        progress=Math.Clamp(progress,0,1);
        var demoLine=demoStart+(demoEnd-demoStart)*progress;
        var residual=Math.Clamp(demoNow-demoLine,-residualLimit,residualLimit);
        return liveStart+(liveEnd-liveStart)*progress+residual;
    }

    internal static float SpatialProgress(float startX,float endX,float currentX)
        => Math.Clamp((startX-currentX)/Math.Max(1,startX-endX),0,1);

    internal static bool ShouldJump(bool jumpStyle,bool alreadyJumped,float progress,bool grounded)
        => jumpStyle && !alreadyJumped && progress is >=.32f and <=.72f && grounded;

    internal static (float Forward,float Left) Recovery(int age,int side)
        => age<18 ? (-.65f,.65f*side) : (.55f,-.85f*side);

    internal static SkillTuning Skill(float strength)
    {
        var q=Math.Clamp((strength-45)/55,0,1);
        return new SkillTuning(2.5f-(2.5f-.35f)*q,(int)MathF.Round(11-(11-4)*q));
    }

    internal static float Unit(uint seed)
    {
        seed^=seed<<13; seed^=seed>>17; seed^=seed<<5;
        return (seed&0xFFFFFF)/16777215f;
    }

    internal static bool CoordinatedPush(uint seed,int round,int lastPush,float chance=.08f)
        => round>0 && lastPush!=round-1 && Unit(seed)<Math.Clamp(chance,0,.25f);

    internal static bool CanStartCoordinatedPush(bool authorized,bool alerted,bool bombPlanted,int deepCandidates)
        => authorized&&!alerted&&!bombPlanted&&deepCandidates>=2;

    internal static bool BlocksDeepCtGoal(string currentTerritory,string goalTerritory,
        bool coordinatedPair,bool bombPlanted,bool localContact,int ctAlive,int tAlive)
    {
        if(goalTerritory!="t_home" || currentTerritory=="t_home" || bombPlanted) return false;
        if(ctAlive>tAlive) return true;
        return !coordinatedPair && !localContact;
    }

    internal static bool CanRotate(string currentZone,string targetZone,string source,int enemyCount,int threshold=2)
        => currentZone==targetZone||currentZone=="unknown"||source is "bomb" or "defender_down"
            ||((source is "visible" or "firefight")&&enemyCount>=Math.Clamp(threshold,2,5));

    internal static int CoverageScore(int basePriority,int threatScore,int enemyCount,int coveredCount,
        bool critical,bool highConfidence,bool current,bool locked,bool urgent)
        => basePriority+threatScore+Math.Min(40,enemyCount*15)
            +(urgent?160:0)+(coveredCount==0?35:-coveredCount*45)
            +(critical?15:0)+(highConfidence?8:0)+(current?(locked?90:25):0);

    internal static bool ExposureRequiresFallback(string urgentLane,IEnumerable<string> supportedLanes)
        => urgentLane.Length>0&&!supportedLanes.Contains(urgentLane,StringComparer.Ordinal);

    internal static string RoundPhase(int elapsedTicks,bool bombPlanted,int ownAlive,int enemyAlive,int pressure,
        int openingTicks=22*64,int lateTicks=75*64)
    {
        if(bombPlanted||ownAlive<=2||enemyAlive<=2||elapsedTicks>=lateTicks) return "late";
        return elapsedTicks>=openingTicks||pressure>=90?"middle":"opening";
    }

    internal static bool AssistedIntelCanRelocate(string source,int confirmedEnemies)
        => source is "bomb" or "defender_down"
            ||(source is "visible" or "firefight" or "assist_region")&&confirmedEnemies>=2;

    internal static bool TaskExpired(int now,int deadline,int lastProgress,int stallTicks=3*64)
        => now>=deadline||now-lastProgress>stallTicks;

    internal static bool CanLockAim(float distance,float speed,int stableTicks,
        float arrivalDistance=14,float arrivalSpeed=28,int requiredStableTicks=6)
        => distance<=arrivalDistance&&speed<arrivalSpeed&&stableTicks>=requiredStableTicks;

    internal static float Distance2(Point3 a,Point3 b)
        => MathF.Pow(a.X-b.X,2)+MathF.Pow(a.Y-b.Y,2)+MathF.Pow(a.Z-b.Z,2);

    internal static Point3 PeekTarget(Point3 origin,float dx,float dy)
        => new(origin.X+dx,origin.Y+dy,origin.Z);

    // Reconstruct a point along the view ray recorded by GOTV. Re-aiming at
    // this world point from the live eye position naturally accounts for X/Y,
    // terrain Z and stance eye-height differences.
    internal static Point3 ProjectTarget(float x,float y,float z,float yaw,float pitch,float distance)
    {
        var yr=yaw*MathF.PI/180; var pr=pitch*MathF.PI/180;
        var flat=MathF.Cos(pr)*distance;
        return new Point3(x+MathF.Cos(yr)*flat,y+MathF.Sin(yr)*flat,z-MathF.Sin(pr)*distance);
    }

    internal static (float Yaw,float Pitch) AimAt(Point3 eye,Point3 target)
    {
        var dx=target.X-eye.X; var dy=target.Y-eye.Y; var dz=target.Z-eye.Z;
        var horizontal=Math.Max(.001f,MathF.Sqrt(dx*dx+dy*dy));
        return (MathF.Atan2(dy,dx)*180/MathF.PI,-MathF.Atan2(dz,horizontal)*180/MathF.PI);
    }

    internal static float ClampAround(float angle,float center,float limit)
        => Turn(center,angle,limit);

    // Aggregate of the 159 accepted Dust2 samples. Pros start looking towards
    // the route, sweep onto mid while exposed, then return their view towards B.
    internal static float MidCrossYaw(float progress)
    {
        ReadOnlySpan<float> p=[0,.10f,.20f,.30f,.40f,.55f,.70f,.82f,.92f,1];
        ReadOnlySpan<float> y=[-162,-154,-132,-111,-103,-102,-127,-160,-174,-176];
        progress=Math.Clamp(progress,0,1);
        for(var i=1;i<p.Length;i++) if(progress<=p[i])
        {
            var t=(progress-p[i-1])/(p[i]-p[i-1]);
            return Turn(y[i-1],y[i],Math.Abs(Delta(y[i-1],y[i]))*t);
        }
        return y[^1];
    }

    internal static float MidCrossPitch(float progress)
    {
        ReadOnlySpan<float> p=[0,.10f,.20f,.30f,.40f,.55f,.70f,.82f,.92f,1];
        ReadOnlySpan<float> v=[3,3.7f,4.2f,3.8f,3.7f,3.8f,4.2f,3.7f,2.3f,1];
        progress=Math.Clamp(progress,0,1);
        for(var i=1;i<p.Length;i++) if(progress<=p[i])
        {
            var t=(progress-p[i-1])/(p[i]-p[i-1]);
            return v[i-1]+(v[i]-v[i-1])*t;
        }
        return v[^1];
    }

    internal static float DemoVariation(float anchor,float observed,float weight,float limit)
        => Turn(anchor,observed,limit)*weight+anchor*(1-weight);

    internal static float HeightPitch(float basePitch,float liveZ,float demoZ,float distance=900)
        => basePitch+MathF.Atan2(liveZ-demoZ,distance)*180/MathF.PI;

    internal static (float Angle,float Velocity) SmoothAngle(float current,float target,float velocity,
        float maxSpeed=280,float acceleration=1100,float hz=64)
    {
        var delta=Delta(current,target);
        var desired=Math.Clamp(delta*9,-maxSpeed,maxSpeed);
        velocity+=Math.Clamp(desired-velocity,-acceleration/hz,acceleration/hz);
        var step=velocity/hz;
        if (Math.Abs(step)>=Math.Abs(delta)) return (target,0);
        return ((current+step+540)%360-180,velocity);
    }
}
