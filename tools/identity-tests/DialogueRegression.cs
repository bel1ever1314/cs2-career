using CareerMatch;
using System.Text.Json;

internal static class DialogueRegression
{
    public static void Run()
    {
        int checks = 0;
        void Check(bool ok, string label) { if (!ok) throw new Exception(label); checks++; }
        ChatContract Contract() => new() { Version = 1, Enabled = true, Rules = [new() {
            Id = "test:chat", When = "round_end", Text = ["{player}，拿了 {round_kills} 个，比分 {score_for}:{score_against}"],
            Maximum = 10, Cooldown = 1 }] };
        Dictionary<string,string> Context() => new() { ["player"] = "人类", ["round_kills"] = "0", ["score_for"] = "2", ["score_against"] = "1" };
        List<ChatPerson> people = [new("human", "人类", "ct", false), new("bot", "队友", "ct", true), new("enemy", "对手", "t", true)];
        var engine = new MatchDialogue(); var config = Contract();
        Check(MatchDialogue.Valid(config), "valid contract");
        var first = engine.EndRound(config,"nonce",1,"win",Context(),people,"ct");
        Check(first is not null && first.Text.Contains("队友") && first.Text.Contains("0 个"), "original player stats + teammate");
        Check(engine.EndRound(config,"nonce",1,"win",Context(),people,"ct") is null, "duplicate round end");
        Check(engine.EndRound(config,"nonce",2,"loss",Context(),people,"ct") is null, "global cooldown");
        Check(engine.EndRound(config,"nonce",3,"loss",Context(),people,"ct") is not null, "cooldown expires");
        engine.Reset();
        Check(engine.EndRound(config,"nonce",1,"win",Context(),people,"ct") == first, "nonce reproducibility/reset");
        Check(new MatchDialogue().EndRound(config,"nonce",0,"win",Context(),people,"ct") is null, "warmup zero ignored");
        config.Enabled = false;
        Check(new MatchDialogue().EndRound(config,"nonce",1,"win",Context(),people,"ct") is null, "disabled");
        config = Contract(); config.Rules[0].SpeakerId = "missing";
        Check(new MatchDialogue().EndRound(config,"nonce",1,"win",Context(),people,"ct") is null, "missing speaker skipped");
        config = Contract(); config.Rules[0].Speaker = "opponent";
        Check(!MatchDialogue.Valid(config), "opponent cannot talk to team");
        config.Rules[0].Channel = "all";
        Check(new MatchDialogue().EndRound(config,"nonce",1,"win",Context(),people,"ct")!.Text.Contains("对手"), "opponent all chat");
        config = Contract(); config.Rules[0].Speaker = "coach";
        Check(new MatchDialogue().EndRound(config,"nonce",1,"win",Context(),[],"ct")!.Text.Contains("教练"), "coach no fake player");
        config = Contract(); config.Rules[0].Conditions = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>("{\"round_kills\":{\"min\":3}}")!;
        Check(new MatchDialogue().EndRound(config,"nonce",1,"win",Context(),people,"ct") is null, "no bot takeover kills credited as human dialogue");
        var context = Context(); context["round_kills"] = "3";
        Check(new MatchDialogue().EndRound(config,"nonce",1,"win",context,people,"ct") is not null, "multikill condition");
        config = Contract(); config.Rules[0].Probability = double.NaN;
        Check(!MatchDialogue.Valid(config), "NaN rejected");
        config = Contract(); config.Rules[0].Text = ["{player.GetType}"];
        Check(!MatchDialogue.Valid(config), "no object traversal");
        Check(MatchDialogue.Clean("\u0002abc\n\u202edef") == "abcdef", "controls removed");
        Check(System.Text.Encoding.UTF8.GetByteCount(MatchDialogue.Clean(new string('中',300), 280)) <= 280, "UTF8 chat limit");
        config = Contract(); config.Maximum = 1; engine = new();
        engine.EndRound(config,"nonce",1,"win",Context(),people,"ct");
        Check(engine.EndRound(config,"nonce",4,"win",Context(),people,"ct") is null, "match limit");
        var builtin = JsonSerializer.Deserialize<ChatContract>(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"match_chat.json")))!;
        Check(MatchDialogue.Valid(builtin), "shared Python shipped rules validated by C#");
        // Contract v1 tests above intentionally retain legacy behavior.
        ChatContract V2() => new() { Version = 2, Enabled = true, Rules = [
            new() { Id="coach", When="round_end", Speaker="coach", Text=["coach first"], Cooldown=1, Maximum=200 },
            new() { Id="mate", When="round_end", Text=["mate reply"], Cooldown=1, Maximum=200 },
            new() { Id="other-mate", When="round_end", Text=["not another mate"], Cooldown=1, Maximum=200 }
        ] };
        var v2=V2(); engine=new();
        var batch=engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct");
        Check(batch.Lines.Count==2 && !batch.IsScene,"v2 separate coach and player slots");
        Check(batch.Lines[0].Message.RuleId=="coach" && batch.Lines[1].Message.RuleId=="mate","ordinary coach then player");
        Check(batch.Lines[1].AfterSeconds==1.5,"ordinary messages staggered");
        Check(engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").Lines.Count==0,"batch deduplicated");
        Check(engine.EndRoundBatch(v2,"n",2,"win",Context(),people,"ct").Lines.Count==2,"no cross-round global cooldown");
        for(int round=3;round<=9;round++) engine.EndRoundBatch(v2,"n",round,"win",Context(),people,"ct");
        Check(engine.EndRoundBatch(v2,"n",10,"win",Context(),people,"ct").Lines.Count==2,"no eight-message global cap");
        v2.Rules[0].Cooldown=3; engine=new();
        engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct");
        Check(engine.EndRoundBatch(v2,"n",2,"win",Context(),people,"ct").Lines.Single().Message.RuleId=="mate","per-rule cooldown independent");
        v2=V2();v2.Rules[0].Maximum=1;engine=new();
        engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct");
        Check(engine.EndRoundBatch(v2,"n",2,"win",Context(),people,"ct").Lines.Single().Message.RuleId=="mate","per-rule count independent");
        v2=V2();v2.Rules[2].Id="aaa"; engine=new();
        Check(engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").Lines[1].Message.RuleId=="mate","tie uses authored order not ID");
        v2.Rules[2].Priority=1;engine=new();
        Check(engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").Lines[1].Message.RuleId=="aaa","priority within player slot");
        v2.Rules[2].Speaker="opponent";v2.Rules[2].Channel="all";engine=new();
        Check(engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").Lines.Count==2,"opponent shares player slot");
        ChatScene Scene(string id="scene") => new() {Id=id,When="round_end",Priority=-100,Cooldown=1,Maximum=1,Sequence=[
            new(){Speaker="coach",Text="first"},new(){Speaker="teammate",Text="second",Delay=1},
            new(){Speaker="coach",Text="third",Delay=2}]};
        v2=V2();v2.Scenes=[Scene()];engine=new();
        batch=engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct");
        Check(batch.IsScene && batch.Lines.Count==3,"scene ignores ordinary quota and outranks all ordinary priority");
        Check(batch.Lines[0].Message.Text.Contains("first") && batch.Lines[1].Message.Text.Contains("second") && batch.Lines[2].Message.Text.Contains("third"),"authored sequence preserved");
        Check(batch.Lines.Select(x=>x.AfterSeconds).SequenceEqual(new double[]{0,1,3}),"scene cumulative delays");
        Check(!engine.EndRoundBatch(v2,"n",2,"win",Context(),people,"ct").IsScene,"scene consumed once then normal chat resumes");
        v2.Scenes=[Scene("z-first"),Scene("a-second")];engine=new();
        Check(engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").Lines[0].Message.RuleId=="z-first","scene same priority authored order");
        Check(engine.EndRoundBatch(v2,"n",2,"win",Context(),people,"ct").Lines[0].Message.RuleId=="a-second","unselected scene not consumed");
        v2.Scenes[1].Priority=1;engine=new();
        Check(engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").Lines[0].Message.RuleId=="a-second","scene numeric priority");
        v2.Scenes=[Scene()];v2.Scenes[0].Sequence[1].SpeakerId="missing";engine=new();
        Check(!engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").IsScene,"missing cast skips entire scene and falls back");
        v2.Scenes=[Scene()];v2.Scenes[0].Probability=0;engine=new();
        Check(!engine.EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").IsScene,"zero chance scene suppressed");
        v2.Scenes=[Scene()];v2.Scenes[0].Sequence[0].Text="snapshot {kills}";
        var snap=Context();snap["kills"]="13";engine=new();batch=engine.EndRoundBatch(v2,"n",1,"win",snap,people,"ct");snap["kills"]="26";
        Check(batch.Lines[0].Message.Text.Contains("13"),"scene stats frozen at trigger");
        Check(new MatchDialogue().EndRoundBatch(v2,"n",1,"win",new Dictionary<string,string>(Context()){["kills"]="13"},people,"ct").Lines.SequenceEqual(batch.Lines),"batch deterministic replay");
        v2.Scenes[0].Sequence[0].Delay=double.NaN;Check(!MatchDialogue.Valid(v2),"NaN scene delay rejected");
        v2.Scenes=[Scene()];v2.Scenes[0].Sequence[0].Delay=4;Check(!MatchDialogue.Valid(v2),"excess scene delay rejected");
        v2.Scenes=[Scene()];v2.Scenes[0].Sequence=[];Check(!MatchDialogue.Valid(v2),"empty scene rejected");
        v2.Scenes=[Scene("coach")];Check(!MatchDialogue.Valid(v2),"scene rule duplicate id rejected");
        v2.Scenes=[Scene()];v2.Enabled=false;Check(new MatchDialogue().EndRoundBatch(v2,"n",1,"win",Context(),people,"ct").Lines.Count==0,"disabled suppresses scene");
        var playback=new DialoguePlayback();var epoch=playback.Begin();
        Check(playback.Take(epoch,0),"playback first line");
        Check(!playback.Take(epoch,0) && !playback.Take(epoch,2),"duplicate and out-of-order timer rejected");
        Check(playback.Take(epoch,1),"ordered timer accepted");
        playback.Cancel();Check(!playback.Take(epoch,2),"freeze end/restart cancels remaining lines");
        var newer=playback.Begin();Check(!playback.Take(epoch,0) && playback.Take(newer,0),"same-nonce new session invalidates old timer");
        var example=JsonSerializer.Deserialize<ChatContract>(File.ReadAllText(Path.Combine(AppContext.BaseDirectory,"match_scene_example.json")))!;
        example.Version=2;example.Enabled=true;Check(MatchDialogue.Valid(example),"shipped scene pack accepted by C#");
        engine=new();Check(engine.EndRoundBatch(example,"demo",1,"win",Context(),people,"ct").Lines.Count==2,"shipped round-one dual lane demo");
        Check(engine.EndRoundBatch(example,"demo",3,"loss",Context(),people,"ct").IsScene,"shipped round-three scene demo");
        Console.WriteLine($"{checks} dialogue checks passed.");
    }
}
