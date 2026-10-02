using System.Numerics;
using System.Security.Cryptography;
using System.Text.Json;
using ValveResourceFormat;
using ValveResourceFormat.NavMesh;
using ValveResourceFormat.ResourceTypes;

// Pure offline exporter: reads extracted map resources, never contacts a game.
if (args.Length == 3 && args[0] == "--model") {
    using var modelResource = new Resource();
    modelResource.Read(args[1]);
    if (modelResource.DataBlock is not Model model) throw new InvalidDataException("Not a model.");
    using var dest = new FileStream(args[2], FileMode.CreateNew, FileAccess.Write);
    JsonSerializer.Serialize(dest, new { ModelData = model.KeyValues.ToString(), PhysicsData = model.GetEmbeddedPhys()?.ToString() });
    return;
}
if (args.Length != 4) throw new ArgumentException("map nav-file entity-file output-json");
string map = args[0], navPath = Path.GetFullPath(args[1]), entityPath = Path.GetFullPath(args[2]), output = Path.GetFullPath(args[3]);
if (File.Exists(output)) throw new IOException("Output exists; choose a new artifact.");
var nav = new NavMeshFile();
using (var stream = File.OpenRead(navPath)) {
    nav.Read(stream);
    if (stream.Position != stream.Length) throw new InvalidDataException("NAV not fully consumed.");
}
if (nav.Areas.Count is 0 or > 100000) throw new InvalidDataException("Invalid area count.");
object Point(Vector3 p) => new { X = p.X, Y = p.Y, Z = p.Z };
var areas = nav.Areas.Values.OrderBy(a => a.AreaId).Select(a => {
    if (a.Corners.Length < 3 || a.Corners.Any(p => !float.IsFinite(p.X) || !float.IsFinite(p.Y) || !float.IsFinite(p.Z)))
        throw new InvalidDataException("Invalid NAV polygon.");
    return new { Id = a.AreaId, Region = "Unknown", Corners = a.Corners.Select(Point).ToArray(),
        HullIndex = a.HullIndex, AttributeFlags = a.AttributeFlags.ToString(), MovableMeshId = a.MovableMeshId,
        LaddersAbove = a.LaddersAbove, LaddersBelow = a.LaddersBelow };
}).ToArray();
var links = new List<object>();
foreach (var area in nav.Areas.Values.OrderBy(a => a.AreaId)) {
    foreach (var edge in area.Connections.Select((targets, index) => (targets, index))) {
        foreach (var target in edge.targets) {
            if (!nav.Areas.TryGetValue(target.AreaId, out var dest) || target.EdgeId >= dest.Corners.Length)
                throw new InvalidDataException($"Unresolved connection {area.AreaId}->{target.AreaId}");
            links.Add(new { From = area.AreaId, To = target.AreaId, SourceEdge = edge.index, TargetEdge = target.EdgeId,
                Kind = "unclassified_nav_connection" });
        }
    }
}
string entityDump = "";
object? entityDiagnostics = null;
if (File.Exists(entityPath)) {
    using var resource = new Resource();
    resource.Read(entityPath);
    if (resource.DataBlock is not EntityLump lump) throw new InvalidDataException("Not an entity lump.");
    entityDump = lump.ToEntityDumpString();
    var entities = lump.GetEntities();
    entityDiagnostics = new { Count = entities.Count, ChildEntityNames = lump.GetChildEntityNames(),
        Source = "default_ents.vents_c" };
}
var result = new {
    SchemaVersion = 1, Map = map, CoordinateSystem = "CS2 world XYZ, Z up, Hammer units",
    NavSha256 = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(navPath))).ToLowerInvariant(),
    Parser = typeof(NavMeshFile).Assembly.FullName, NavVersion = nav.Version, NavSubVersion = nav.SubVersion,
    IsAnalyzed = nav.IsAnalyzed, FullyConsumed = true, Areas = areas, Links = links,
    Ladders = nav.Ladders, GenerationParams = nav.GenerationParams,
    MovableMeshIds = nav.MovableMeshIds, TransformedBounds = nav.TransformedBounds,
    RegionEvidence = "NAV format exposes no area place name; Unknown is intentionally retained",
    EntityDump = entityDump, EntityDiagnostics = entityDiagnostics,
    BodyClearanceVerified = false, CollisionGeometry = false,
    SourceConstraint = "Local Valve map resources; private local use; NAV is not collision/LOS geometry"
};
Directory.CreateDirectory(Path.GetDirectoryName(output)!);
using (var stream = new FileStream(output, FileMode.CreateNew, FileAccess.Write))
    JsonSerializer.Serialize(stream, result, new JsonSerializerOptions { WriteIndented = true, IncludeFields = true });
Console.WriteLine($"{map}: NAV {nav.Version}.{nav.SubVersion}, {areas.Length} areas, {links.Count} links, EOF verified");
