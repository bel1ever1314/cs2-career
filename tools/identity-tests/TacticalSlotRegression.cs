using System.Text.Json;
using CareerMatch;
using CareerTactics;

internal static class TacticalSlotRegression
{
    public static void Run()
    {
        var checks = 0;
        void Check(bool okay, string label) { checks++; if (!okay) throw new Exception(label); }
        CustomTactic Tactic() => new() { Id = "double", Name = "双狙", Side = "ct", Assignment = "ability", HumanSlot = 3,
            Slots = Enumerable.Range(1,5).Select(i => new CustomTacticSlot { Slot = i,
                Duty = i is 1 or 2 ? "awp" : i == 4 ? "entry" : "rifle",
                Steps = [new() { Position = [0,0], Wait = 0, LookAt = null }] }).ToList() };
        string[] roster = ["human", "star", "second", "entry", "rifle"];
        TacticalRosterMember[] members = [
            new("star","awp",new Dictionary<string,float>{{"awp",99},{"entry",75},{"rifle",90}}),
            new("second","rifle",new Dictionary<string,float>{{"awp",94},{"entry",74},{"rifle",88}}),
            new("entry","entry",new Dictionary<string,float>{{"awp",65},{"entry",98},{"rifle",80}}),
            new("rifle","rifle",new Dictionary<string,float>{{"awp",66},{"entry",80},{"rifle",98}})];
        var tactic = Tactic();
        var binding = TacticalSlotAssignment.Assign(tactic, roster, "human", members);
        Check(binding[2].PlayerId == "human", "human selected slot3 remains manual");
        Check(binding.Where(b => b.Route.Duty == "awp").Select(b => b.PlayerId).ToHashSet().SetEquals(["star","second"]),
            "repeated AWP assigned top2 fits without requiring two career snipers");
        Check(binding[3].PlayerId == "entry" && binding[4].PlayerId == "rifle", "global one-to-one best-fit");
        Check(binding.Select(b => b.PlayerId).Distinct().Count() == 5, "never duplicate a player");
        for (var i=0;i<100;i++) Check(TacticalSlotAssignment.Assign(tactic, roster.Reverse().ToArray(), "human", members.Reverse().ToArray())
            .Select(b=>b.PlayerId).SequenceEqual(binding.Select(b=>b.PlayerId)), "ability tie ordering reproducible despite entity/order change");
        var candidates = roster.Select(id=>new TacticalBotCandidate(id,"ct",true,true,true)).ToArray();
        var alive = TacticalRosterSlots.Bind(tactic, roster, "human", candidates,"ct", members);
        var dead = TacticalRosterSlots.Bind(tactic, roster, "human", candidates.Select(c=>c.Id=="star"?c with{Alive=false}:c),"ct",members);
        Check(dead.All(b=>b.PlayerId!="star") && dead.All(b=>alive.Single(a=>a.PlayerId==b.PlayerId).TacticSlot==b.TacticSlot), "death does not remap");
        var taken = TacticalRosterSlots.Bind(tactic, roster,"human",candidates.Select(c=>c.Id=="entry"?c with{HumanControlled=true}:c),"ct",members);
        Check(taken.All(b=>b.PlayerId!="entry") && taken.All(b=>alive.Single(a=>a.PlayerId==b.PlayerId).TacticSlot==b.TacticSlot),"takeover does not remap");
        tactic.Assignment="roster"; tactic.HumanSlot=1;
        Check(TacticalSlotAssignment.Assign(tactic,roster,"human",members).Select(b=>b.PlayerId).SequenceEqual(roster),"legacy order even with ability metadata");
        tactic=Tactic();
        Check(TacticalSlotAssignment.Assign(tactic,roster,"human").Count==5,"old request fallback does not require all roles");
        var invalid = false;
        try { var t=Tactic(); t.Assignment="roster"; TacticalSlotAssignment.Assign(t,roster,"human",members); } catch(InvalidDataException){invalid=true;}
        Check(invalid,"roster cannot move human from slot1");
        var playbook=new TacticalPlaybook { Version=1, Map="de_dust2", Tactics=[Tactic()] };
        var json=JsonSerializer.Serialize(playbook);
        Check(TacticalPlaybook.Parse(json).Tactics[0].Slots.Count(s=>s.Duty=="awp")==2,"strict import allows repeat duties");
        foreach(var source in new[]{json.Replace("\"duty\":\"awp\"","\"duty\":\"sniper\""),json.Replace("\"assignment\":\"ability\"","\"assignment\":null"),json.Replace("\"human_slot\":3","\"human_slot\":6")})
        { invalid=false;try{TacticalPlaybook.Parse(source);}catch(Exception){invalid=true;}Check(invalid,"invalid optional slot contract rejected"); }
        var plan=new TacticalBuyPlan { Nonce="match",Map="de_dust2",Round=12,Side="t",Duties=new(){{11,"awp"},{12,"awp"},{13,"rifle"},{14,"entry"}}};
        var live=new Dictionary<ulong,string>{{11,"t"},{12,"t"},{13,"t"},{14,"t"}};
        Check(TacticalBuyPlan.Parse(JsonSerializer.Serialize(plan)).Matches("match","de_dust2",12,true,true,live),"halftime uses live team side");
        Check(!plan.Matches("other","de_dust2",12,true,true,live)&&!plan.Matches("match","de_nuke",12,true,true,live)
            &&!plan.Matches("match","de_dust2",13,true,true,live)&&!plan.Matches("match","de_dust2",12,true,false,live),"session,map,round,freeze gates");
        Check(!plan.Matches("match","de_dust2",12,true,true,new Dictionary<ulong,string>{{11,"ct"}}),"wrong side or missing identity rejected");
        foreach(var source in new[]{JsonSerializer.Serialize(plan).Replace("\"11\":\"awp\"","\"11\":\"awp\",\"11\":\"rifle\""),JsonSerializer.Serialize(plan).Replace("\"round\":12","\"round\":12,\"script\":\"x\"")})
        {invalid=false;try{TacticalBuyPlan.Parse(source);}catch(Exception){invalid=true;}Check(invalid,"duplicate/unknown bridge data rejected");}
        Console.WriteLine($"PASS tactical slot assignment: {checks} assertions (no live match simulated).");
    }
}
