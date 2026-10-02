# Public 3D source stage

This tree contains the Python career engine, Godot 3D client, canonical standalone
RTS source and its namespaced client copy. It contains no player save, runtime,
private extension, original Demo, cached account data or previous source snapshot.

Install Python 3.12+ and requirements-desktop.txt for the original desktop build.
The 3D backend uses the Python career source at the root of this tree. Install
Godot 4, set CS2CAREER_GODOT to its executable, and use
work/career3d_redesign/启动样板.cmd. data/career_link.json uses python on PATH
and a project-relative repo_root. Select an explicit Python in that config if
needed. Runtime data is created inside the project's runtime/career directory.
The standalone RTS launcher uses the same Godot environment variable.

Optional image media is separate: put locally prepared assets under media/ at
the source-tree root, with teams/team-media.json, maps/ and skin_art/. Manifest
image paths are relative to their own manifest. Missing media stays a placeholder.
Valve artwork and team trademarks are not licensed as project code. Preparation
scripts and provenance references are included; player image caches are excluded.
ChillRoundF.ttf and fonts/OFL.txt are copied only after pinned SHA256 checks.

Original models can be regenerated with Blender from source/:
1. room_primitives_reference.py exports cozy_room.glb.
2. build_chicken.py exports rookie_chicken.glb and rookie_chicken.blend; copy
   them to assets/player_chicken.glb and assets/chicken_source.blend. The shipped
   player/chicken-source files are identical to these original authoring outputs.
3. build_club.py consumes chicken_source.blend and exports chicken_club.glb.
4. build_grand_arena.py plus small_arena_reference.py create grand_major_arena.blend;
   build_walkable_arena.py consumes it locally and exports major_walk.glb.
Music source is compose_arena_entrance.py; GeneralUser GS rendering attribution
and its original license are retained when the rendered music is included.
Generated soundfont/tools/installer distributions are not copied by this stage.
RTS map rebuilding uses numpy/Pillow plus the explicitly supplied local NAV input;
the nav_export project declares its .NET SDK and ValveResourceFormat dependency.

SOURCE_STAGE_MANIFEST.json records public source hashes and transformations.
Machine Windows home prefixes in text are changed to C:/Users/Public (preserving
the original slash style); credential-like text and private paths in binaries
are rejected. The source inputs themselves are never rewritten. Configuration
and launchers in this stage use portable source settings. Game verification
remains pending; source/isolated tests do not certify a live CS2 match.
