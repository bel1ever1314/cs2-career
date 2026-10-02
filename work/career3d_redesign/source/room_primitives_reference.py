"""Original cozy room prototype. Run with Blender --background --python this_file.

All geometry is generated here; no third-party models, textures or game assets.
Blender coordinates: X right, Y back, Z up. Godot GLB importer handles conversion.
"""
import bpy
import math
import os
import random
from mathutils import Vector
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
random.seed(23)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != 'Collection':
        bpy.data.collections.remove(c)
room = bpy.data.collections.get('Collection')
room.name = 'CozyRoom'

def linear(c):
    return c / 12.92 if c < .04045 else ((c + .055) / 1.055) ** 2.4

def material(name, color, rough=.6, emission=0):
    h = color.lstrip('#')
    rgb = [linear(int(h[i:i+2], 16) / 255) for i in (0, 2, 4)]
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*rgb, 1)
    bs.inputs['Roughness'].default_value = rough
    if emission:
        bs.inputs['Emission Color'].default_value = (*rgb, 1)
        bs.inputs['Emission Strength'].default_value = emission
    return m

cream = material('Warm ivory plaster', '#F4E7CC')
mint = material('Sage painted wainscot', '#AABFAD')
trim = material('Honey wood', '#B98453')
wood = material('Natural oak', '#D7AD77')
woodlight = material('Light oak', '#E1BC89')
wooddark = material('Walnut', '#73503B')
seam = material('Floor seams', '#AD855F')
coral = material('Terracotta linen', '#D98F72')
corallight = material('Linen highlights', '#E3A589')
ivory = material('Cotton', '#FFF0D6')
teal = material('Deep sage cloth', '#698A7D')
gold = material('Brushed brass', '#D9AC56', .32)
dark = material('Ink', '#374641')
green = material('Leaves', '#678A57')
greenlight = material('Fresh leaves', '#A0B475')
soil = material('Potting soil', '#584136')
clay = material('Ceramic clay', '#DFA88A', .42)
blue = material('Dusty blue', '#8FAEB9')
screen = material('Screen glow', '#618F97', .42, .45)
screenlight = material('Screen graphics', '#B4D6CC', .6, .35)
orange = material('Amber', '#E9B460')
brown = material('Plush caramel', '#BE956C')
blush = material('Plush blush', '#DD9B87')

def finish(o, name, mat, smooth=False):
    o.name = name
    if mat:
        o.data.materials.append(mat)
    if smooth and o.type == 'MESH':
        for p in o.data.polygons:
            p.use_smooth = True
    return o

def box(name, loc, size, mat, radius=.05, rot=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if radius:
        b = o.modifiers.new('Soft edges', 'BEVEL')
        b.width = min(radius, min(size) * .47)
        b.segments = 4
        n = o.modifiers.new('Weighted corner normals', 'WEIGHTED_NORMAL')
        n.keep_sharp = True
    o.rotation_euler.z = rot
    return finish(o, name, mat)

def ellipsoid(name, loc, scale, mat, rot=(0,0,0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=loc)
    o = bpy.context.object
    o.scale = scale
    o.rotation_euler = rot
    return finish(o, name, mat, True)

def cylinder(name, loc, radius, depth, mat, vertices=48, bevel=.025):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = bpy.context.object
    if bevel:
        b = o.modifiers.new('Rounded rim', 'BEVEL')
        b.width = min(bevel, depth*.3)
        b.segments = 3
        o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return finish(o, name, mat, True)

def cone(name, loc, r1, r2, depth, mat):
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=r1, radius2=r2, depth=depth, location=loc)
    o = bpy.context.object
    b = o.modifiers.new('Soft lip', 'BEVEL')
    b.width = .025
    b.segments = 3
    o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return finish(o, name, mat, True)

def rod(name, a, b, radius, mat):
    delta = Vector(b)-Vector(a)
    o = cylinder(name, (Vector(a)+Vector(b))/2, radius, delta.length, mat, 16, .008)
    o.rotation_euler = delta.to_track_quat('Z','Y').to_euler()
    return o

def torus(name, loc, major, minor, mat, rot=(0,0,0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
        major_segments=48, minor_segments=12, location=loc, rotation=rot)
    return finish(bpy.context.object, name, mat, True)

def plant(name, x, y, z, s=1):
    cone(name+' pot', (x,y,z+.18*s), .16*s, .21*s, .36*s, clay)
    cylinder(name+' earth',(x,y,z+.35*s),.18*s,.025*s,soil)
    for i in range(7):
        a = i*2.4
        end = (x+math.cos(a)*.25*s,y+math.sin(a)*.23*s,z+(.60+.08*(i%3))*s)
        rod(name+' stem',(x,y,z+.32*s),end,.013*s,green)
        ellipsoid(name+' leaf',end,(.11*s,.055*s,.25*s),green if i%2 else greenlight,
            (.45*math.cos(a),.6*math.sin(a),a))

def book(name,x,y,z,w,h,mat):
    box(name,(x,y,z+h/2),(w,.24,h),mat,.018)
    box(name+' spine band',(x,y-.126,z+h*.76),(w*.75,.01,.022),gold,.003)

# Floating cutaway shell and warm floorboards.
box('Rounded room plinth',(0,0,-.20),(6.75,6.05,.38),wooddark,.15)
box('Floor underlay',(0,0,.015),(6.4,5.7,.10),seam,.04)
floor_mats = [material('Oak plank '+str(i),c) for i,c in enumerate(['#D8B385','#DDBA8E','#D3AC7C','#E1BD91'])]
for row in range(13):
    x=-3.18+(row+.5)*6.36/13
    pieces = [(-2.85,0.0),(0.0,2.85)] if row%2 else [(-2.85,-1.25),(-1.25,1.45),(1.45,2.85)]
    for a,b in pieces:
        box('Oak floor board',(x,(a+b)/2,.075),(6.36/13-.012,b-a-.015,.065),random.choice(floor_mats),.012)

# Back and left walls; open camera-facing sides.
box('Back wall',(0,2.93,1.64),(6.7,.20,3.30),cream,.075)
box('Left wall',(-3.29,.02,1.64),(.20,5.95,3.30),cream,.075)
box('Back sage lower wall',(0,2.808,.52),(6.4,.075,.88),mint,.016)
box('Left sage lower wall',(-3.168,.0,.52),(.075,5.70,.88),mint,.016)
for i in range(17):
    box('Back panel seam',(-3.05+i*.38,2.76,.52),(.022,.025,.80),teal,.008)
for i in range(15):
    box('Left panel seam',(-3.12,-2.65+i*.38,.52),(.025,.022,.80),teal,.008)
box('Back chair rail',(0,2.73,1.0),(6.42,.14,.09),wood,.026)
box('Left chair rail',(-3.085,0,1.0),(.14,5.72,.09),wood,.026)
box('Back skirting',(0,2.73,.20),(6.42,.15,.19),wood,.028)
box('Left skirting',(-3.085,0,.20),(.15,5.72,.19),wood,.028)
box('Back top wood cap',(0,2.91,3.31),(6.76,.27,.12),wood,.035)
box('Left top wood cap',(-3.29,-.11,3.31),(.27,5.77,.12),wood,.035)

# Window: a small illustrated outside view, modelled rather than textured.
sky=material('Window blue sky','#B9D2D0',.7,.18)
hill=material('Distant greenery','#9DB8A1')
window_x=1.12
box('Window deep frame',(window_x,2.72,2.16),(2.50,.22,1.76),wood,.075)
box('Window sky',(window_x,2.582,2.16),(2.28,.028,1.53),sky,.02)
ellipsoid('Outside sun',(1.80,2.55,2.59),(.16,.018,.16),ivory)
for x,z,s in [(.36,1.67,.53),(1.02,1.66,.67),(1.94,1.65,.46)]:
    ellipsoid('Garden beyond window',(x,2.553,z),(s,.02,.32),hill)
for x in (window_x-1.17,window_x,window_x+1.17):
    box('Window vertical frame',(x,2.49,2.16),(.067,.12,1.62),ivory,.018)
for z in (1.35,2.16,2.97):
    box('Window horizontal frame',(window_x,2.49,z),(2.42,.12,.062),ivory,.018)
box('Wide window sill',(window_x,2.41,1.30),(2.76,.46,.13),woodlight,.045)
rod('Curtain rail',(-.43,2.42,3.06),(2.66,2.42,3.06),.04,wooddark)
for cx in (-.18,2.42):
    for j in range(4):
        ellipsoid('Soft sage curtain',(cx+(j-1.5)*.09,2.37,2.24),(.095,.065,.75),teal)
    box('Curtain tie',(cx,2.29,1.95),(.38,.055,.085),gold,.025)

# Bed on the left, padded headboard and soft fabric volumes.
for x in (-2.70,-1.30):
    for y in (-.40,2.03):
        cylinder('Bed foot',(x,y,.25),.085,.32,wooddark)
box('Bed frame',(-2.0,.84,.42),(1.82,2.86,.27),wood,.12)
box('Mattress',(-2.0,.82,.66),(1.73,2.74,.29),ivory,.13)
box('Bed headboard',(-2.0,2.25,.99),(1.91,.18,1.08),wood,.13)
box('Headboard cushion',(-2.0,2.135,1.09),(1.62,.09,.58),coral,.09)
box('Duvet',(-2.0,.38,.85),(1.80,1.91,.32),coral,.15)
box('Folded duvet edge',(-2.0,1.21,1.00),(1.79,.27,.13),corallight,.055)
for j in range(6):
    box('Duvet stitched seam',(-2.70+j*.28,.34,1.015),(.018,1.62,.009),corallight,.003)
for x in (-2.43,-1.61):
    p=box('Plump pillow',(x,1.70,.93),(.74,.60,.24),ivory,.115,rot=(-.07 if x < -2 else .07))
box('Bed throw',(-2.0,-.38,1.035),(1.84,.37,.085),teal,.035)
for x in (-2.73,-2.49,-2.25,-2.01,-1.77,-1.53,-1.29):
    rod('Throw tassel',(x,-.56,1.02),(x,-.64,.91),.017,ivory)

# Bedside drawers and lamp.
box('Bedside cabinet',(-.64,1.91,.46),(.72,.66,.71),woodlight,.075)
for z in (.33,.61):
    box('Drawer face',(-.64,1.561,z),(.60,.05,.23),wood,.025)
    ellipsoid('Drawer brass knob',(-.64,1.515,z),(.045,.032,.045),gold)
cylinder('Bedside lamp base',(-.66,1.90,.85),.16,.045,gold)
rod('Bedside lamp stem',(-.66,1.90,.87),(-.66,1.90,1.12),.024,gold)
cone('Bedside lampshade',(-.66,1.90,1.22),.24,.14,.29,ivory)

# Desk under window: friendly rounded computer and work details.
box('Desk oak top',(1.40,1.99,.98),(2.48,.97,.17),woodlight,.075)
for x in (.37,2.40):
    for y in (1.63,2.33):
        rod('Desk tapered leg',(x,y,.14),(x*.985,y,.91),.062,wood)
box('Desk drawer',(2.16,1.87,.76),(.70,.67,.30),wood,.04)
ellipsoid('Desk drawer handle',(2.16,1.505,.76),(.08,.025,.025),wooddark)
box('Monitor foot',(1.41,2.13,1.095),(.42,.30,.06),dark,.04)
box('Monitor neck',(1.41,2.18,1.34),(.075,.075,.47),dark,.025)
box('Monitor rounded casing',(1.41,2.16,1.57),(1.22,.12,.73),dark,.065)
box('Monitor screen',(1.41,2.089,1.58),(1.09,.015,.59),screen,.025)
# Abstract map / match interface, intentionally no unreadable tiny lettering.
for x,z,w,h in [(1.06,1.69,.25,.045),(1.64,1.69,.32,.045),(1.15,1.43,.30,.038),(1.66,1.43,.22,.038)]:
    box('Screen UI bar',(x,2.076,z),(w,.012,h),screenlight,.009)
box('Screen map',(1.4,2.073,1.56),(.25,.013,.22),teal,.02)
for x,z in [(1.30,1.60),(1.40,1.54),(1.48,1.61)]:
    ellipsoid('Screen map marker',(x,2.060,z),(.025,.008,.025),orange)
box('Desk mat',(1.45,1.69,1.076),(1.68,.43,.019),teal,.06)
box('Keyboard',(1.22,1.69,1.11),(.85,.27,.054),ivory,.028)
for row in range(3):
    for col in range(11):
        box('Keyboard key',(.86+col*.068,1.605+row*.07,1.143),(.052,.050,.018),woodlight if row==0 else ivory,.009)
ellipsoid('Mouse',(1.98,1.68,1.12),(.083,.13,.038),ivory)
box('Computer tower',(2.53,2.06,.50),(.33,.55,.72),ivory,.045)
box('Computer inset',(2.53,1.771,.50),(.22,.015,.55),teal,.025)
for z in (.35,.62):
    o=torus('Computer fan ring',(2.53,1.75,z),.07,.012,woodlight,(math.pi/2,0,0))

# Swivel chair, rounded padded seat and back.
cylinder('Chair base', (1.35,.94,.19),.27,.06,dark)
rod('Chair piston',(1.35,.94,.18),(1.35,.94,.58),.049,dark)
for i in range(5):
    a=i*math.tau/5
    q=(1.35+math.cos(a)*.36,.94+math.sin(a)*.36,.16)
    rod('Chair star foot',(1.35,.94,.20),q,.025,dark)
    ellipsoid('Chair caster',q,(.045,.045,.045),dark)
box('Chair cushion',(1.35,.91,.63),(.76,.66,.18),teal,.087)
for x in (1.03,1.67):
    rod('Chair back support',(x,.67,.60),(x,.59,1.17),.033,wood)
box('Chair rounded back',(1.35,.58,1.03),(.80,.16,.71),mint,.078)

# Headphones hanging from desk end.
o=torus('Headphone arch',(.23,1.74,.97),.16,.025,dark,(math.pi/2,0,0))
for x in (.075,.385):
    ellipsoid('Headphone earcup',(x,1.74,.90),(.056,.062,.12),coral)

# Rug with inset borders. An oval feels soft and handmade.
o=cylinder('Large oval rug',(0,-.91,.135),1,.044,ivory,96,.01)
o.scale=(1.73,1.33,1)
o=cylinder('Rug terracotta border',(0,-.91,.160),1,.008,coral,96,0)
o.scale=(1.58,1.18,1)
o=cylinder('Rug center',(0,-.91,.169),1,.008,ivory,96,0)
o.scale=(1.49,1.09,1)
for i in range(22):
    a=i*math.tau/22
    ellipsoid('Rug edge stitch',(math.cos(a)*1.65,-.91+math.sin(a)*1.25,.167),(.025,.025,.006),wood)

# Low table and belongings.
for a in (.2,2.3,4.4):
    x=.05+math.cos(a)*.33; y=-1.06+math.sin(a)*.33
    rod('Coffee table leg',(x*1.1,y,.18),(x,y,.58),.055,wooddark)
cylinder('Round coffee table',(.05,-1.06,.64),.68,.14,woodlight,64,.04)
box('Notebook',(-.18,-1.05,.735),(.34,.43,.055),blue,.019,rot=-.16)
box('Notebook elastic',(-.08,-1.066,.768),(.022,.42,.012),ivory,.003,rot=-.16)
cone('Tea cup',(.33,-.91,.81),.082,.098,.18,ivory)
cylinder('Tea',(.33,-.91,.903),.081,.008,wooddark,32,0)
torus('Cup handle',(.433,-.91,.827),.050,.014,ivory,(math.pi/2,0,0))
box('Gamepad',(.12,-1.39,.756),(.35,.17,.065),coral,.031,rot=.16)
for x in (-.005,.245):
    ellipsoid('Gamepad grip',(x,-1.44,.747),(.075,.095,.04),coral)
for x in (.025,.205):
    cylinder('Gamepad thumbstick',(x,-1.36,.795),.024,.018,dark,20,.005)

# Floor cushion and an original little bear plush.
ellipsoid('Beanbag',(1.72,-.83,.43),(.62,.59,.37),mint)
ellipsoid('Beanbag back',(1.83,-.48,.65),(.48,.23,.38),mint,(-.25,0,0))
ellipsoid('Cushion',(1.72,-.85,.73),(.25,.19,.07),ivory)
ellipsoid('Plush body',(-2.12,-.18,1.22),(.24,.18,.28),brown)
ellipsoid('Plush head',(-2.12,-.19,1.53),(.255,.20,.225),brown)
for dx in (-.18,.18):
    ellipsoid('Plush ear',(-2.12+dx,-.17,1.73),(.09,.062,.10),brown)
    ellipsoid('Plush arm',(-2.12+dx*1.5,-.18,1.27),(.09,.09,.16),brown)
    ellipsoid('Plush paw',(-2.12+dx,-.32,1.02),(.11,.13,.085),brown)
for dx in (-.087,.087):
    ellipsoid('Plush eye',(-2.12+dx,-.382,1.56),(.021,.012,.026),dark)
    ellipsoid('Plush cheek',(-2.12+dx*1.45,-.374,1.49),(.035,.012,.020),blush)
ellipsoid('Plush muzzle',(-2.12,-.387,1.47),(.083,.024,.052),ivory)
ellipsoid('Plush nose',(-2.12,-.416,1.49),(.025,.015,.017),dark)
box('Plush scarf',(-2.12,-.18,1.345),(.43,.35,.06),teal,.028)

# Left-wall wall art, with a simple original landscape.
box('Landscape frame',(-3.04,1.11,2.23),(.14,1.22,.96),wooddark,.045)
box('Landscape paper',(-2.955,1.11,2.23),(.025,1.05,.80),ivory,.015)
ellipsoid('Print sun',(-2.937,1.35,2.43),(.012,.145,.145),orange)
ellipsoid('Print green hill',(-2.927,1.12,2.04),(.012,.48,.19),mint)
ellipsoid('Print orange hill',(-2.916,.84,2.02),(.012,.24,.14),coral)

# Shelf and small trophy: a hint of a player's room, not a gaming showroom.
box('Wall floating shelf',(-2.78,-1.43,1.92),(.55,1.71,.13),woodlight,.04)
for y in (-2.10,-.78):
    box('Shelf bracket',(-3.02,y,1.70),(.22,.07,.36),wood,.02)
for i,(h,mat) in enumerate([(.41,coral),(.48,teal),(.35,blue),(.45,wooddark)]):
    box('Shelf book',(-2.80,-1.96+i*.105,1.995+h/2),(.29,.085,h),mat,.014)
    box('Shelf book line',(-2.645,-1.96+i*.105,2.05),(.009,.063,.02),ivory,.003)
cylinder('Trophy foot',(-2.78,-1.28,2.027),.12,.07,wooddark)
rod('Trophy stem',(-2.78,-1.28,2.06),(-2.78,-1.28,2.20),.029,gold)
cone('Trophy bowl',(-2.78,-1.28,2.30),.07,.16,.21,gold)
for y in (-1.47,-1.09):
    torus('Trophy handle',(-2.78,y,2.31),.083,.018,gold,(0,math.pi/2,0))
plant('Shelf succulent',-2.79,-.80,1.99,.51)

# Entry cabinet and foliage.
box('Entry cabinet',(2.59,-2.14,.45),(.83,.87,.72),woodlight,.055)
box('Cabinet inset',(2.59,-2.59,.44),(.68,.03,.54),mint,.025)
box('Cabinet divider',(2.59,-2.625,.44),(.035,.035,.54),wood,.008)
for x in (2.49,2.69):
    ellipsoid('Cabinet knob',(x,-2.65,.48),(.028,.023,.028),gold)
plant('Entry plant',2.60,-2.10,.82,1.30)
plant('Window plant',.18,2.34,1.38,.50)
for x in (-1.07,-.80):
    ellipsoid('Soft slippers',(x,-2.15,.19),(.105,.21,.075),teal)
    ellipsoid('Slipper opening',(x,-2.085,.24),(.065,.10,.022),dark)

# A small woven basket beside bed.
cone('Woven storage basket',(-2.68,-1.37,.33),.24,.30,.44,wood)
torus('Basket rim',(-2.68,-1.37,.55),.28,.022,wooddark)
for i in range(7):
    torus('Basket woven band',(-2.68,-1.37,.16+i*.055),.245+i*.006,.010,woodlight)
ellipsoid('Basket blanket',(-2.68,-1.37,.55),(.23,.22,.065),ivory)

# Lighting for the saved Blender scene and its preview renders.
def area(name, loc, energy, size, color, target):
    bpy.ops.object.light_add(type='AREA', location=loc)
    o=bpy.context.object; o.name=name
    o.data.energy=energy; o.data.shape='DISK'; o.data.size=size; o.data.color=color
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o

area('Large soft daylight',(1.0,-3.5,7.8),1050,6.0,(1.0,.89,.74),(0,0,0))
area('Window bounce',(1.0,2.0,4.6),650,3.5,(1.0,.95,.84),(0,-1,.5))
area('Cool gentle fill',(-3,-1,4),220,4.0,(.79,.88,1.0),(0,0,1))
bpy.ops.object.light_add(type='POINT', location=(-.66,1.90,1.20))
bpy.context.object.name='Bedside warm glow'
bpy.context.object.data.energy=12
bpy.context.object.data.color=(1,.66,.32)
bpy.context.object.data.shadow_soft_size=.30

# Studio backdrop, excluded from the exported interactive room.
studio=material('Studio peach','#E9DBCB')
backdrop=box('Studio ground',(0,0,-.46),(200,200,.10),studio,.01)

scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=48
scene.cycles.use_denoising=True
scene.cycles.adaptive_threshold=.035
scene.render.resolution_x=1500
scene.render.resolution_y=1300
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(.30,.30,.30)
scene.world.use_nodes=True
bg=scene.world.node_tree.nodes.get('Background')
bg.inputs['Color'].default_value=(.65,.73,.80,1)
bg.inputs['Strength'].default_value=.30
scene.view_settings.view_transform='AgX'
try:
    scene.view_settings.look='AgX - Medium High Contrast'
except TypeError:
    pass
scene.render.film_transparent=False
bpy.ops.object.camera_add(location=(9.4,-12.2,10.1))
camera=bpy.context.object; camera.name='Room overview camera'
camera.rotation_euler=(Vector((0,0,1.0))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'; camera.data.ortho_scale=10.35; camera.data.lens=45
scene.camera=camera

# GLB: mesh-only, no studio plane, lighting and camera are managed by Godot.
bpy.ops.object.select_all(action='DESELECT')
for o in room.objects:
    if o.type=='MESH' and o != backdrop:
        o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets'/'cozy_room.glb'),
    export_format='GLB', use_selection=True, export_apply=True,
    export_cameras=False, export_lights=False, export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets'/'cozy_room.blend'))
scene.render.filepath=str(ROOT/'renders'/'room_day.png')
bpy.ops.render.render(write_still=True)
print('COZY_ROOM_COMPLETE', len([o for o in room.objects if o.type=='MESH']))
