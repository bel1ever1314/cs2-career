extends CanvasLayer
## Presentation-only dialogue window. ClubLife owns choices and resumption.
var life
var panel: PanelContainer
var heading: Label
var activity: Label
var text: Label
var relation: Label
func setup(manager) -> void:
	life=manager;layer=8
	var root:=Control.new();root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);root.mouse_filter=Control.MOUSE_FILTER_IGNORE;add_child(root)
	panel=PanelContainer.new();root.add_child(panel);panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_left=60;panel.offset_right=-60;panel.offset_top=-355;panel.offset_bottom=-30
	var style:=StyleBoxFlat.new();style.bg_color=Color(.96,.92,.82,.99)
	style.corner_radius_top_left=18;style.corner_radius_top_right=18;style.corner_radius_bottom_left=18;style.corner_radius_bottom_right=18
	style.content_margin_left=28;style.content_margin_right=28;style.content_margin_top=22;style.content_margin_bottom=22
	panel.add_theme_stylebox_override("panel",style)
	var col:=VBoxContainer.new();col.add_theme_constant_override("separation",12);panel.add_child(col)
	heading=label(col,27);activity=label(col,15);text=label(col,21);text.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;text.custom_minimum_size.y=75
	relation=label(col,14)
	var row:=HBoxContainer.new();row.add_theme_constant_override("separation",12);col.add_child(row)
	var topics: Array=[ ["busy","1  你在忙什么？"],["training","2  聊聊训练"],["encourage","3  一起加油"],["leave","4  回头见"] ]
	for item in topics:
		var button:=Button.new();button.text=item[1];button.custom_minimum_size=Vector2(195,44);button.focus_mode=Control.FOCUS_NONE
		button.add_theme_font_size_override("font_size",17);button.pressed.connect(life.choose.bind(item[0]));row.add_child(button)
	life.dialogue_changed.connect(refresh);life.dialogue_closed.connect(func():panel.visible=false)
	panel.visible=false
func label(parent: Node,size: int) -> Label:
	var result:=Label.new();result.add_theme_font_size_override("font_size",size);result.add_theme_color_override("font_color",Color("294844"));parent.add_child(result);return result
func refresh() -> void:
	if life.speaker==null:panel.visible=false;return
	var npc=life.speaker
	heading.text=str(npc.definition["name"])+"  /  "+str(npc.definition["role"])
	activity.text=life.topic_selected+"  ·  对方会等你聊完再继续"
	text.text=life.line
	relation.text="熟悉度 %d / 5（仅本次小样）   ·   点击选项或按 1—4，Esc 结束交谈" % npc.bond
	panel.visible=true
