"""Original toy-like Major venue. Blender --background --python this_file.

All models are generated locally. This is a concept venue, not a replica of an
official Major. Coordinates: Blender X/Y ground and Z up; GLB converts to Godot.
"""
import bpy
import math
import random
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
for folder in ('assets','renders','temp'):
    (ROOT/folder).mkdir(parents=True,exist_ok=True)
random.seed(31)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name!='Collection':bpy.data.collections.remove(c)
arena=bpy.data.collections.get('Collection');arena.name='MajorArena'

def rgb(value):
    h=value.lstrip('#')
    def linear(v):return v/12.92 if v<.04045 else ((v+.055)/1.055)**2.4
    return tuple(linear(int(h[i:i+2],16)/255) for i in (0,2,4))

def mat(name,color,roughness=.55,metal=0,emission=0):
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb(color),1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=m.diffuse_color
    bs.inputs['Roughness'].default_value=roughness;bs.inputs['Metallic'].default_value=metal
    if emission:
        bs.inputs['Emission Color'].default_value=m.diffuse_color
        bs.inputs['Emission Strength'].default_value=emission
    return m

navy=mat('Midnight blue shell','#344A5D');navy2=mat('Stage dark slate','#243442')
cream=mat('Warm ivory structure','#EADFC7');white=mat('Chalk white','#FFF4DC')
teal=mat('Sea glass team','#78B2A6');teal_dark=mat('Deep teal seats','#447F7C')
coral=mat('Apricot team','#DF966D');coral_dark=mat('Terracotta seats','#B96F53')
gold=mat('Championship brass','#E5B45C',.3,.55);wood=mat('Warm plywood','#C79A68')
floor=mat('Warm stone concourse','#CEC6B5');stepmat=mat('Bleacher risers','#657D85')
carpet=mat('Golden entrance carpet','#DCAC61');black=mat('Equipment graphite','#273238')
screen=mat('Main LED navy','#172D3D',.5,0,.18)
ice=mat('LED sea glass','#96DBCD',.4,0,1.2);amber=mat('LED amber','#F5C976',.4,0,1.1)
lightwhite=mat('LED warm white','#FFEDC5',.5,0,1.3)
skin=[mat('Plush skin '+str(i),c) for i,c in enumerate(['#D0A582','#ECCCB0','#B38468','#BBA891'])]
shirts=[teal,coral,cream,navy,mat('Crowd lavender','#ABA4C6'),mat('Crowd mustard','#D4B469')]
green=mat('Decorative greenery','#749A74')

def finish(o,name,material,smooth=False):
    o.name=name
    if material:o.data.materials.append(material)
    if smooth and o.type=='MESH':
        for p in o.data.polygons:p.use_smooth=True
    return o

def box(name,loc,size,material,bevel=.06,angle=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object;o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        b=o.modifiers.new('Soft toy edges','BEVEL');b.width=min(bevel,min(size)*.46);b.segments=3
        o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    o.rotation_euler.z=angle
    return finish(o,name,material)

def sphere(name,loc,size,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,location=loc)
    o=bpy.context.object;o.scale=size
    return finish(o,name,material,True)

def cyl(name,loc,radius,height,material,verts=32,bevel=.025):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=radius,depth=height,location=loc)
    o=bpy.context.object
    if bevel:
        m=o.modifiers.new('Rounded rim','BEVEL');m.width=min(bevel,height*.3);m.segments=3
        o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return finish(o,name,material,True)

def cone(name,loc,r1,r2,height,material):
    bpy.ops.mesh.primitive_cone_add(vertices=40,radius1=r1,radius2=r2,depth=height,location=loc)
    o=bpy.context.object;m=o.modifiers.new('Soft rim','BEVEL');m.width=.025;m.segments=3
    o.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return finish(o,name,material,True)

def rod(name,a,b,radius,material):
    v=Vector(b)-Vector(a)
    o=cyl(name,(Vector(a)+Vector(b))/2,radius,v.length,material,12,.006)
    o.rotation_euler=v.to_track_quat('Z','Y').to_euler();return o

def tube(name,points,radius,material):
    c=bpy.data.curves.new(name,'CURVE');c.dimensions='3D';c.resolution_u=2
    c.bevel_depth=radius;c.bevel_resolution=3
    s=c.splines.new('POLY');s.points.add(len(points)-1)
    for p,v in zip(s.points,points):p.co=(*v,1)
    o=bpy.data.objects.new(name,c);arena.objects.link(o);c.materials.append(material);return o

def torus(name,loc,major,minor,material):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=32,minor_segments=8,location=loc)
    return finish(bpy.context.object,name,material,True)

def text(name,body,loc,size,material):
    c=bpy.data.curves.new(name,'FONT');c.body=body;c.size=size
    c.align_x='CENTER';c.align_y='CENTER';c.extrude=.005;c.bevel_depth=.002
    o=bpy.data.objects.new(name,c);arena.objects.link(o);o.location=loc;o.rotation_euler=(math.pi/2,0,0)
    c.materials.append(material);return o

def star(name,loc,radius,material):
    verts=[loc]
    for i in range(10):
        a=math.pi/2+i*math.pi/5;r=radius if i%2==0 else radius*.45
        verts.append((loc[0]+r*math.cos(a),loc[1],loc[2]+r*math.sin(a)))
    faces=[(0,i+1,(i+1)%10+1) for i in range(10)]
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);arena.objects.link(o);mesh.materials.append(material)
    o.modifiers.new('Emblem thickness','SOLIDIFY').thickness=.025;return o

def rotated_point(origin,angle,local):
    x,y,z=local;c=math.cos(angle);s=math.sin(angle)
    return (origin[0]+x*c-y*s,origin[1]+x*s+y*c,origin[2]+z)

def seat_and_fan(x,y,z,angle,seatmat,index,occupied=True):
    origin=(x,y,z)
    def p(v):return rotated_point(origin,angle,v)
    box('Seat cushion',p((0,0,.31)),(.47,.46,.12),seatmat,.052,angle)
    box('Seat rounded back',p((0,.19,.58)),(.48,.12,.53),seatmat,.055,angle)
    rod('Seat pedestal',p((0,0,.05)),p((0,0,.28)),.054,navy2)
    if not occupied:return
    clothing=shirts[index%len(shirts)];face=skin[index%len(skin)]
    sphere('Fan plush body',p((0,-.015,.60)),(.19,.17,.25),clothing)
    sphere('Fan round head',p((0,-.04,.92)),(.205,.19,.20),face)
    for dx in (-.15,.15):sphere('Fan bear ear',p((dx,-.005,1.087)),(.066,.055,.074),face)
    for dx in (-.068,.068):sphere('Fan eye',p((dx,-.22,.945)),(.017,.011,.021),black)
    for dx in (-.1,.1):sphere('Fan shoe',p((dx,-.235,.28)),(.08,.12,.067),navy2)
    for side in (-1,1):
        a=p((side*.16,-.03,.68));b=p((side*.29,-.10,1.02 if index%5==0 else .46))
        rod('Fan sleeve',a,b,.062,clothing);sphere('Fan hand',b,(.067,.067,.067),face)
    if index%11==0:
        rod('Supporter flag pole',p((.28,-.08,1.03)),p((.28,-.08,1.62)),.013,wood)
        box('Supporter pennant',p((.45,-.08,1.48)),(.36,.025,.22),coral if index%2 else teal,.012,angle)

# Arena shell with open roof and front for a cutaway view.
box('Rounded navy venue base',(0,0,-.33),(20.6,17.0,.75),navy,.30)
box('Foundation gold reveal',(0,0,.005),(20.35,16.76,.12),gold,.055)
box('Concourse floor',(0,0,.12),(20.1,16.5,.20),floor,.20)
box('Central fan floor',(0,-1.05,.235),(12.0,10.4,.075),cream,.12)
box('Main golden carpet',(0,-4.00,.286),(2.45,8.1,.05),carpet,.024)
for x in (-1.06,1.06):box('Carpet fine line',(x,-4,.318),(.032,7.9,.01),white,.004)
for y in (-6.4,-5.7,-5.0):
    box('Aisle arrow',(-.09,y,.322),(.24,.045,.018),cream,.007,math.pi/5)
    box('Aisle arrow',(.09,y,.322),(.24,.045,.018),cream,.007,-math.pi/5)
box('Rear acoustic wall',(0,7.48,3.25),(20.0,.38,6.2),navy,.18)
for x in [-9.65,-7.5,-5.4,-3.2,3.2,5.4,7.5,9.65]:box('Rear wall rib',(x,7.20,3.22),(.15,.17,5.78),stepmat,.06)
box('Back cornice',(0,7.43,6.4),(20.10,.59,.28),cream,.12)
for side in (-1,1):
    box('Side low wall',(side*9.90,-.05,1.34),(.32,15.7,2.27),navy,.12)
    box('Side ivory coping',(side*9.90,-.05,2.50),(.47,15.73,.14),cream,.06)
    for y in (-6.7,-3.2,.35,3.9,7.05):box('Side pillar',(side*9.9,y,2.0),(.55,.55,3.6),cream,.17)

# Championship stage and runway.
box('Main stage',(0,3.48,.63),(12.7,6.3,.80),navy2,.18)
box('Stage pale top',(0,3.48,1.065),(12.66,6.24,.14),navy,.065)
box('Front stage luminous strip',(0,.285,.72),(12.3,.045,.065),ice,.023)
for side in (-1,1):
    for j in range(3):
        top=.40+j*.235
        box('Stage access stair',(side*5.20,-.50+j*.29,.24+top/2),(1.65,.66,top),stepmat,.035)
        box('Stair nosing',(side*5.20,-.83+j*.29,.245+top),(1.55,.065,.026),lightwhite,.01)
box('Trophy runway',(0,.15,.54),(2.38,3.35,.59),navy2,.12)
box('Trophy runway top',(0,.15,.87),(2.34,3.31,.085),teal_dark,.035)
for x in (-1.12,1.12):box('Runway edge',(x,.15,.926),(.055,3.23,.025),amber,.01)

arc=[];inner=[]
for i in range(81):
    a=math.pi*i/80
    arc.append((7.05*math.cos(a),5.90,2.00+5.88*math.sin(a)))
    inner.append((6.72*math.cos(a),5.78,2.00+5.54*math.sin(a)))
tube('Ivory stage ribbon',arc,.25,cream);tube('Arch warm light',inner,.048,amber)
for x in (-7.05,7.05):box('Arch pedestal',(x,5.90,1.10),(.85,.87,1.83),cream,.18)
box('Main screen surround',(0,5.82,4.68),(10.50,.37,3.78),black,.20)
box('Main screen LED',(0,5.605,4.68),(10.13,.04,3.44),screen,.018)
text('Screen major title','MAJOR',(0,5.55,5.42),1.13,white)
text('Screen final title','G R A N D   F I N A L',(0,5.55,4.64),.27,amber)
box('Screen divider',(0,5.54,4.32),(8.65,.015,.022),teal,.005)
text('Screen score','12  :  12',(0,5.53,3.91),.59,white)
text('Left team label','TEAM 01',(-3.25,5.53,3.91),.29,ice)
text('Right team label','TEAM 02',(3.25,5.53,3.91),.29,amber)
for side in (-1,1):
    for j in range(3):box('Screen decorative bar',(side*(4.02+j*.22),5.54,5.47),(.09,.02,.50-j*.11),ice if side<0 else amber,.03)
for side in (-1,1):
    x=side*6.01
    box('Tall team tower',(x,4.28,3.15),(1.02,.38,4.0),teal_dark if side<0 else coral_dark,.14)
    box('Tower light line',(x,4.059,3.13),(.10,.035,3.63),ice if side<0 else amber,.045)
    star('Tower emblem',(x,4.016,4.01),.31,white)
    for y in (1.3,3.4,5.5):
        cyl('Floor moving light base',(side*6.05,y,1.24),.20,.20,black)
        o=box('Floor light housing',(side*6.05,y,1.50),(.32,.30,.38),black,.08);o.rotation_euler.y=-side*.35
        sphere('Stage lamp lens',(side*6.01,y-.11,1.63),(.11,.035,.11),ice if side<0 else amber)

def team_booth(side):
    cx=side*3.16;team=teal if side<0 else coral
    box('Team competition desk',(cx,2.73,1.74),(4.76,1.03,.22),cream,.09)
    box('Team desk front',(cx,2.25,1.51),(4.62,.16,.49),team,.065)
    box('Desk front illuminated band',(cx,2.146,1.30),(4.36,.035,.045),ice if side<0 else amber,.018)
    for dx in (-2.12,2.12):box('Desk support',(cx+dx,2.73,1.43),(.19,.80,.58),navy2,.05)
    text('Booth team number','01' if side<0 else '02',(cx,2.137,1.56),.29,white)
    for i in range(5):
        x=cx+(i-2)*.88
        box('Player monitor back',(x,2.72,2.17),(.65,.105,.43),black,.045)
        box('Monitor back accent',(x,2.653,2.17),(.27,.02,.035),team,.01)
        rod('Monitor stem',(x,2.79,1.86),(x,2.79,2.13),.027,black)
        box('Keyboard',(x,3.014,1.891),(.39,.15,.042),black,.017)
        for j in range(5):box('Keyboard lit row',(x+(j-2)*.065,2.974,1.917),(.04,.04,.009),ice if side<0 else amber,.003)
        sphere('Mouse',(x+.30,3.013,1.923),(.045,.069,.025),white)
        seat_and_fan(x,3.48,1.13,0,navy2,i,False)
        face=skin[(i+(side+1))%4]
        sphere('Competitor jersey',(x,3.43,1.89),(.215,.18,.31),team)
        sphere('Competitor head',(x,3.405,2.28),(.225,.21,.23),face)
        for dx in (-.17,.17):sphere('Competitor plush ear',(x+dx,3.41,2.48),(.075,.065,.07),face)
        for dx in (-.078,.078):sphere('Competitor eye',(x+dx,3.207,2.30),(.019,.009,.021),black)
        hp=[(x+.246*math.cos(a),3.39,2.29+.255*math.sin(a)) for a in [j*math.pi/16 for j in range(17)]]
        tube('Player headset',hp,.026,black)
        for dx in (-.235,.235):
            sphere('Player headset cup',(x+dx,3.39,2.28),(.049,.081,.105),black)
            rod('Player arm',(x+dx*.8,3.38,1.94),(x+dx*.8,3.04,1.92),.064,team)
    box('Coach tactics table',(cx,4.53,1.72),(1.08,.41,.08),cream,.03)
    sphere('Coach body',(cx,4.87,1.84),(.25,.20,.43),navy2)
    sphere('Coach head',(cx,4.87,2.38),(.24,.21,.24),skin[0])
    for dx in (-.18,.18):sphere('Coach ear',(cx+dx,4.87,2.59),(.075,.065,.075),skin[0])
team_booth(-1);team_booth(1)

# Original cup, elevated on its own championship pedestal.
box('Trophy stone base',(0,-.28,1.17),(1.03,.96,.43),cream,.10)
box('Trophy brass plaque',(0,-.79,1.17),(.57,.035,.19),gold,.02)
text('Trophy plaque letters','CHAMPION',(0,-.817,1.17),.083,navy2)
cyl('Trophy bottom',(0,-.28,1.43),.32,.13,gold)
cone('Trophy stem',(0,-.28,1.67),.15,.09,.41,gold)
cone('Trophy cup',(0,-.28,2.02),.13,.42,.40,gold)
torus('Trophy lip',(0,-.28,2.23),.39,.028,gold)
for side in (-1,1):
    pts=[(side*(.28+.30*math.sin(a)),-.28,2.14-.39*(a/math.pi)) for a in [j*math.pi/20 for j in range(21)]]
    tube('Trophy sweeping handle',pts,.047,gold)
star('Trophy medallion',(0,-.65,2.06),.12,white)

# Side seating banks face the stage; front seating leaves the carpet unobstructed.
index=0
for side in (-1,1):
    for row in range(4):
        x=side*(6.88+row*.73);z=.25+row*.47
        box('Side seating terrace',(x,.43,z/2),(.74,8.38,z),stepmat,.025)
        box('Side step glow',(x,-3.79,z+.016),(.64,.036,.025),amber,.008)
        for col in range(10):
            y=-3.31+col*.80;angle=math.atan2(-x,-(2.2-y))
            seat_and_fan(x,y,z+.03,angle,teal_dark if side<0 else coral_dark,index,index%9!=3);index+=1
    for y in (-3.95,4.88):
        for row in range(7):
            x=side*(6.50+row*.47);z=.20+row*.275
            box('Bleacher aisle stair',(x,y,z/2),(.48,.65,z),cream,.023)
    for y in (-3.78,4.80):rod('Stand handrail',(side*6.65,y,.92),(side*9.18,y,2.56),.027,cream)
for side in (-1,1):
    for row in range(2):
        y=-4.95-row*.82;z=.24+row*.38
        box('Front seating terrace',(side*3.57,y,z/2),(3.99,.84,z),stepmat,.035)
        for col in range(6):
            x=side*(1.96+col*.65)
            seat_and_fan(x,y,z+.035,math.pi,teal_dark if side<0 else coral_dark,index,index%7!=3);index+=1

# Broadcast cameras, entry marquee and fan-zone kiosks.
for x in (-3.23,3.23):
    for a in (0,2.1,4.2):rod('Camera tripod',(x,-.53,1.36),(x+.26*math.cos(a),-.53+.26*math.sin(a),.29),.026,black)
    box('Broadcast camera',(x,-.53,1.49),(.40,.51,.28),black,.055)
    o=cyl('Camera lens',(x,-.23,1.51),.105,.18,navy2);o.rotation_euler.x=math.pi/2
    box('Camera tally',(x,-.52,1.65),(.055,.06,.025),coral,.006)
for x in (-1.64,1.64):box('Entrance gate post',(x,-7.16,1.12),(.28,.48,1.78),cream,.11)
box('Entrance rounded marquee',(0,-7.16,2.00),(3.73,.51,.55),navy,.16)
text('Entrance lettering','MAJOR',(0,-7.445,2.01),.36,white)
for side in (-1,1):
    x=side*7.25;y=-6.63
    box('Fan kiosk lower body',(x,y,.75),(2.35,1.15,.98),teal_dark if side<0 else coral_dark,.13)
    box('Fan kiosk counter',(x,y,1.27),(2.51,1.31,.16),cream,.065)
    for dx in (-1.04,1.04):rod('Kiosk canopy post',(x+dx,y+.25,1.32),(x+dx,y+.25,2.43),.045,wood)
    box('Kiosk canopy',(x,y,2.43),(2.7,1.5,.24),cream,.11)
    for j in range(7):box('Kiosk awning stripe',(x+(j-3)*.34,y,2.564),(.19,1.38,.028),teal if side<0 else coral,.012)
    box('Kiosk sign',(x,y-.71,2.32),(1.76,.065,.33),navy,.045)
    text('Kiosk title','SNACKS' if side<0 else 'FAN SHOP',(x,y-.752,2.32),.19,white)
    if side<0:
        for j in range(4):
            cone('Paper drink cup',(x+(j-1.5)*.37,y-.20,1.47),.07,.10,.27,coral if j%2 else teal)
            cyl('Drink lid',(x+(j-1.5)*.37,y-.20,1.615),.103,.022,white)
            rod('Cup straw',(x+(j-1.5)*.37,y-.20,1.62),(x+(j-1.5)*.37+.025,y-.20,1.75),.012,white)
    else:
        for j in range(3):
            box('Folded fan jersey',(x+(j-1)*.50,y-.13,1.43),(.42,.44,.13),teal if j%2 else coral,.06)
            star('Jersey star',(x+(j-1)*.50,y-.37,1.45),.065,white)
    px=x-side*1.63
    cone('Topiary pot',(px,y,.43),.23,.31,.43,wood)
    rod('Topiary trunk',(px,y,.62),(px,y,1.10),.047,wood)
    sphere('Topiary crown',(px,y,1.18),(.43,.40,.43),green)
rod('Lighting bar',(-6.1,5.9,7.05),(6.1,5.9,7.05),.07,navy2)
for x in (-5.5,-3.7,-1.9,0,1.9,3.7,5.5):
    box('Overhead light fixture',(x,5.88,6.91),(.34,.41,.28),black,.06)
    sphere('Overhead lens',(x,5.65,6.85),(.12,.045,.105),ice if x<0 else amber)
text('Rear upper side left','01',(-8.28,7.246,4.98),.91,ice)
text('Rear upper side right','02',(8.28,7.246,4.98),.91,amber)

def area(name,loc,power,size,color,target):
    bpy.ops.object.light_add(type='AREA',location=loc)
    o=bpy.context.object;o.name=name;o.data.energy=power;o.data.shape='DISK';o.data.size=size;o.data.color=color
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o
area('Huge softbox',(1,-7,17),2850,11,(1.0,.87,.70),(0,0,0))
area('Blue side fill',(-10,0,11),1500,9,(.65,.83,1.0),(0,2,1))
area('Warm arena rim',(7,7,12),2400,7,(1.0,.77,.52),(0,0,1))
area('Stage teal wash',(-4,3.0,6.8),220,4,(.51,1.0,.87),(-3,2,1))
area('Stage amber wash',(4,3.0,6.8),220,4,(1.0,.66,.36),(3,2,1))
studio=mat('Studio blue grey','#B8C5CA')
ground=box('Studio backdrop',(0,0,-.79),(200,200,.1),studio,.01)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.035
scene.render.resolution_x=1700;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.world.use_nodes=True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.58,.72,.80,1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.38
scene.view_settings.view_transform='AgX'
try:scene.view_settings.look='AgX - Medium High Contrast'
except TypeError:pass
bpy.ops.object.camera_add(location=(22,-30,26))
camera=bpy.context.object;camera.name='Arena overview camera'
camera.rotation_euler=(Vector((0,.4,2.05))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=31.5;scene.camera=camera
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets'/'major_arena.blend'))
bpy.ops.object.select_all(action='DESELECT')
for o in list(arena.objects):
    if o.type in ('CURVE','FONT'):o.select_set(True)
if bpy.context.selected_objects:
    bpy.context.view_layer.objects.active=bpy.context.selected_objects[0];bpy.ops.object.convert(target='MESH')
bpy.ops.object.select_all(action='DESELECT')
for o in arena.objects:
    if o.type=='MESH' and o!=ground:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets'/'major_arena.glb'),export_format='GLB',use_selection=True,export_apply=True,export_cameras=False,export_lights=False,export_yup=True)
scene.render.filepath=str(ROOT/'renders'/'arena_overview.png')
bpy.ops.render.render(write_still=True)
print('MAJOR_ARENA_COMPLETE',len([o for o in arena.objects if o.type=='MESH']))
