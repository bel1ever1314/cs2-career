namespace CareerMatch;

internal static class LocalActionMath
{
    internal static float AngleDelta(float from, float to) => ((to - from) % 360 + 540) % 360 - 180;
    internal static (float Yaw, float Pitch) Aim(float eyeX, float eyeY, float eyeZ,
        float targetX, float targetY, float targetZ)
    {
        var dx = targetX - eyeX; var dy = targetY - eyeY; var dz = targetZ - eyeZ;
        return (MathF.Atan2(dy, dx) * 180 / MathF.PI,
            -MathF.Atan2(dz, MathF.Sqrt(dx * dx + dy * dy)) * 180 / MathF.PI);
    }

    internal static (float Forward, float Left) Drive(float dx, float dy,
        float vx, float vy, float yaw, float maxSpeed = 140)
    {
        var distance = MathF.Sqrt(dx * dx + dy * dy);
        // Position error requests a bounded desired velocity. Feedback brakes
        // near the endpoint; 450 is the ABI command scale, not weapon max speed.
        var speed = Math.Min(maxSpeed, distance * 8);
        var wantedX = distance < .001f ? 0 : dx / distance * speed;
        var wantedY = distance < .001f ? 0 : dy / distance * speed;
        var x = wantedX + Math.Clamp((wantedX - vx) * .7f, -80, 80);
        var y = wantedY + Math.Clamp((wantedY - vy) * .7f, -80, 80);
        var radians = yaw * MathF.PI / 180;
        return (Math.Clamp((x * MathF.Cos(radians) + y * MathF.Sin(radians)) / 450, -1, 1),
            Math.Clamp((-x * MathF.Sin(radians) + y * MathF.Cos(radians)) / 450, -1, 1));
    }
}
