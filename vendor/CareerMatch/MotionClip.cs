using System.Text.Json.Serialization;

namespace CareerMatch;

// Data-only contract. Coordinates are never translated/rotated or assigned to
// a pawn. Time is seconds; the runtime samples at its actual tick interval.
internal sealed class MotionClipPack
{
    [JsonPropertyName("schema_version")] public int Schema { get; set; }
    [JsonPropertyName("map")] public string Map { get; set; }="";
    [JsonPropertyName("execution")] public string Execution { get; set; }="";
    [JsonPropertyName("frame_columns")] public string[] Columns { get; set; }=[];
    [JsonPropertyName("clips")] public List<MotionClip> Clips { get; set; }=[];

    internal void Validate()
    {
        if(Schema!=1||Map!="de_dust2"||Execution!="trajectory_guidance_live_physics"
            ||!Columns.SequenceEqual(new[]{"t","x","y","z","yaw","pitch","vx","vy","vz","ground","walk","duck","jump"})
            ||Clips.Count is <1 or >512||Clips.Select(c=>c.Id).Distinct().Count()!=Clips.Count)
            throw new InvalidDataException("clip_pack_contract");
        foreach(var clip in Clips) clip.Validate();
    }
}

internal sealed class MotionClip
{
    [JsonPropertyName("id")] public string Id { get; set; }="";
    [JsonPropertyName("kind")] public string Kind { get; set; }="";
    [JsonPropertyName("side")] public string Side { get; set; }="";
    [JsonPropertyName("phase")] public string Phase { get; set; }="";
    [JsonPropertyName("direction")] public string Direction { get; set; }="";
    [JsonPropertyName("weapon_id")] public int WeaponId { get; set; }
    [JsonPropertyName("scoped")] public bool Scoped { get; set; }
    [JsonPropertyName("frames")] public List<float[]> Frames { get; set; }=[];
    public float Duration=>Frames[^1][0];
    public float JumpTime=>Frames.FirstOrDefault(f=>f[12]==1)?[0]??-1;

    internal void Validate()
    {
        if(Id.Length is <1 or >80||Side is not ("ct" or "t")||Phase is not ("opening" or "middle")
            ||Kind is not ("mid_cross" or "b_clear" or "mid_clear")
            ||Direction is not ("west" or "north" or "south")||WeaponId is <1 or >64
            ||Frames.Count is <32 or >385)
            throw new InvalidDataException("clip_metadata:"+Id);
        float previous=-1; float[]? previousFrame=null;
        foreach(var f in Frames)
        {
            if(f.Length!=13||f.Any(v=>!float.IsFinite(v))||f[0]<0||f[0]>6
                ||(previous>=0&&(f[0]<=previous||f[0]-previous>.04f))
                ||f.Skip(1).Take(3).Any(v=>Math.Abs(v)>10000)||Math.Abs(f[4])>360||Math.Abs(f[5])>45
                ||MathF.Sqrt(f[6]*f[6]+f[7]*f[7])>315||Math.Abs(f[8])>350
                ||f[9] is not (0 or 1)||f[10] is not (0 or 1)||f[11] is <0 or >1||f[12] is not (0 or 1))
                throw new InvalidDataException("clip_frame:"+Id);
            previous=f[0];
            if(previousFrame is { } old)
            {
                var dt=f[0]-old[0];
                if(MathF.Sqrt(MathF.Pow(f[1]-old[1],2)+MathF.Pow(f[2]-old[2],2))>315*dt+.05f
                    ||Math.Abs(f[3]-old[3])>350*dt+.05f)
                    throw new InvalidDataException("clip_position_gap:"+Id);
            }
            previousFrame=f;
        }
        if(Frames[0][0]!=0||Frames[0][9]!=1||Frames[^1][9]!=1||Frames.Count(f=>f[12]==1)>1
            ||(Kind=="mid_cross"&&(Side!="ct"||Direction!="west"||JumpTime<.15f||JumpTime>Duration-.15f))
            ||(Kind!="mid_cross"&&Frames.Any(f=>f[9]!=1||f[12]!=0)))
            throw new InvalidDataException("clip_jump_contract:"+Id);
    }

    internal float[] Sample(float seconds)
    {
        if(seconds<=0) return (float[])Frames[0].Clone();
        if(seconds>=Duration) return (float[])Frames[^1].Clone();
        var lo=0; var hi=Frames.Count-1;
        while(hi-lo>1) {var mid=(lo+hi)/2; if(Frames[mid][0]<=seconds) lo=mid; else hi=mid;}
        var a=Frames[lo]; var b=Frames[hi]; var t=(seconds-a[0])/(b[0]-a[0]);
        var result=(float[])a.Clone();
        for(var i=0;i<=8;i++) result[i]=a[i]+(b[i]-a[i])*t;
        result[4]=a[4]+NaturalMotion.Delta(a[4],b[4])*t;
        result[11]=a[11]+(b[11]-a[11])*t;
        return result;
    }
}

internal static class ClipMotion
{
    // CS usercmd has a 450 input scale; this is NOT a fraction of weapon speed.
    // Feed-forward recorded velocity + bounded position/velocity feedback.
    // The engine retains weapon acceleration, friction, collision and gravity.
    internal static (float Forward,float Left) Command(float dx,float dy,float vx,float vy,
        float liveVx,float liveVy,float yaw)
    {
        var x=vx+Math.Clamp(dx*7,-90,90)+Math.Clamp((vx-liveVx)*.7f,-80,80);
        var y=vy+Math.Clamp(dy*7,-90,90)+Math.Clamp((vy-liveVy)*.7f,-80,80);
        return NaturalMotion.Input(x,y,yaw,450);
    }

    internal static bool EntryFits(float[] f,float x,float y,float z,float vx,float vy,
        float yaw,float pitch,bool grounded,float duck)
    {
        var speed=MathF.Sqrt(vx*vx+vy*vy); var reference=MathF.Sqrt(f[6]*f[6]+f[7]*f[7]);
        return grounded&&Math.Abs(duck-f[11])<.2f
            &&MathF.Pow(x-f[1],2)+MathF.Pow(y-f[2],2)<=24*24&&Math.Abs(z-f[3])<=10
            &&Math.Abs(NaturalMotion.Delta(yaw,f[4]))<=40&&Math.Abs(pitch-f[5])<=15
            &&Math.Abs(speed-reference)<=Math.Max(35,reference*.35f)
            &&(reference<35||speed<20||(vx*f[6]+vy*f[7])/(speed*reference)>.75f);
    }

    internal static bool CanJump(bool already,bool grounded,float error,float speed,float reference)
        =>!already&&grounded&&error<=20&&speed>=Math.Max(100,reference*.75f);
}
