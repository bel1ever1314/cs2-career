"""Create a separate playable venue asset; leave the original .blend intact.

The model was a presentation cutaway: solid seating terraces crossed the
front door. Carve an actual central ground-level vomitory, then line its
open cut faces with tunnel walls and roof. Blender Z up, negative Y front.
"""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/grand_major_arena.blend'))
report = []
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH' and not obj.name.startswith('Crowd'):
        points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        lo = [min(p[i] for p in points) for i in range(3)]
        hi = [max(p[i] for p in points) for i in range(3)]
        if any(s in obj.name.lower() for s in ['floor','terrace','ring','rail','stair','platform','step','turnstile','runway']):
            report.append({'name':obj.name,'min':lo,'max':hi})

bpy.ops.mesh.primitive_cube_add(size=1, location=(0,-34,2.52))
cutter = bpy.context.object
cutter.name = 'Temporary entry opening cutter'
cutter.dimensions = (6.0,35.0,4.6) # bottom .22, above public floor; opens the structural wall
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
changed=[]
for obj in list(bpy.context.scene.objects):
    if obj == cutter or obj.type != 'MESH': continue
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    intersects = lo[0]<3 and hi[0]>-3 and lo[1]<-16.5 and hi[1]>-51.5 and lo[2]<4.82 and hi[2]>.22
    if not intersects: continue
    name=obj.name.lower()
    structural=any(s in name for s in ['terrace','circulation ring','outside rail','safety rail','public stair','entry bay','timber fin'])
    if structural:
        bpy.context.view_layer.objects.active=obj
        modifier=obj.modifiers.new('Walkable central entry','BOOLEAN')
        modifier.operation='DIFFERENCE'
        modifier.solver='EXACT'
        modifier.object=cutter
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        changed.append(obj.name)
    elif name.startswith('crowd') and hi[2]<4.82:
        bpy.data.objects.remove(obj,do_unlink=True)
bpy.data.objects.remove(cutter,do_unlink=True)

def material(name,color):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    return mat

navy=material('Tunnel navy',(0.06,.12,.16))
cream=material('Tunnel warm stone',(.72,.77,.72))
gold=material('Tunnel amber',(.94,.61,.22))
def box(name,position,size,mat):
    bpy.ops.mesh.primitive_cube_add(size=1,location=position)
    obj=bpy.context.object;obj.name=name;obj.dimensions=size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj

box('Walk tunnel floor',(0,-34.2,.34),(5.7,32.4,.26),navy)
for side in [-1,1]:
    box('Walk tunnel lining', (side*2.88,-34.2,2.38),(.24,32.4,3.85),cream)
    box('Walk tunnel guide strip',(side*2.737,-34.2,1.25),(.022,32.4,.10),gold)
box('Walk tunnel ceiling',(0,-34.2,4.40),(5.9,32.4,.2),navy)

# Front hall central turnstile: keep the side lanes, open a signed 2.2 m
# walking lane instead of making the controller ghost through a gate.
for obj in list(bpy.context.scene.objects):
    if obj.name.startswith(('Entry turnstile','Turnstile arm')) and abs(obj.location.x)<1.5:
        bpy.data.objects.remove(obj,do_unlink=True)

bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.scene.objects:
    if obj.type in {'MESH','FONT','EMPTY'}:obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets/major_walk.glb'),export_format='GLB',use_selection=True,export_apply=True,export_cameras=False,export_lights=False,export_animations=False)
(ROOT/'temp/arena_geometry.json').write_text(json.dumps({'changed':changed,'bounds_blender':report},indent=2),encoding='utf-8')
print('WALKABLE_ARENA',len(changed),'structural meshes opened')
