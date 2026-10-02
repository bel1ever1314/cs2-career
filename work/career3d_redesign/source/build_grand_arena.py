"""Original arena cutaway inspired by public arena seating/concourse layouts.

Run in Blender 5.2. The small reference is used only as a library of original
primitive builders and the ten-player booth. No external meshes are imported.
Coordinates: X/Y ground, Z up. Crowd meshes are shared for efficient instancing.
"""
from pathlib import Path
import ast
import json

reference = (Path(__file__).parent / 'small_arena_reference.py').read_text(encoding='utf-8')
exec(compile(reference.split('# Arena shell with open roof')[0], __file__, 'exec'))
arena.name = 'GrandMajorArena'
for node in ast.parse(reference).body:
    if isinstance(node, ast.FunctionDef) and node.name == 'team_booth':
        exec(compile(ast.Module(body=[node], type_ignores=[]), __file__, 'exec'))

def arc_band(name, ri, ro, low, high, material, start=-.075, end=math.pi+.075):
    n = max(4, int((end-start)*28))
    verts=[]
    for i in range(n+1):
        a=start+(end-start)*i/n
        for r,z in ((ri,low),(ro,low),(ri,high),(ro,high)):
            verts.append((r*math.cos(a),3-r*math.sin(a),z))
    faces=[]
    for i in range(n):
        k=4*i
        faces.extend([(k,k+4,k+5,k+1),(k+2,k+3,k+7,k+6),
                      (k,k+2,k+6,k+4),(k+1,k+5,k+7,k+3)])
    faces.extend([(0,1,3,2),(4*n,4*n+2,4*n+3,4*n+1)])
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);arena.objects.link(o);mesh.materials.append(material)
    return o

def arc_line(name,r,z,material,radius=.055,start=-.075,end=math.pi+.075):
    return tube(name,[(r*math.cos(a),3-r*math.sin(a),z)
                     for a in [start+(end-start)*i/140 for i in range(141)]],radius,material)

def translated_new(before, delta):
    for o in set(bpy.data.objects)-before:
        o.location += Vector(delta)

# Width 108, length 94; people and desks retain their small-prototype scale.
box('Rounded foundation',(0,-12,-.75),(108,94,1.5),navy,.7)
box('Brass foundation trim',(0,-12,.035),(107.3,93.3,.15),gold,.07)
box('Public plaza and arena floor',(0,-12,.17),(106.7,92.7,.18),floor,.3)
arc_band('Bowl dark floor',0,50,.27,.34,navy2)
box('Event floor',(0,0,.38),(42,38,.12),navy,.3)
box('Rear stage platform',(0,18,.89),(32,15,1.25),navy2,.3)
box('Stage oak border',(0,18,1.55),(32.1,15.1,.10),wood,.045)
box('Stage performance floor',(0,18,1.62),(31.5,14.5,.08),navy2,.04)
for i in range(5):
    box('Front stage broad step',(0,10.02-i*.40,.39+(5-i)*.117),(18,.43,(5-i)*.234),cream,.035)
box('Champions runway',(0,5.4,.68),(3.2,11.5,.55),navy2,.13)
for x in (-1.53,1.53):box('Runway light',(x,5.4,.972),(.055,11.4,.035),amber,.013)

# Main screen, banners and stage wings. Main display is intentionally much
# larger than the ten unchanged desks/players, not uniformly scaled furniture.
box('Stage rear acoustic wall',(0,25.65,7.9),(34,.65,15.2),navy,.26)
for x in range(-16,17,2):box('Stage oak acoustic fin',(x,25.24,7.9),(.17,.3,14.1),wood,.055)
box('Main screen rounded surround',(0,24.1,9.4),(24.5,.66,10.8),cream,.25)
box('Main LED screen',(0,23.69,9.4),(23.8,.13,10.1),screen,.16)
text('Main MAJOR headline','MAJOR',(0,23.58,11.8),2.35,white)
text('Main stage subtitle','THE GRAND FINAL',(0,23.56,9.8),.64,gold)
text('Main score','12 : 12',(0,23.55,7.85),1.68,ice)
text('Event signature','CS2 CAREER  /  WORLD CHAMPIONSHIP',(0,23.54,5.44),.34,white)
for side in (-1,1):
    box('Wing screen surround',(side*20.0,21.1,7.5),(6.1,.55,9.2),cream,.19)
    box('Wing screen',(side*20.0,20.78,7.5),(5.6,.1,8.7),screen,.14)
    text('Wing team title','TEAM 01' if side<0 else 'TEAM 02',(side*20,20.69,9.5),.59,ice if side<0 else amber)
    star('Wing team star',(side*20,20.67,7.65),1.4,teal if side<0 else coral)
    text('Wing final label','FINALIST',(side*20,20.67,5.3),.42,white)
    before=set(bpy.data.objects);team_booth(side);translated_new(before,(side*2.8,14.0,.50))
    # Backstage buildings, portals and coach/media lounge.
    box('Backstage team block',(side*35,19,4.0),(17,17,7.4),cream,.48)
    box('Team tunnel portal',(side*28.8,10.39,2.18),(3.8,.24,3.8),navy2,.23)
    text('Tunnel label','PLAYERS',(side*28.8,10.20,4.53),.43,navy)
    box('Backstage color band',(side*35,10.4,5.5),(15.4,.15,.8),teal if side<0 else coral,.10)
    text('Backstage title','TEAM LOUNGE' if side<0 else 'MEDIA CENTRE',(side*35,10.28,6.44),.50,navy)
    for dx in (-4,0,4):
        box('Lounge window',(side*35+dx,10.33,3.1),(2.7,.17,2.5),screen,.15)
    for y in (11.5,16,20.5):
        cyl('Stage light base',(side*15,y,1.86),.27,.36,black)
        box('Stage moving light',(side*15,y,2.21),(.52,.50,.50),black,.12)
        sphere('Stage lens',(side*15,y-.24,2.23),(.18,.035,.18),ice if side<0 else amber)

# Original trophy from the small scene, preserved at furniture scale.
trophy_code=reference.split('# Original cup, elevated on its own championship pedestal.')[1].split('# Side seating banks')[0]
before=set(bpy.data.objects);exec(compile(trophy_code,__file__,'exec'));translated_new(before,(0,2.0,-.20))

# Bake eight reusable seat/fan prototypes rather than thousands of unique bears.
prefabs=[]
for variant in range(8):
    before=set(bpy.data.objects)
    seat_and_fan(0,0,0,0,teal_dark if variant%2==0 else coral_dark,variant,variant!=7)
    created=list(set(bpy.data.objects)-before)
    bpy.ops.object.select_all(action='DESELECT')
    for o in created:o.select_set(True)
    bpy.context.view_layer.objects.active=created[0]
    bpy.ops.object.convert(target='MESH');bpy.ops.object.join()
    o=bpy.context.object
    # Joining into a scaled sphere retains that object's transform. Bake it
    # before sharing raw mesh data, otherwise crowd instances become giants.
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    dec=o.modifiers.new('Crowd distance mesh','DECIMATE');dec.ratio=.38
    bpy.ops.object.modifier_apply(modifier=dec.name)
    mesh=o.data;mesh.name='CrowdPrefab_%02d'%variant;mesh.use_fake_user=True
    assert max(o.dimensions)<2.2, 'Crowd prototype transform was not baked'
    prefabs.append(mesh);bpy.data.objects.remove(o,do_unlink=True)

seat_count=0
def crowd(x,y,z,angle,index):
    global seat_count
    o=bpy.data.objects.new('Crowd_%05d'%seat_count,prefabs[index%8]);arena.objects.link(o)
    o.location=(x,y,z);o.rotation_euler.z=angle;seat_count+=1

# Three stepped horseshoe tiers, distinct public circulation rings between them.
tiers=[(23.0,.65,6),(32.0,5.1,7),(42.0,10.0,7)]
for tier,(radius,base,rows) in enumerate(tiers):
    for row in range(rows):
        r=radius+row*.94;z=base+row*.55
        arc_band('Tier %d terrace %d'%(tier+1,row+1),r-.48,r+.48,.33,z,stepmat)
        count=int(math.pi*r/.70)
        for i in range(count):
            a=.035+(math.pi-.07)*i/(count-1)
            if min(abs(a-j*math.pi/6) for j in range(7))<.026:continue
            x=r*math.cos(a);y=3-r*math.sin(a)
            crowd(x,y,z+.025,math.atan2(-x,-(17-y)),seat_count+row*3)
        # Proper walk aisles, subdivided into gentle smaller stair risers.
        for j in range(1,6):
            a=j*math.pi/6
            for k in range(3):
                rr=r-.47+k*.314;zz=z-.55+(k+1)*(.55/3)
                box('Radial public stair',(rr*math.cos(a),3-rr*math.sin(a),max(.36,zz)/2),
                    (.33,1.48,max(.36,zz)),cream,.015,a)
    outer=radius+(rows-1)*.94+.55
    arc_band('Tier %d circulation ring'%(tier+1),outer,outer+2.30,.34,base+(rows-1)*.55,floor)
    arc_line('Tier front safety rail',radius-.52,base+1.1,cream,.07)
    arc_line('Continuous LED ribbon',radius-.56,base+.42,ice if tier%2==0 else amber,.11)
    arc_line('Concourse outside rail',outer+2.05,base+(rows-1)*.55+1.0,cream,.07)
    for j in range(6):
        a=(j+.5)*math.pi/6
        x=(radius-.55)*math.cos(a);y=3-(radius-.55)*math.sin(a)
        # Section numbers are visible from the front cutaway, not official seat codes.
        text('Section number',str((tier+1)*100+j+1),(x,y-.06,base+.03),.36,white)

# A rhythm of public entry bays and timber fins softens the exposed bowl wall.
for j in range(19):
    a=.08+(math.pi-.16)*j/18
    r=50.62;angle=math.pi/2-a
    x=r*math.cos(a);y=3-r*math.sin(a)
    box('Exterior timber fin',(x,y,7.0),(.20,.42,13.2),wood,.07,angle)
    if j%2==1:
        box('Concourse public entry bay',(x,y,2.13),(2.7,.19,3.5),navy,.16,angle)
        o=text('Exterior gate number','GATE %02d'%(j//2+1),(x+.13*math.cos(a),y-.13*math.sin(a),4.25),.32,navy)
        o.rotation_euler.z=angle

# Flat-floor seating blocks separated by a wide central champions aisle.
for row in range(20):
    y=7.0-row*.88
    for side in (-1,1):
        for col in range(11):
            x=side*(3.25+col*.67)
            crowd(x,y,.49,math.pi,seat_count+row)
box('Main floor centre aisle',(0,-7,.475),(3.9,21,.055),carpet,.025)
text('Floor welcome','FINALS WEEKEND',(0,-17.5,.50),1.0,cream).rotation_euler=(0,0,0)

# Front foyer is a separate human-scale destination, not another spectator row.
box('Front foyer floor',(0,-52.0,.42),(72,11.4,.24),cream,.18)
for x in (-35,35):box('Foyer short return wall',(x,-52,2.0),(.42,11.0,3.15),navy,.15)
for side in (-1,1):
    cx=side*24
    box('Foyer concession counter',(cx,-51.8,1.15),(13,1.6,1.3),teal if side<0 else coral,.16)
    box('Counter oak worktop',(cx,-51.8,1.84),(13.3,1.85,.14),wood,.065)
    for xx in (-5,5):rod('Kiosk canopy post',(cx+xx,-51.2,.6),(cx+xx,-51.2,4.1),.10,cream)
    box('Concession fascia',(cx,-51.3,3.8),(13.6,.48,.85),navy,.16)
    text('Concession sign','FAN SHOP' if side<0 else 'COFFEE & SNACKS',(cx,-51.58,3.81),.52,white)
    for k in range(6):
        cyl('Coffee or souvenir display',(cx-4.5+k*1.8,-51.8,2.03),.13,.28,cream if side>0 else gold)
    # Wayfinding towers and gate openings establish the scale against the crowd.
    box('Gate sign tower',(side*11,-48.3,2.3),(1.9,.45,3.8),navy,.15)
    text('Gate wayfinding','A' if side<0 else 'B',(side*11,-48.58,2.92),.98,gold)
    text('Gate wayfinding small','SEATS',(side*11,-48.58,1.88),.22,white)
for x in (-5.4,-3.6,-1.8,0,1.8,3.6,5.4):
    box('Entry turnstile',(x,-54.7,.97),(.52,1.2,1.15),navy,.12)
    rod('Turnstile arm',(x,-55.0,1.32),(x+.7,-55.0,1.32),.035,gold)
for x in (-8.0,8.0):rod('Entrance welcome column',(x,-56.0,.5),(x,-56.0,5.8),.22,cream)
box('Entrance title frame',(0,-56.0,5.1),(18,.60,1.65),navy,.26)
text('Entrance title','MAJOR ARENA',(0,-56.34,5.25),1.0,white)
text('Entrance subtitle','A PLACE TO BECOME LEGEND',(0,-56.34,4.55),.23,gold)
for x in (-40,-31,31,40):
    cyl('Plaza tree planter',(x,-56.0,.76),.88,1.0,cream)
    cyl('Plaza tree trunk',(x,-56.0,2.0),.14,2.2,wood)
    sphere('Plaza rounded tree',(x,-56.0,3.4),(1.5,1.5,1.8),green)

# Rear suspension frame retained; roof omitted as an intentional dollhouse cutaway.
for x in (-24.3,24.3):rod('Stage arch upright',(x,24,.8),(x,24,18.5),.30,cream)
tube('Championship overhead arch',[(24.3*math.cos(a),24,18.5+3.3*math.sin(a))
     for a in [math.pi*i/64 for i in range(65)]],.30,cream)
for x in range(-21,22,3):
    rod('Rig pendant',(x,24,18.5),(x,24,16.8),.035,black)
    box('Rig spotlight',(x,24,16.6),(.65,.7,.6),black,.12)
    sphere('Rig lens',(x,23.64,16.5),(.22,.04,.18),lightwhite)

metadata={'schema_version':1,'seat_count':seat_count,'tiers':3,
          'foundation_dimensions':[108,94],'style':'original cozy arena cutaway',
          'references':['https://www.royalarena.dk/en/om'],
          'note':'Concept model, not a measured Royal Arena replica or construction plan.'}
(ROOT/'assets'/'venue_info.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print('VENUE_METADATA',metadata,flush=True)

world=bpy.data.worlds.new('Soft architectural daylight') if not bpy.data.worlds else bpy.data.worlds[0]
bpy.context.scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(*rgb('#B8C9D0'),1)
world.node_tree.nodes['Background'].inputs[1].default_value=.65
backdrop=box('Studio backdrop',(0,0,-1.65),(1000,1000,.10),mat('Studio mist','#B8C9D0'),0)
def area(name,loc,energy,size,color,target):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=rgb(color)
    o=bpy.data.objects.new(name,d);arena.objects.link(o);o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Huge softbox',(-45,-35,85),140000,60,'#FFF1D4',(0,-10,0))
area('Cool fill',(55,10,60),100000,50,'#DAEEFF',(0,0,5))
area('Stage front light',(0,-2,29),19000,25,'#FFF0DC',(0,19,5))
camdata=bpy.data.cameras.new('Overview Camera');cam=bpy.data.objects.new('Overview Camera',camdata);arena.objects.link(cam)
cam.location=(110,-149,123);target=Vector((0,-10,4.0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
camdata.type='ORTHO';camdata.ortho_scale=139;bpy.context.scene.camera=cam
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32
scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.055
scene.render.resolution_x=1800;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets'/'grand_major_arena.blend'))
# GLB shares crowd meshes. Runtime viewer promotes them to MultiMesh batches.
bpy.ops.object.select_all(action='DESELECT')
for o in list(bpy.data.objects):
    if o.type in {'FONT','CURVE'}:o.select_set(True)
bpy.context.view_layer.objects.active=next(o for o in bpy.context.selected_objects)
bpy.ops.object.convert(target='MESH')
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type=='MESH' and o.name!='Studio backdrop':o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets'/'grand_major_arena.glb'),export_format='GLB',
    use_selection=True,export_apply=True,export_yup=True,export_lights=False,export_cameras=False)
print('GLB_EXPORTED',flush=True)
scene.render.filepath=str(ROOT/'renders'/'grand_arena_overview.png');bpy.ops.render.render(write_still=True)
camdata.type='PERSP';camdata.lens=24;cam.location=(0,-19,5.4);target=Vector((0,19,8.0))
cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
scene.render.resolution_x=1800;scene.render.resolution_y=1100
scene.render.filepath=str(ROOT/'renders'/'grand_arena_audience.png');bpy.ops.render.render(write_still=True)
print('GRAND_ARENA_DONE',flush=True)
