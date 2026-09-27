using System.Text.Json;
using CareerMatch;

internal static class ClipRegression
{
    internal static void Run()
    {
        void Check(bool condition,string message) {if(!condition) throw new Exception("clip: "+message);}
        void Near(float a,float b,string message)=>Check(Math.Abs(a-b)<.001f,message);
        var frames=Enumerable.Range(0,65).Select(i=>new float[]{i/64f,i*2,0,0,
            i<32?179:-179,2,128,0,0,1,0,0,0}).ToList();
        var clip=new MotionClip {Id="test",Kind="mid_clear",Side="ct",Phase="opening",Direction="north",WeaponId=16,Frames=frames};
        clip.Validate();
        Near(clip.Sample(.5f)[1],64,"chronological positions retained");
        Near(Math.Abs(clip.Sample(31.5f/64)[4]),180,"yaw wraps along short path");
        Near(clip.Sample(.123f)[0],.123f,"sample by seconds, not server frame number");
        var one=clip.Sample(-1); one[1]=99; Near(clip.Frames[0][1],0,"samples cannot mutate data");
        var slow=ClipMotion.Command(0,0,80,0,80,0,0);
        var fast=ClipMotion.Command(0,0,240,0,240,0,0);
        Check(fast.Forward>slow.Forward*2.9f,"speed does not cancel to unit throttle");
        Near(slow.Forward,80/450f,"native command scale is 450");
        var side=ClipMotion.Command(0,0,-240,0,-240,0,-90);
        Near(side.Forward,0,"cross facing mid remains lateral");
        Check(side.Left<0,"correct right strafe");
        var brake=ClipMotion.Command(0,0,0,0,120,0,0);
        Check(brake.Forward<0,"feedback brakes a moving body during recorded pause");
        var cap=ClipMotion.Command(1000,1000,300,300,-300,-300,45);
        Check(cap.Forward*cap.Forward+cap.Left*cap.Left<=1.001,"bounded command magnitude");
        var f=clip.Frames[0];
        Check(ClipMotion.EntryFits(f,0,0,0,128,0,179,2,true,0),"exact source entrance");
        Check(!ClipMotion.EntryFits(f,30,0,0,128,0,179,2,true,0),"no free translation");
        Check(!ClipMotion.EntryFits(f,0,0,24,128,0,179,2,true,0),"wrong floor rejected");
        Check(!ClipMotion.EntryFits(f,0,0,0,-128,0,179,2,true,0),"opposite travel rejected");
        Check(!ClipMotion.EntryFits(f,0,0,0,128,0,0,2,true,0),"opposite aim rejected");
        Check(!ClipMotion.EntryFits(f,0,0,0,128,0,179,2,false,0),"airborne entry rejected");
        Check(!ClipMotion.CanJump(false,true,5,0,240),"never jump in place for crossing");
        Check(ClipMotion.CanJump(false,true,5,230,240),"purposeful jump with run-up");
        Check(!ClipMotion.CanJump(true,true,5,230,240),"one pulse per action");
        Check(!ClipMotion.CanJump(false,false,5,230,240),"no second midair jump");
        clip.Frames[10][4]=float.NaN;
        try {clip.Validate(); throw new Exception("invalid clip accepted");} catch(InvalidDataException) { }

        var pack=JsonSerializer.Deserialize<MotionClipPack>(File.ReadAllBytes(Path.Combine(AppContext.BaseDirectory,"de_dust2_clips.json")))!;
        pack.Validate();
        Check(pack.Clips.Any(c=>c.Kind=="mid_cross"),"bundled jump sample");
        foreach(var kind in new[]{"b_clear","mid_clear"}) foreach(var team in new[]{"ct","t"})
            Check(pack.Clips.Any(c=>c.Kind==kind&&c.Side==team),"both sides: "+kind);
        // Same time yields same pose regardless of 64 Hz / 128 Hz iteration.
        var real=pack.Clips[0]; var expected=real.Sample(.5f);
        foreach(var hz in new[]{64,128})
        {
            var result=real.Sample(hz/2f/hz);
            for(var i=0;i<13;i++) Near(expected[i],result[i],"tick-rate independent reference");
        }
        Console.WriteLine($"Motion clip checks passed; {pack.Clips.Count} bundled clips validated. Live engine physics NOT tested.");
    }
}
