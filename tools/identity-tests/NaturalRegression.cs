using CareerMatch;

internal static class NaturalRegression
{
    public static void Run()
    {
        void Near(float a,float b,string why) { if(Math.Abs(a-b)>.001) throw new Exception(why); }
        // CT travels west while holding a southward sightline: lateral movement,
        // not turning the whole body towards the travel direction.
        var cross=NaturalMotion.Input(-250,0,-90,250);
        Near(cross.Forward,0,"west crossing must strafe while aiming south");
        Near(cross.Left,-1,"west must be right strafe when facing south");
        Near(NaturalMotion.Turn(179,-179,10),-179,"short path across yaw wrap");
        Near(NaturalMotion.Turn(0,90,10),10,"view slew cap");
        var walk=NaturalMotion.Input(130,0,0,130);
        Near(walk.Forward,1,"walk speed must not be scaled down twice");
        foreach(var yaw in new[]{-180f,-90f,0f,90f,179f})
        {
            var input=NaturalMotion.Input(80,-70,yaw,250);
            var r=yaw*MathF.PI/180;
            Near((input.Forward*MathF.Cos(r)-input.Left*MathF.Sin(r))*250,80,"world x preserved");
            Near((input.Forward*MathF.Sin(r)+input.Left*MathF.Cos(r))*250,-70,"world y preserved");
        }
        var cap=NaturalMotion.Input(900,800,30,250);
        Near(cap.Forward*cap.Forward+cap.Left*cap.Left,1,"diagonal normalized");
        Near(NaturalMotion.Curve(-100,-700,-120,-720,-420,.5f,50),-400,"straight demo rebased to live corridor");
        Near(NaturalMotion.Curve(2100,2300,2100,2200,2200,.5f,60),2250,"recorded curve residual retained");
        Near(NaturalMotion.Curve(2100,2300,2100,2200,2500,.5f,60),2260,"extreme snapshot residual is bounded");
        Near(NaturalMotion.SpatialProgress(-100,-700,-400),.5f,"movement phase follows live position");
        Near(NaturalMotion.SpatialProgress(-100,-700,-50),0,"phase cannot run before entry");
        if(NaturalMotion.ShouldJump(true,false,.2f,true)) throw new Exception("jump before route run-up forbidden");
        if(!NaturalMotion.ShouldJump(true,false,.4f,true)) throw new Exception("spatial run-up jump expected");
        if(NaturalMotion.ShouldJump(true,true,.4f,true)) throw new Exception("only one planned jump");
        var back=NaturalMotion.Recovery(5,1); Near(back.Forward,-.65f,"recovery first backs out"); Near(back.Left,.65f,"recovery first sidesteps");
        var retry=NaturalMotion.Recovery(25,1); Near(retry.Forward,.55f,"recovery retries forward"); Near(retry.Left,-.85f,"retry changes lane");
        var eye=new NaturalMotion.Point3(-400,2200,-64);
        var focus=NaturalMotion.ProjectTarget(eye.X,eye.Y,eye.Z,-105,6,1200);
        var recovered=NaturalMotion.AimAt(eye,focus);
        Near(recovered.Yaw,-105,"projected target preserves recorded yaw at same eye");
        Near(recovered.Pitch,6,"projected target preserves recorded pitch at same eye");
        var high=NaturalMotion.AimAt(new NaturalMotion.Point3(0,0,0),new NaturalMotion.Point3(100,0,100));
        Near(high.Yaw,0,"3d aim horizontal direction"); Near(high.Pitch,-45,"higher target requires upward pitch");
        Near(NaturalMotion.MidCrossYaw(0),-162,"learned view begins toward route");
        Near(NaturalMotion.MidCrossYaw(.4f),-103,"learned view checks mid while exposed");
        Near(NaturalMotion.MidCrossYaw(1),-176,"learned view returns towards B");
        Near(NaturalMotion.MidCrossPitch(.4f),3.7f,"learned exposed head-line pitch");
        Near(NaturalMotion.DemoVariation(-100,-80,.25f,12),-97,"demo variation is bounded and weighted");
        var lower=NaturalMotion.HeightPitch(4,50,0,900); if(lower<=4) throw new Exception("higher live eye must look further down");
        var smooth=NaturalMotion.SmoothAngle(0,90,0); if(smooth.Angle<=0 || smooth.Angle>=5) throw new Exception("view starts with bounded acceleration");
        if(smooth.Velocity<=0 || smooth.Velocity>280) throw new Exception("view angular velocity bounded");
        var low=NaturalMotion.Skill(45); var highSkill=NaturalMotion.Skill(100); var middle=NaturalMotion.Skill(72.5f);
        Near(low.ErrorDegrees,2.5f,"45 strength aim error endpoint"); Near(highSkill.ErrorDegrees,.35f,"100 strength aim error endpoint");
        if(low.ReactionTicks!=11||highSkill.ReactionTicks!=4||middle.ErrorDegrees<=highSkill.ErrorDegrees||middle.ErrorDegrees>=low.ErrorDegrees)
            throw new Exception("skill execution quality must improve monotonically");
        var pushes=0; var last=-10; uint policySeed=0xC2C2026;
        for(var round=1;round<=200;round++)
        {
            policySeed=unchecked(policySeed*1664525+1013904223);
            if(!NaturalMotion.CoordinatedPush(policySeed,round,last)) continue;
            if(last==round-1) throw new Exception("coordinated pushes cannot occur in consecutive rounds");
            pushes++; last=round;
        }
        if(pushes is <13 or >19) throw new Exception($"8% coordinated push policy out of range: {pushes}/200");
        if(!NaturalMotion.CanStartCoordinatedPush(true,false,false,2))
            throw new Exception("two deep candidates should activate an authorized quiet-round push");
        if(NaturalMotion.CanStartCoordinatedPush(true,true,false,2)
            ||NaturalMotion.CanStartCoordinatedPush(true,false,true,2)
            ||NaturalMotion.CanStartCoordinatedPush(true,false,false,1))
            throw new Exception("alerts, bomb tasks and solo candidates must cancel coordinated push");
        if(!NaturalMotion.BlocksDeepCtGoal("ct_home","t_home",false,false,false,5,5))
            throw new Exception("ordinary solo CT deep push must be blocked");
        if(NaturalMotion.BlocksDeepCtGoal("ct_home","t_home",true,false,false,5,5))
            throw new Exception("authorized coordinated pair must be allowed when numbers are even");
        if(!NaturalMotion.BlocksDeepCtGoal("contested","t_home",true,false,true,5,3))
            throw new Exception("numbers advantage must prefer holding territory");
        if(NaturalMotion.BlocksDeepCtGoal("ct_home","t_home",false,true,false,2,4))
            throw new Exception("bomb objective must permit retake movement");
        if(NaturalMotion.CanRotate("mid","b","sound",1))
            throw new Exception("one B sound must not pull the mid defender");
        if(NaturalMotion.CanRotate("mid","b","sound",3))
            throw new Exception("multiple listeners must not turn one sound into confirmed enemies");
        if(!NaturalMotion.CanRotate("mid","b","visible",2))
            throw new Exception("two confirmed enemies must permit cross-zone support");
        if(!NaturalMotion.CanRotate("mid","b","bomb",1))
            throw new Exception("confirmed bomb must permit cross-zone support");
        if(NaturalMotion.CanRotate("mid","b","enemy_down",1))
            throw new Exception("one enemy death must not abandon the mid lane");
        if(!NaturalMotion.CanRotate("mid","b","defender_down",1))
            throw new Exception("a fallen site defender must permit support rotation");
        if(!NaturalMotion.ExposureRequiresFallback("mid",new[]{"a_short"}))
            throw new Exception("an uncovered exposed lane must fall back to native AI");
        if(NaturalMotion.ExposureRequiresFallback("mid",new[]{"mid","a_short"}))
            throw new Exception("a supported exposed lane should be held");
        if(NaturalMotion.RoundPhase(10*64,false,5,5,0)!="opening"
            ||NaturalMotion.RoundPhase(25*64,false,5,5,0)!="middle"
            ||NaturalMotion.RoundPhase(10*64,false,5,5,90)!="middle"
            ||NaturalMotion.RoundPhase(10*64,true,5,5,0)!="late"
            ||NaturalMotion.RoundPhase(10*64,false,2,5,0)!="late")
            throw new Exception("opening, middle and late phase transitions must follow round state");
        if(NaturalMotion.AssistedIntelCanRelocate("sound",3)
            ||NaturalMotion.AssistedIntelCanRelocate("firefight",1)
            ||!NaturalMotion.AssistedIntelCanRelocate("visible",2)
            ||!NaturalMotion.AssistedIntelCanRelocate("defender_down",1)
            ||!NaturalMotion.AssistedIntelCanRelocate("bomb",0))
            throw new Exception("assisted area intelligence must remain bounded");
        if(NaturalMotion.CanLockAim(13,20,5)||NaturalMotion.CanLockAim(15,0,8)
            ||NaturalMotion.CanLockAim(10,35,8)||!NaturalMotion.CanLockAim(10,20,6))
            throw new Exception("aim may lock only after verified arrival and settling");
        if(!NaturalMotion.TaskExpired(500,499,500)||!NaturalMotion.TaskExpired(500,900,300)
            ||NaturalMotion.TaskExpired(500,900,350))
            throw new Exception("stalled and deadline task recovery contract");
        var uncovered=NaturalMotion.CoverageScore(60,0,0,0,true,true,false,false,false);
        var duplicate=NaturalMotion.CoverageScore(60,0,0,1,true,true,false,false,false);
        if(uncovered<=duplicate) throw new Exception("uncovered critical lanes must win team allocation");
        var lockedLane=NaturalMotion.CoverageScore(60,0,0,0,true,true,true,true,false);
        if(lockedLane<=uncovered) throw new Exception("minimum hold hysteresis must prevent view twitching");
        var peek=NaturalMotion.PeekTarget(new(100,200,12),-24,30);
        Near(peek.X,76,"peek x offset"); Near(peek.Y,230,"peek y offset"); Near(peek.Z,12,"peek keeps terrain height");
        Console.WriteLine("Natural motion checks passed (3D head-line, phases, tasks, bounded shared intel, arrival lock, coverage and skill interpolation).");
    }
}
