"""Original cozy chicken esports clubhouse. Blender Z-up, Y-back.

Six furnished areas linked by a wide hall. It is a dollhouse spatial prototype,
not an architectural construction plan. Walls are intentionally cut down at
camera-facing edges. Named room collections make future interactions separable.
"""
from pathlib import Path
reference=(Path(__file__).parent/'room_primitives_reference.py').read_text(encoding='utf-8')
exec(compile(reference.split('# Floating cutaway shell')[0],__file__,'exec'))
room.name='ClubStructure'
ROOT=Path(__file__).resolve().parents[1]
for folder in ('assets','renders','temp'):(ROOT/folder).mkdir(exist_ok=True)

navy=material('Club midnight','#2F4853');stone=material('Warm terrazzo','#DED5BF')
tile=material('Kitchen porcelain','#F2E9D7');tile2=material('Kitchen sage tile','#BCCDC0')
carpet=material('Training acoustic carpet','#718D8B');rug=material('Lounge apricot rug','#E1AF87')
glass=material('Window daylight','#BCD9D6',.45,.22);steel=material('Brushed appliances','#8EAAA8',.35)
coffee=material('Coffee','#5B4031');fruit=material('Tomato red','#C76B51')

def text(name,body,loc,size,mat):
    c=bpy.data.curves.new(name,'FONT');c.body=body;c.size=size;c.align_x='CENTER';c.align_y='CENTER'
    c.extrude=.003;c.bevel_depth=.001
    o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o)
    o.location=loc;o.rotation_euler=(math.pi/2,0,0);c.materials.append(mat);return o

def zone_begin(name):
    return name,set(bpy.data.objects)

def zone_end(token):
    name,before=token;c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c)
    for o in set(bpy.data.objects)-before:
        for old in list(o.users_collection):old.objects.unlink(o)
        c.objects.link(o)

def floor_label(name,word,x,y,material=navy):
    o=text(name,word,(x,y,.17),.38,material);o.rotation_euler=(0,0,0)

def wall_x(name,x,y0,y1,height=1.25):
    if y1<=y0:return
    box(name,(x,(y0+y1)/2,.14+height/2),(.18,y1-y0,height),cream,.04)
    box(name+' oak cap',(x,(y0+y1)/2,.17+height),(.23,y1-y0+.04,.075),wood,.026)

def wall_y(name,y,x0,x1,height=1.25):
    if x1<=x0:return
    box(name,((x0+x1)/2,y,.14+height/2),(x1-x0,.18,height),cream,.04)
    box(name+' oak cap',((x0+x1)/2,y,.17+height),(x1-x0+.04,.23,.075),wood,.026)

def doorway(name,y,x,width=1.6):
    for side in (-1,1):box(name+' oak jamb',(x+side*width/2,y,1.30),(.13,.24,2.32),wood,.04)
    box(name+' oak lintel',(x,y,2.48),(width+.14,.25,.18),wood,.05)
    box(name+' sign',(x,y-.14,2.60),(width+.30,.07,.30),navy,.06)
    text(name+' text',name.upper(),(x,y-.186,2.60),.16,ivory)

def rear_window(x,width):
    box('Window frame',(x,8.65,2.20),(width,.22,1.83),wood,.08)
    box('Window pale sky',(x,8.51,2.20),(width-.18,.04,1.62),glass,.03)
    for dx in (-width*.25,width*.25):
        ellipsoid('Window garden',(x+dx,8.474,1.65),(width*.23,.012,.28),greenlight)
    for dx in (-width/2+.07,0,width/2-.07):box('Window mullion',(x+dx,8.44,2.20),(.058,.13,1.68),ivory,.018)
    box('Window sill',(x,8.34,1.31),(width+.22,.40,.12),woodlight,.035)

def chair(x,y,z=.16,angle=0,color=teal,office=False):
    def p(dx,dy,dz):return (x+dx*math.cos(angle)-dy*math.sin(angle),y+dx*math.sin(angle)+dy*math.cos(angle),z+dz)
    box('Chair seat',p(0,0,.48),(.57,.56,.14),color,.065,angle)
    box('Chair curved back',p(0,.23,.86),(.58,.14,.68),color,.068,angle)
    if office:
        rod('Chair stem',p(0,0,.08),p(0,0,.42),.055,dark)
        for a in range(5):
            ang=angle+a*math.tau/5
            end=(x+.31*math.cos(ang),y+.31*math.sin(ang),z+.1)
            rod('Chair caster leg',p(0,0,.13),end,.032,dark)
            ellipsoid('Chair caster',end,(.055,.055,.05),dark)
    else:
        for dx in (-.21,.21):
            for dy in (-.19,.19):rod('Chair leg',p(dx,dy,.04),p(dx,dy,.44),.033,wooddark)

def table(x,y,length,width,z=.93):
    box('Oak tabletop',(x,y,z),(length,width,.13),woodlight,.09)
    for dx in (-length/2+.18,length/2-.18):
        for dy in (-width/2+.14,width/2-.14):box('Table oak leg',(x+dx,y+dy,(z-.04+.16)/2),(.10,.10,z-.20),wood,.027)

def mug(x,y,z,color=ivory):
    cylinder('Coffee mug',(x,y,z+.08),.078,.15,color,24,.009)
    cylinder('Coffee surface',(x,y,z+.158),.058,.006,coffee,24,.001)
    torus('Mug handle',(x+.087,y,z+.09),.041,.014,color,(math.pi/2,0,0))

def sofa(x,y,width=2.8,angle=0,color=coral):
    def p(dx,dy,dz):return (x+dx*math.cos(angle)-dy*math.sin(angle),y+dx*math.sin(angle)+dy*math.cos(angle),dz)
    box('Sofa base',p(0,0,.46),(width,.95,.40),color,.17,angle)
    box('Sofa back',p(0,.40,.95),(width,.23,1.0),color,.11,angle)
    for side in (-1,1):
        box('Sofa arm',p(side*(width/2-.12),-.03,.76),(.27,.96,.56),color,.12,angle)
    for i in range(3):box('Sofa loose cushion',p((i-1)*(width-.55)/3,-.08,.72),((width-.60)/3,.67,.22),corallight if color==coral else mint,.08,angle)
    for side in (-1,1):
        o=box('Sofa scatter pillow',p(side*(width/2-.45),.20,1.07),(.45,.17,.45),ivory,.09,angle)
        o.rotation_euler.y=side*.17

# The uninterrupted public corridor occupies Y=-0.8..1.65. Rear rooms open into
# it; front rooms have wide doorways, not solid walls across their approaches.
box('Rounded clubhouse foundation',(0,0,-.15),(25.4,20.5,.55),navy,.23)
box('Foundation oak edge',(0,0,.095),(25.1,20.2,.12),wood,.05)
box('Main interior floor',(0,0,.12),(24.5,18.0,.09),stone,.03)
for ix in range(41):
    x=-12.1+ix*.59
    for iy in range(5):box('Oak floor plank',(x,-7.95+iy*1.43,.175),(.577,1.41,.04),woodlight if (ix+iy)%3 else wood,.008)
box('Continuous corridor runner',(0,.39,.19),(23.8,1.65,.04),mint,.08)
for x in (-7.0,0,7.3):floor_label('Hallway arrow','>  CLUBHOUSE  >',x,.26,teal)
wall_y('Rear wall',8.82,-12.3,12.3,3.25)
wall_x('Left external wall',-12.27,-8.8,8.8,1.25)
wall_x('Right external wall',12.27,-8.8,8.8,1.1)
wall_x('Training meeting partition',-2.1,1.70,8.7,1.45)
wall_x('Meeting kitchen partition',4.2,1.70,8.7,1.45)
wall_x('Lounge lobby partition',-4.4,-8.75,-.83,1.05)
wall_x('Lobby dining partition',3.1,-8.75,-.83,1.05)
for x0,x1,doorx,name in [(-12.2,-2.1,-6.25,'Training'),(-2.1,4.2,1.0,'Tactics'),(4.2,12.2,8.1,'Kitchen')]:
    wall_y(name+' hall wall',1.70,x0,doorx-.85)
    wall_y(name+' hall wall',1.70,doorx+.85,x1)
    doorway(name,1.70,doorx,1.7)
for x0,x1,doorx,name in [(-12.2,-4.4,-7.6,'Lounge'),(3.1,12.2,7.0,'Dining')]:
    wall_y(name+' hall wall',-.86,x0,doorx-1.0,1.0)
    wall_y(name+' hall wall',-.86,doorx+1.0,x1,1.0)
    doorway(name,-.86,doorx,2.0)
for x,width in [(-9.5,3.7),(-4.5,3.2),(1.05,4.1),(6.2,2.8),(10.1,2.7)]:rear_window(x,width)

t=zone_begin('TrainingRoom')
box('Training acoustic carpet',(-7.18,5.23,.20),(9.85,6.65,.065),carpet,.10)
box('Long five player desktop',(-7.12,4.85,1.01),(8.8,1.12,.16),woodlight,.095)
box('Desk modesty panel',(-7.12,4.52,.68),(8.7,.11,.54),navy,.04)
for x in (-11.2,-9.6,-7.95,-6.3,-4.65,-3.0):box('Desk supporting leg',(x,4.85,.57),(.12,.79,.78),navy,.04)
for i in range(5):
    x=-10.6+i*1.73
    # Players behind the monitor face the camera / public corridor.
    box('Gaming monitor',(x,4.81,1.51),(1.10,.13,.67),dark,.06)
    box('Monitor rear mint badge',(x,4.732,1.51),(.40,.022,.055),mint,.012)
    box('Monitor lit display',(x,4.89,1.51),(1.00,.018,.56),screen,.025)
    rod('Monitor stand',(x,4.81,1.08),(x,4.81,1.28),.035,dark)
    box('Mousepad',(x+.18,5.12,1.10),(1.19,.48,.017),navy,.04)
    box('Keyboard',(x-.14,5.17,1.135),(.64,.24,.045),dark,.025)
    for row in range(3):
        for col in range(9):box('Keycap',(x-.40+col*.063,5.095+row*.071,1.165),(.05,.054,.012),mint if row==0 else ivory,.006)
    ellipsoid('Mouse',(x+.58,5.17,1.17),(.065,.1,.035),ivory)
    box('PC case',(x+.62,4.9,.54),(.33,.60,.72),navy,.045)
    for z in (.36,.61):
        torus('PC cooling fan',(x+.62,4.59,z),.095,.017,mint,(math.pi/2,0,0))
    chair(x,5.99,.16,0,navy,True)
    mug(x-.61,4.99,1.10,ivory)
    text('Player station number','0'+str(i+1),(x,4.444,.72),.15,ivory)
# Review screen on rear wall between/over windows, and coach workstation.
box('Coach review display',(-7.15,8.48,2.17),(1.22,.15,1.6),navy,.08)
text('Review title','PRACTICE',(-7.15,8.378,2.58),.15,ivory)
text('Review schedule','10:00\nSCRIM\n\n15:00\nREVIEW',(-7.15,8.375,2.02),.115,mint)
table(-10.7,7.78,1.9,.80)
box('Coach laptop base',(-10.7,7.72,1.025),(.64,.39,.045),navy,.025)
o=box('Coach laptop screen',(-10.7,7.91,1.22),(.64,.035,.37),screen,.025);o.rotation_euler.x=-.12
chair(-10.7,7.0,.16,math.pi,teal)
plant('Training plant',-3.0,7.80,.23,1.2)
floor_label('Training floor label','01 / TRAINING',-7.2,2.36,ivory)
zone_end(t)

t=zone_begin('TacticsRoom')
box('Meeting rug',(1.0,5.0,.21),(4.9,4.1,.05),mint,.15)
table(.95,4.9,2.75,1.35,1.0)
for x in (-.05,1.0,2.05):
    chair(x,6.00,.16,0,teal);chair(x,3.80,.16,math.pi,teal)
for x in (-.05,1.85):mug(x,4.90,1.07)
box('Coach notebook',(.9,4.87,1.09),(.48,.36,.04),navy,.02)
box('Tactics board frame',(1.02,8.26,2.15),(3.45,.15,1.86),wood,.055)
box('Tactics board',(1.02,8.155,2.15),(3.22,.04,1.64),ivory,.025)
text('Tactics board title','TEAM PLAN',(1.02,8.119,2.76),.19,navy)
for x,y,w,h in [(-.02,2.37,.58,.45),(.77,2.28,.55,.30),(1.78,2.4,.61,.47),(1.1,1.78,1.40,.23)]:
    box('Map board region',(x,8.112,y),(w,.013,h),mint,.025)
for x,z,col in [(-.17,2.32,coral),(.1,2.45,coral),(.7,2.26,teal),(1.8,2.4,teal),(1.25,1.8,coral)]:
    ellipsoid('Magnetic tactics token',(x,8.079,z),(.066,.015,.066),col)
rod('Tactics arrow',(.15,8.076,2.1),(.75,8.076,1.94),.016,navy)
rod('Tactics arrow',(.75,8.076,1.94),(1.60,8.076,2.19),.016,navy)
plant('Meeting plant',3.27,7.72,.17,1.25)
floor_label('Tactics floor label','02 / TACTICS',.95,2.35,teal)
zone_end(t)

t=zone_begin('Kitchen')
for ix in range(10):
    for iy in range(9):box('Kitchen floor tile',(4.66+ix*.74,2.08+iy*.74,.204),(.726,.726,.04),tile if (ix+iy)%2 else tile2,.008)
# L-shaped cabinetry, working island and obvious preparation / washing zones.
for i in range(7):
    x=4.83+i*.88
    box('Kitchen rear cabinet',(x,7.76,.66),(.85,1.02,1.0),mint,.05)
    box('Kitchen cabinet panel',(x,7.223,.67),(.73,.028,.83),teal,.025)
    rod('Cupboard pull',(x-.13,7.194,.96),(x+.13,7.194,.96),.018,gold)
box('Kitchen long countertop',(7.48,7.74,1.20),(6.35,1.19,.16),ivory,.055)
for i in range(3):
    box('Side lower cabinet',(11.47,6.26-i*.95,.66),(1.0,.91,1.0),mint,.055)
box('Side countertop',(11.47,5.30,1.20),(1.18,3.0,.16),ivory,.055)
# Sink: dark cavity bounded by porcelain rims rather than a shiny filled slab.
box('Sink recess',(6.35,7.70,1.295),(1.20,.76,.055),steel,.06)
box('Sink bowl',(6.35,7.70,1.329),(.98,.55,.015),dark,.08)
for x in (5.80,6.90):box('Sink lip',(x,7.70,1.35),(.07,.68,.045),ivory,.02)
rod('Tap upright',(6.35,8.02,1.25),(6.35,8.02,1.68),.035,steel)
rod('Tap spout',(6.35,8.02,1.68),(6.35,7.70,1.68),.035,steel)
box('Hob black glass',(9.12,7.69,1.298),(1.36,.88,.04),navy,.03)
for x in (8.81,9.42):
    for y in (7.46,7.92):torus('Hob ring',(x,y,1.327),.15,.014,steel)
cylinder('Soup pot',(9.42,7.92,1.50),.18,.32,coral)
cylinder('Soup pot lid',(9.42,7.92,1.673),.20,.045,ivory)
ellipsoid('Pot knob',(9.42,7.92,1.714),(.05,.05,.035),wooddark)
box('Extractor hood',(9.12,8.13,2.86),(1.53,.90,.30),ivory,.09)
box('Extractor chimney',(9.12,8.44,3.10),(.55,.32,.45),steel,.055)
box('Fridge',(11.36,7.82,1.51),(1.12,1.22,2.72),ivory,.11)
box('Fridge door',(11.36,7.176,1.77),(1.04,.09,1.99),mint,.075)
box('Freezer door',(11.36,7.176,.63),(1.04,.09,.29),mint,.05)
rod('Fridge handle',(10.99,7.106,1.56),(10.99,7.106,2.18),.026,gold)
box('Fridge note',(11.48,7.116,2.08),(.28,.017,.34),ivory,.012)
text('Fridge note text','GG!',(11.48,7.100,2.1),.093,teal)
box('Prep island',(7.35,4.62,.63),(2.45,1.1,.94),wood,.09)
box('Prep worktop',(7.35,4.62,1.16),(2.62,1.26,.15),ivory,.08)
box('Chopping board',(7.05,4.56,1.27),(.80,.48,.055),wooddark,.035)
for dx in (-.2,0,.2):ellipsoid('Fresh tomato',(7.02+dx,4.55,1.36),(.085,.08,.085),fruit)
cone('Fruit bowl',(8.06,4.65,1.31),.14,.25,.16,clay)
for dx,dy in [(-.09,0),(.08,0),(0,.1)]:ellipsoid('Orange',(8.06+dx,4.65+dy,1.45),(.105,.105,.10),orange)
plant('Kitchen herb pot',5.14,7.74,1.29,.5)
floor_label('Kitchen floor label','03 / KITCHEN',8.2,2.33,teal)
zone_end(t)

t=zone_begin('Lounge')
box('Lounge rounded rug',(-8.30,-4.95,.225),(5.95,4.52,.06),rug,.20)
sofa(-8.45,-3.29,3.50,0,coral)
sofa(-11.00,-5.09,2.72,math.pi/2,teal)
table(-8.08,-5.16,2.40,1.10,.65)
box('Coffee table magazine',(-8.40,-5.15,.746),(.48,.34,.035),navy,.02)
mug(-7.48,-5.26,.72)
cone('Snack bowl',(-8.15,-5.0,.79),.10,.19,.12,ivory)
for x,y in [(-8.12,-4.99),(-8.20,-5.04),(-8.08,-5.05)]:ellipsoid('Snack', (x,y,.87),(.063,.046,.029),orange)
# TV stands on a low cabinet, facing the seating rather than a blank partition.
box('TV console',(-7.98,-7.52,.63),(3.20,.63,.83),wood,.08)
for x in (-8.95,-8,-7.05):box('Console inset door',(x,-7.861,.63),(.88,.035,.65),mint,.025)
box('Television',(-7.98,-7.48,1.69),(2.84,.15,1.48),navy,.075)
box('TV screen',(-7.98,-7.386,1.69),(2.65,.023,1.29),screen,.04)
o=text('TV screen title','MATCH DAY',(-7.98,-7.36,1.91),.20,ivory);o.rotation_euler=(math.pi/2,0,math.pi)
for side in (-1,1):box('TV feet',(-7.98+side*.89,-7.48,1.03),(.28,.34,.05),navy,.02)
plant('Lounge tall plant',-11.52,-2.06,.17,1.7)
floor_label('Lounge floor label','04 / LOUNGE',-8.32,-1.55,teal)
zone_end(t)

t=zone_begin('Lobby')
box('Lobby welcome rug',(-.73,-6.60,.22),(4.65,2.6,.055),teal,.17)
floor_label('Welcome rug text','WELCOME HOME',-.73,-6.57,ivory)
box('Reception oak desk',(-1.13,-2.57,.81),(3.70,1.05,1.25),wood,.15)
box('Reception green front',(-1.13,-3.114,.81),(3.50,.065,1.0),teal,.095)
box('Reception countertop',(-1.13,-2.57,1.47),(3.91,1.21,.15),ivory,.085)
text('Club reception title','ROOKIE CLUB',(-1.13,-3.162,.90),.26,ivory)
text('Club reception small','PLAY. LEARN. BELONG.',(-1.13,-3.164,.59),.098,ivory)
box('Reception tablet',(-2.23,-2.69,1.74),(.51,.075,.34),navy,.04)
plant('Reception greenery',.16,-2.52,1.55,.43)
# Trophy cabinet with all shelves visible from the entry.
for x in (1.13,2.73):box('Honours cabinet side',(x,-4.19,1.35),(.10,.65,2.40),wood,.035)
box('Honours cabinet top',(1.93,-4.19,2.55),(1.70,.65,.12),wood,.04)
box('Honours cabinet dark backing',(1.93,-3.90,1.35),(1.45,.025,2.17),navy,.02)
for z in (.30,1.03,1.75,2.46):box('Trophy cabinet shelf',(1.93,-4.19,z),(1.46,.69,.07),woodlight,.025)
for i,z in enumerate((.40,1.13,1.85)):
    for dx in (-.37,.37):
        x=1.93+dx;cylinder('Trophy foot',(x,-4.07,z+.035),.12,.07,gold)
        cone('Trophy stem',(x,-4.07,z+.16),.06,.04,.21,gold)
        cone('Trophy cup',(x,-4.07,z+.37),.055,.18,.23,gold)
        for side in (-1,1):torus('Trophy handle',(x+side*.15,-4.07,z+.39),.073,.018,gold,(math.pi/2,0,0))
text('Honours label','OUR STORY',(1.93,-4.53,2.56),.13,navy)
plant('Lobby entrance tree',-3.46,-7.49,.16,1.55)
for x in (-2.65,1.2):box('Open entrance timber post',(x,-8.74,1.56),(.22,.35,2.83),wood,.07)
box('Entrance overhead sign',(-.72,-8.74,3.01),(4.11,.35,.58),navy,.10)
text('Entry sign text','ROOKIE ESPORTS',(-.72,-8.95,3.03),.285,ivory)
box('Entry outdoor step',(-.72,-9.30,.14),(4.65,1.05,.20),stone,.08)
for x in (-3.70,2.17):plant('Entry planter',x,-9.32,.24,.9)
zone_end(t)

t=zone_begin('DiningRoom')
box('Dining rug',(7.69,-4.44,.21),(7.73,5.60,.045),ivory,.17)
table(7.34,-4.52,4.78,1.53,1.02)
for x in (5.48,6.72,7.96,9.20):
    chair(x,-3.29,.16,0,teal);chair(x,-5.74,.16,math.pi,coral)
for x in (5.48,6.72,7.96,9.20):
    for y in (-4.98,-4.07):
        cylinder('Dinner plate',(x,y,1.111),.22,.029,ivory,32,.008)
        torus('Plate rim',(x,y,1.13),.185,.012,woodlight)
        box('Linen napkin',(x+.32,y,1.12),(.16,.29,.018),mint,.017)
        rod('Dining chopstick',(x+.28,y-.11,1.145),(x+.28,y+.11,1.145),.008,wooddark)
        rod('Dining chopstick',(x+.32,y-.11,1.145),(x+.32,y+.11,1.145),.008,wooddark)
        mug(x-.32,y,1.10)
plant('Table flower',7.32,-4.52,1.10,.42)
# Sideboard has a coffee machine, water dispenser and cereal jars.
box('Dining sideboard',(7.91,-7.52,.72),(5.70,.78,1.10),mint,.065)
box('Sideboard top',(7.91,-7.52,1.31),(5.89,.95,.12),woodlight,.05)
box('Coffee machine',(6.13,-7.49,1.71),(.72,.54,.68),navy,.08)
box('Coffee machine silver panel',(6.13,-7.795,1.71),(.59,.06,.47),steel,.04)
mug(6.13,-7.79,1.41)
cylinder('Coffee grinder hopper',(6.13,-7.49,2.12),.17,.23,clay)
for x in (7.4,7.85,8.3):
    cylinder('Breakfast jar',(x,-7.52,1.56),.135,.39,ivory,32)
    cylinder('Jar wood lid',(x,-7.52,1.77),.145,.065,wood,32)
box('Water dispenser',(9.68,-7.51,1.76),(.61,.62,.76),ivory,.09)
ellipsoid('Water bottle',(9.68,-7.51,2.29),(.22,.22,.33),blue)
plant('Dining corner plant',11.27,-6.75,.16,1.35)
floor_label('Dining floor label','05 / DINING',7.8,-1.62,teal)
zone_end(t)

# Append our original chicken as a reusable hierarchy. No game character assets.
with bpy.data.libraries.load(str(ROOT/'assets'/'chicken_source.blend'),link=False) as (src,dst):
    dst.objects=src.objects
loaded=[o for o in dst.objects if o]
proto=next(o for o in loaded if o.name=='Chicken')
members=[proto]+list(proto.children_recursive)
def in_kit(o):
    while o:
        if o.name=='PlayerKit':return True
        o=o.parent
    return False
for o in members:
    for c in list(o.users_collection):c.objects.unlink(o)
def add_chicken(name,x,y,z,scale=.59,angle=0,jersey=False):
    c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c)
    mapping={o:o.copy() for o in members}
    for old,new in mapping.items():
        c.objects.link(new);new.name=name+'_'+old.name
        if old.parent in mapping:new.parent=mapping[old.parent];new.matrix_parent_inverse=old.matrix_parent_inverse.copy()
    root=mapping[proto];root.location=(x,y,z);root.scale=(scale,)*3;root.rotation_euler.z=angle
    for old,new in mapping.items():
        if in_kit(old):
            new.hide_render=not jersey;new.hide_viewport=not jersey
        if old.name=='Cream belly bib':new.hide_render=jersey;new.hide_viewport=jersey
    return root
for i in range(5):add_chicken('Player%02d'%(i+1),-10.6+i*1.73,6.0,.21,.57,0,True)
add_chicken('Receptionist',-1.1,-1.66,.17,.62,0,True)
add_chicken('Chef',8.0,6.32,.17,.63,-.2,False)
add_chicken('Lounge teammate',-5.67,-5.58,.17,.61,.60,True)
add_chicken('Dining teammate',10.54,-2.70,.17,.61,-.7,False)
# Delete unused loaded studio resources, not originals on disk.
for o in loaded:
    if o.name in bpy.data.objects:bpy.data.objects.remove(o,do_unlink=True)

# Building views and render-only studio lights.
scene=bpy.context.scene
world=bpy.data.worlds.new('Club soft daylight');scene.world=world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.68,.76,.70,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.5
backdrop=box('Studio backdrop',(0,0,-.47),(200,200,.05),material('Studio pale sage','#B6C5B9'),0)
def area(name,loc,energy,size,color,target):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);scene.collection.objects.link(o);o.location=loc
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
area('Soft key',(-10,-12,23),4200,16,(1,.87,.68),(0,0,0))
area('Sky fill',(12,4,18),3000,13,(.75,.89,1),(0,0,1))
area('Window fill',(-8,9,9),1000,9,(1,.95,.78),(-6,3,0))
camdata=bpy.data.cameras.new('Club overview camera');cam=bpy.data.objects.new('Club overview camera',camdata);scene.collection.objects.link(cam)
cam.location=(24,-35,33);target=Vector((0,.2,.5));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
camdata.type='ORTHO';camdata.ortho_scale=35.5;scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=40;scene.cycles.use_denoising=True;scene.cycles.adaptive_threshold=.045
scene.render.resolution_x=1800;scene.render.resolution_y=1450;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'assets'/'chicken_club.blend'))
# Hidden accessory variants remain in the source file, but not the runtime GLB.
visible=[o for o in bpy.data.objects if o.type in {'MESH','FONT','CURVE'} and not o.hide_render and o.name!='Studio backdrop']
bpy.ops.object.select_all(action='DESELECT')
for o in visible:
    if o.type in {'FONT','CURVE'}:o.select_set(True)
bpy.context.view_layer.objects.active=next(iter(bpy.context.selected_objects));bpy.ops.object.convert(target='MESH')
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    if o.type=='MESH' and not o.hide_render and o.name!='Studio backdrop':o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets'/'chicken_club.glb'),export_format='GLB',use_selection=True,
    export_apply=True,export_yup=True,export_lights=False,export_cameras=False)
scene.render.filepath=str(ROOT/'renders'/'club_overview.png');bpy.ops.render.render(write_still=True)
cam.location=(-3.1,-1.9,7.0);target=Vector((-7.1,5.2,1.0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
camdata.ortho_scale=12.7;scene.render.resolution_x=1600;scene.render.resolution_y=1100
scene.render.filepath=str(ROOT/'renders'/'club_training.png');bpy.ops.render.render(write_still=True)
print('CLUB_BUILD_COMPLETE',flush=True)
