using CareerMatch;

internal static class AssistRegression
{
    public static void Run()
    {
        var a = new ActorOwnership();
        int checks = 0;
        void Check(bool value, string label) { checks++; if (!value) throw new Exception(label); }
        // Reduced from observed round-12 hurt/takeover order: bot1 hit twice,
        // bot2 delivered the final hit through the same human controller.
        // The old trace did not log the raw assister; this tests that reported
        // controller case, not recovery of an unlogged official assist.
        a.NewMatch();
        a.Takeover("human", "bot1", 1);
        a.Support("enemy", "human", "bot1");
        a.Support("enemy", "human", "bot1");
        a.Takeover("human", "bot2", 2);
        a.Support("enemy", "human", "bot2");
        var result = a.ResolveAssist("enemy", "human", false, "bot2");
        Check(result.PlayerId == "bot1" && !result.Ambiguous, "killer excluded before ambiguity check");
        Check(result.Candidates.Length == 2, "audit retains both physical actors");
        Check(a.ResolveAssist("enemy", "bot1", false, "bot2").PlayerId == "bot1", "original bot alias finds controlled contribution");
        var awards = new Dictionary<string,int> { ["human"]=0, ["bot1"]=0, ["bot2"]=0 };
        if (result.PlayerId is { } id) awards[id]++;
        Check(awards.Values.Sum() == 1 && awards["bot1"] == 1 && awards["human"] == 0, "one assist only; no human duplicate");

        // Round-14 shape: own body chips enemy, then controlled bot finishes.
        a.NewRound();
        a.Support("enemy", "human", "human");
        a.Takeover("human", "bot1", 1);
        a.Support("enemy", "human", "bot1");
        result = a.ResolveAssist("enemy", "human", false, "bot1");
        Check(result.PlayerId == "human" && !result.Ambiguous, "pre-death human assist stays human");

        a.NewRound();
        a.Support("enemy", "bot1", "bot1");
        a.Takeover("human", "bot1", 1);
        Check(a.ResolveAssist("enemy", "human", false, "other").PlayerId == "bot1", "autonomous bot damage survives controller swap");
        a.Takeover("human", "bot2", 2);
        Check(a.ResolveAssist("enemy", "human", false, "other").PlayerId == "bot1", "first bot evidence retained through second takeover");
        a.Support("enemy", "human", "bot2");
        Check(a.ResolveAssist("enemy", "human", false, "other").Ambiguous, "two actual non-killers still fail closed");
        Check(a.ResolveAssist("unknown", "human", false, "other").Ambiguous, "missing evidence cannot fabricate an assist");
        a.Detach("human");
        Check(a.ResolveAssist("unknown", "human", false, "other").Ambiguous, "disconnect cannot erase ambiguity history");

        a.NewRound();
        a.Takeover("human", "bot1", 1);
        a.Support("enemy", "human", "bot1");
        result = a.ResolveAssist("enemy", "human", false, "bot1");
        Check(result.PlayerId is null && !result.Ambiguous, "killer-only evidence is no assist, not an identity failure");
        a.Support("enemy", "human", "human", true);
        Check(a.ResolveAssist("enemy", "human", true, "bot1").PlayerId == "human", "flash and damage evidence stay separate");
        a.Support("enemy", "human", "bot1", true);
        Check(a.ResolveAssist("enemy", "human", true, "bot1").PlayerId == "human", "flash from killer also excluded");
        a.Support("enemy", "human", "bot2", true);
        Check(a.ResolveAssist("enemy", "human", true, "bot1").Ambiguous, "genuine multiple flash contributors remain rejected");
        Check(a.ResolveAssist("different-enemy", "human", true, "other").Ambiguous, "different victims never share contributions");

        a.NewRound();
        Check(a.ResolveAssist("enemy", "human", false, "other").PlayerId == "human", "new round clears support and alias history");
        Check(a.ResolveAssist("enemy", "human", false, "human").PlayerId is null, "ordinary killer never assists itself");
        a.Support("enemy", "enemy", "enemy");
        Check(a.ResolveAssist("enemy", "enemy", false, "human").PlayerId is null, "victim is never an assister");
        a.NewMatch();
        Check(!a.HadTakeover, "new match clears audit state");
        // Exact damage/takeover sequence from FURIA-Legacy, round 13.
        a.Support("dumau", "human", "human", damage: 46);
        a.Support("dumau", "yuurih", "yuurih", damage: 2);
        a.Takeover("human", "yuurih", 1);
        a.Support("dumau", "human", "yuurih", damage: 26);
        a.Takeover("human", "molodoy", 2);
        a.Support("dumau", "human", "molodoy", damage: 110);
        result = a.ResolveAssist("dumau", "human", false, "molodoy");
        Check(result.PlayerId == "human" && !result.Ambiguous, "actual round 13: 46 beats 28, killer excluded");
        Check(result.Reason == "career_damage_then_reached_first_v1", "custom rule visible in audit");
        a.Support("dumau", "yuurih", "yuurih", damage: 18);
        Check(a.ResolveAssist("dumau", "human", false, "molodoy").PlayerId == "human", "46 tie uses first to reach total");
        a.Support("dumau", "yuurih", "yuurih", damage: 1);
        Check(a.ResolveAssist("dumau", "human", false, "molodoy").PlayerId == "yuurih", "47 beats 46: bot wins without human double count");
        a.NewRound();
        a.Support("enemy", "human", "bot1", damage: 10);
        a.Support("enemy", "human", "human", damage: 20);
        a.Support("enemy", "human", "bot1", damage: 10);
        Check(a.ResolveAssist("enemy", "human", false, "other").PlayerId == "human", "tie uses reaching total, not first hit");
        Console.WriteLine($"{checks} assist attribution checks passed (killer exclusion, aliases, flash, strict ambiguity, reset).");
    }
}
