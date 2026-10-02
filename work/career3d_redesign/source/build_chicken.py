"""Original toy chicken character; editable geometry, no Valve assets.
Blender Z-up, face toward -Y. Named pivots support simple prototype animation.
"""
import bpy
import math
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene

def rgb(h):
    h=h.lstrip('#')
    def linear(c):return c/12.92 if c<.04045 else ((c+.055)/1.055)**2.4
    return tuple(linear(int(h[i:i+2],16)/255) for i in (0,2,4))

def mat(name,color,rough=.55,metal=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb(color),1);m.use_nodes=True
    b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=m.diffuse_color
    b.inputs['Roughness'].default_value=rough;b.inputs['Metallic'].default_value=metal
    return m

ivory=mat('Warm cream feathers','#FFF1D2');white=mat('Wing feather tips','#FFF8E7')
belly=mat('Soft buttery bib','#FFE4AE');red=mat('Coral red comb','#D96153')
redlight=mat('Comb warm highlight','#E57560');orange=mat('Apricot beak and feet','#EFA147')
darkorange=mat('Beak seam','#BC7037');eye=mat('Espresso eyes','#292D32',.23)
blush=mat('Peach cheek','#F3C1A0');shine=mat('Eye catchlight','#FFFFFF',.2)
navy=mat('Jersey midnight','#2C4556');teal=mat('Jersey sea glass','#70B5A5')
gold=mat('Championship trim','#DDBA72',.4,.25);black=mat('Headset foam','#283339')
stone=mat('Display plinth','#EAE1CF');background=mat('Backdrop sage','#A6BAB4')

def attach(o,name,m):
    o.name=name;o.data.materials.append(m)
    for p in o.data.polygons:p.use_smooth=True
    return o

def egg(name,loc,size,m):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=20,location=loc)
    o=bpy.context.object;o.scale=size
    return attach(o,name,m)

def box(name,loc,size,m,bevel=.03):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    b=o.modifiers.new('Soft corners','BEVEL');b.width=bevel;b.segments=4
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return attach(o,name,m)

def cylinder(name,loc,radius,depth,m):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=radius,depth=depth,location=loc)
    o=bpy.context.object;b=o.modifiers.new('Soft rim','BEVEL');b.width=.025;b.segments=3
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL');return attach(o,name,m)

def curve(name,points,radius,m):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.bevel_depth=radius;c.bevel_resolution=4
    s=c.splines.new('BEZIER');s.bezier_points.add(len(points)-1)
    for p,v in zip(s.bezier_points,points):p.co=v;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    o=bpy.data.objects.new(name,c);scene.collection.objects.link(o);c.materials.append(m);return o

def group(name,loc=(0,0,0),parent=None):
    o=bpy.data.objects.new(name,None);scene.collection.objects.link(o);o.location=loc
    if parent:o.parent=parent
    return o

def reparent(o,parent):
    bpy.context.view_layer.update();world=o.matrix_world.copy();o.parent=parent;o.matrix_world=world
    return o

def label(name,body,loc,size,m):
    c=bpy.data.curves.new(name,'FONT');c.body=body;c.size=size;c.align_x='CENTER';c.align_y='CENTER'
    c.extrude=.0015;c.bevel_depth=.0008
    o=bpy.data.objects.new(name,c);scene.collection.objects.link(o);o.location=loc;o.rotation_euler=(math.pi/2,0,0)
    c.materials.append(m);return o

chicken=group('Chicken')
body=group('BodyPivot',(0,0,1.0),chicken)
head=group('HeadPivot',(0,-.05,1.66),chicken)
baseparts=[]
baseparts.append(egg('Pear shaped body',(0,.045,1.04),(.555,.445,.66),ivory))
baseparts.append(egg('Cream belly bib',(0,-.345,.99),(.402,.143,.43),belly))
for o in baseparts:reparent(o,body)

# Feathered tail, fan rather than a mammal's round tail.
for i in range(3):
    o=egg('Tail feather %d'%i,((i-1)*.145,.438,1.03+(.10 if i==1 else 0)),(.145,.16,.32),white)
    o.rotation_euler.x=-.66;o.rotation_euler.y=(i-1)*.35;reparent(o,body)

for side in (-1,1):
    pivot=group('WingLeftPivot' if side<0 else 'WingRightPivot',(side*.47,.02,1.28),chicken)
    o=egg('Short wing',(side*.517,-.008,1.05),(.175,.32,.36),ivory)
    o.rotation_euler.y=-side*.20;reparent(o,pivot)
    for i in range(3):
        o=egg('Rounded feather tip',(side*(.545+i*.01),-.19+i*.13,.858+i*.03),(.13,.105,.20),white)
        o.rotation_euler.y=-side*.25;reparent(o,pivot)

headparts=[]
headparts.append(egg('Round chicken head',(0,-.09,1.77),(.49,.44,.46),ivory))
# Comb runs front-to-back along the crown, unmistakably chicken even in silhouette.
for i,(y,z,s) in enumerate([(-.17,2.205,.155),(.015,2.25,.19),(.205,2.185,.147)]):
    headparts.append(egg('Comb lobe %d'%i,(0,y,z),(.108,s*.86,s),red if i!=1 else redlight))
for side in (-1,1):
    headparts.append(egg('Eye L' if side<0 else 'Eye R',(side*.214,-.476,1.86),(.064,.041,.083),eye))
    headparts.append(egg('Eye glint',(side*.214-.014,-.511,1.886),(.016,.010,.020),shine))
    headparts.append(egg('Tiny cheek',(side*.324,-.424,1.698),(.075,.024,.040),blush))

# Small tapering upper beak, rounded with subdivision; not a wide duck bill.
verts=[]
for y,z,rx,rz in [(-.466,1.689,.123,.095),(-.57,1.685,.146,.087),(-.70,1.67,.072,.043),(-.754,1.66,.009,.007)]:
    for i in range(12):
        a=2*math.pi*i/12;verts.append((rx*math.cos(a),y,z+rz*math.sin(a)))
faces=[]
for row in range(3):
    for i in range(12):faces.append((row*12+i,row*12+(i+1)%12,(row+1)*12+(i+1)%12,(row+1)*12+i))
faces.extend([tuple(reversed(range(12))),tuple(range(36,48))])
mesh=bpy.data.meshes.new('Upper beak mesh');mesh.from_pydata(verts,[],faces);mesh.update()
o=bpy.data.objects.new('Small tapered beak',mesh);scene.collection.objects.link(o);attach(o,o.name,orange)
o.modifiers.new('Rounded beak','SUBSURF').levels=2;headparts.append(o)
headparts.append(egg('Lower beak',(0,-.57,1.614),(.113,.125,.041),darkorange))
headparts.append(egg('Small chicken wattle',(0,-.432,1.497),(.077,.052,.105),red))
for o in headparts:reparent(o,head)

# Little three-toed feet with broad soft contact patches.
for side in (-1,1):
    pivot=group('FootLeftPivot' if side<0 else 'FootRightPivot',(side*.225,0,.25),chicken)
    reparent(egg('Short shin',(side*.225,.018,.338),(.074,.076,.177),orange),pivot)
    reparent(egg('Foot pad',(side*.225,-.074,.158),(.154,.181,.069),orange),pivot)
    for toe in (-1,0,1):
        o=egg('Chicken toe',(side*.225+toe*.091,-.192+abs(toe)*.026,.146),(.052,.117,.047),orange)
        o.rotation_euler.z=-toe*.24;reparent(o,pivot)

# Optional team uniform and headphones live in a separate group, off by default.
kit=group('PlayerKit',parent=chicken)
kitparts=[]
verts=[]
rings=[]
for j in range(25):
    z=.65+(.78*j/24)
    q=math.sqrt(max(0,1-((z-1.04)/.66)**2))
    rings.append((z,.555*q+.023,.445*q+.028))
for z,rx,ry in rings:
    for i in range(48):
        a=2*math.pi*i/48;verts.append((rx*math.cos(a),.045+ry*math.sin(a),z))
faces=[]
for r in range(len(rings)-1):
    for i in range(48):faces.append((r*48+i,r*48+(i+1)%48,(r+1)*48+(i+1)%48,(r+1)*48+i))
mesh=bpy.data.meshes.new('Jersey shell mesh');mesh.from_pydata(verts,[],faces);mesh.update()
o=bpy.data.objects.new('Sleeveless team jersey',mesh);scene.collection.objects.link(o);attach(o,o.name,navy)
o.modifiers.new('Jersey thickness','SOLIDIFY').thickness=.012;kitparts.append(o)
for z,rx,ry in [(1.429,.471,.388),(.654,.474,.390)]:
    kitparts.append(curve('Jersey teal trim',[(rx*math.cos(a),.045+ry*math.sin(a),z) for a in [2*math.pi*i/64 for i in range(65)]],.016,teal))
kitparts.append(label('Player jersey number','01',(0,-.444,1.00),.22,white))
kitparts.append(label('Jersey team label','CAREER',(0,-.416,1.24),.071,teal))
kitparts.append(curve('Headphone band',[(.56*math.cos(a),.04+.35*math.sin(a),1.84+.43*math.sin(a)) for a in [math.pi*i/24 for i in range(25)]],.036,black))
for side in (-1,1):
    kitparts.append(egg('Headphone cushion',(side*.474,-.02,1.82),(.077,.159,.182),black))
    kitparts.append(egg('Headphone ear shell',(side*.538,-.02,1.82),(.054,.142,.165),teal))
kitparts.append(curve('Headset boom mic',[(-.562,-.13,1.73),(-.56,-.37,1.62),(-.29,-.56,1.58)],.018,black))
kitparts.append(egg('Microphone foam',(-.285,-.561,1.58),(.05,.034,.028),black))
for o in kitparts:reparent(o,kit);o.hide_render=True

# Showcase furniture is a separate asset group and can be removed in a game.
stand=group('DisplayStand')
reparent(cylinder('Display base',(0,0,.025),1.04,.11,teal),stand)
reparent(cylinder('Display top',(0,0,.086),1.025,.045,stone),stand)
reparent(box('Name plaque',(0,-.978,.112),(.66,.08,.17),navy,.025),stand)
reparent(label('Name plate text','ROOKIE',(0,-1.024,.12),.090,white),stand)

world=bpy.data.worlds.new('Warm studio');scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(*rgb('#DCE5D8'),1)
world.node_tree.nodes['Background'].inputs[1].default_value=.48
ground=box('Studio backdrop',(0,0,-.066),(200,200,.03),background,.001)
def light(name,loc,energy,size,color):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=rgb(color)
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=loc
    o.rotation_euler=(Vector((0,0,1.1))-o.location).to_track_quat('-Z','Y').to_euler()
light('Big soft key',(-3,-4,6),420,4,'#FFF0D8')
light('Soft sky fill',(4,-1,3.5),180,3,'#DDEFFF')
light('Warm edge',(0,3,4.5),320,3,'#FFF0D3')
c=bpy.data.cameras.new('Portrait camera');cam=bpy.data.objects.new('Portrait camera',c);scene.collection.objects.link(cam)
cam.location=(3.5,-6.8,3.6);cam.rotation_euler=(Vector((0,0,1.22))-cam.location).to_track_quat('-Z','Y').to_euler()
c.type='ORTHO';c.ortho_scale=3.65;scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.resolution_x=1400;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets'/'rookie_chicken.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type in {'FONT','CURVE'}:o.select_set(True)
bpy.context.view_layer.objects.active=next(iter(bpy.context.selected_objects));bpy.ops.object.convert(target='MESH')
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type in {'MESH','EMPTY'} and o.name!='Studio backdrop':o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets'/'rookie_chicken.glb'),export_format='GLB',use_selection=True,
    export_apply=True,export_yup=True,export_lights=False,export_cameras=False)
scene.render.filepath=str(ROOT/'renders'/'chicken_portrait.png');bpy.ops.render.render(write_still=True)
for o in kit.children_recursive:o.hide_render=False
bpy.data.objects['Cream belly bib'].hide_render=True
scene.render.filepath=str(ROOT/'renders'/'chicken_player.png');bpy.ops.render.render(write_still=True)
print('CHICKEN_BUILD_COMPLETE',flush=True)
