namespace CareerMatch;

internal static class TacticalWaypointPolicy
{
    // A zero-wait intermediate waypoint is a transit boundary, not a release
    // of the route. The last waypoint and completed positional waits still
    // hand movement back to native AI through the normal release path.
    internal static bool IsTransit(TacticStepAction action, float completedWait)
        => action == TacticStepAction.Advanced && completedWait == 0;

    // An overlapping next point is evaluated by the normal arrival clock on
    // the next tick. Do not manufacture a path failure for an already reached
    // destination, or loop across several points in one tick.
    internal static bool ShouldCheckMovement(int tick, bool transit, bool nextGoalReached = false)
        => (!transit || !nextGoalReached) && (transit || tick % 16 == 0);
}
