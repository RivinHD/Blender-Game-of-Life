import bpy
from bpy.types import Panel, Operator, AddonPreferences
from bpy.props import IntVectorProperty, EnumProperty, IntProperty, BoolProperty
from bpy.app.handlers import persistent
import bl_math
from numpy import zeros
from operator import itemgetter
from typing import Tuple, List

def get_game_collection() -> bpy.types.Collection:
    collection = bpy.data.collections.get("Game of Life", None)
    if collection is None:
        collection = bpy.data.collections.new("Game of Life")
        bpy.context.scene.collection.children.link(collection)
    return collection

def link_to_collection(obj: bpy.types.Object) -> None:
    for coll in obj.users_collection:
        coll.objects.unlink(obj)
    collection = get_game_collection()
    collection.objects.link(obj)

def get_cell_mesh(overwrite: bool = False) -> bpy.types.Mesh:
    mesh = bpy.data.meshes.get("Game of Life", None)
    if mesh is None or overwrite:
        if mesh is None:
            mesh = bpy.data.meshes.new("Game of Life")
        mesh.clear_geometry()
        mesh.from_pydata( # create Cube
            vertices = [(0.5, 0.5, 0.5), (0.5, 0.5, -0.5), (0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, -0.5, -0.5)],
            edges = [(5, 7), (1, 5), (0, 1), (7, 6), (2, 3), (4, 5), (2, 6), (0, 2), (7, 3), (6, 4), (4, 0), (3, 1)],
            faces = [(0, 4, 6, 2), (3, 2, 6, 7), (7, 6, 4, 5), (5, 1, 3, 7), (1, 0, 2, 3), (5, 4, 0, 1)]
        )
    return mesh

def create_cell(position : Tuple[int, int, int]) -> bpy.types.Object:
    obj = bpy.data.objects.new(f"Cell-{position}", get_cell_mesh())
    obj.location = position
    obj.lock_rotation = obj.lock_scale = (True, True, True)
    link_to_collection(obj)
    return obj

def correct_object(obj: bpy.types.Object, mesh: bpy.types.Mesh) -> None:
    obj.name = f"Cell-{tuple(int(x) for x in obj.location)}"
    obj.parent = None
    obj.rotation_euler = (0, 0, 0)
    obj.scale = (1, 1, 1)
    obj.data = mesh

def apply_rules(objects: list, collection: bpy.types.Collection, low_value: int, high_value: int ,use_3d : bool, use_diagnol : bool, combine_planes: bool, hide: bool = False) -> List[str]:
    if len(objects) == 0:
        return ()
    objects_by_location = {str(tuple(map(int, obj.location))): obj.name for obj in collection.objects}
    all_object_locations = [tuple(map(int, obj.location)) for obj in objects]
    mins = [int(min(all_object_locations, key= itemgetter(i))[i] - 2) for i in range(3)]
    maxs = [int(max(all_object_locations, key= itemgetter(i))[i] + 3) for i in range(3)]
    playground = zeros(tuple(i - j for i, j in zip(maxs, mins)), dtype= bool)
    possible_locations = []

    x_min, y_min, z_min = mins
    for x, y, z in all_object_locations: # set alive celles
        playground[x - x_min][y - y_min][z - z_min] = True
        for xi in (-1, 0, 1):
            for yi in (-1, 0, 1):
                for zi in (-1, 0, 1):
                    possible_locations.append((x + xi - x_min, y + yi - y_min, z + zi - z_min))
    possible_locations = set(possible_locations)

    alives = []
    for i, j, k in possible_locations:
        is_alive = playground[i][j][k]
        count_xy = count_xz = count_yz = count_diag_xyz = count_diag_negxyz = total_count = 0
        for l in (-1, 1):
            x = playground[i + l][j][k]
            y = playground[i][j + l][k]
            xy = playground[i + l][j + l][k]
            x_y = playground[i + l][j - l][k]

            count_xy += sum((x, y, xy, x_y))
            total_count += sum((x, y, xy, x_y))

            if use_3d:
                z = playground[i][j][k + l]
                xz = playground[i + l][j][k + l]
                x_z = playground[i + l][j][k - l]
                yz = playground[i][j + l][k + l]
                y_z = playground[i][j + l][k - l]

                count_xz += sum((x, z, xz, x_z))
                count_yz += sum((y, z, yz, y_z))
                total_count += sum((z, xz, x_z, yz, y_z))
                
                if use_diagnol:
                    xyz = playground[i + l][j + l][k + l]
                    x_yz = playground[i + l][j - l][k + l]
                    xy_z = playground[i + l][j + l][k - l]
                    x_y_z = playground[i + l][j - l][k - l]

                    count_diag_xyz += sum((z, xy, xyz, xy_z))
                    count_diag_negxyz += sum((z, x_y, x_yz, x_y_z))
                    total_count += sum((xyz, x_yz, xy_z, x_y_z))
        if combine_planes:
            counts = [total_count]
        else:
            if use_3d:
                if use_diagnol:
                    counts = [count_xy, count_xz, count_yz, count_diag_xyz, count_diag_negxyz]
                else:
                    counts = [count_xy, count_xz, count_yz]
            else:
                counts = [count_xy]

        if is_alive:
            #       Rule 3
            alive = any(x == low_value or x == high_value for x in counts)
            #           Rule 2                         Rule 4                                   
            alive = not(all(x < low_value for x in counts) or any(x > high_value for x in counts))
        else:
            #       Rule 1
            alive = any(x == high_value for x in counts)

        location = tuple(map(int, (i + x_min, j + y_min, k + z_min)))
        if alive:
            name = objects_by_location.get(str(location), None)
            if name is None:
                new_obj = create_cell(location)
                new_obj.hide_viewport = hide
                new_obj.hide_render = hide
                name = new_obj.name
            alives.append(name) # get existing cell or creat new cell
    return alives

classes = []
base_case = []
last_process_data = []

class BGOL_PT_game_of_life(Panel):
    bl_idname = "BGOL_PT_game_of_life"
    bl_label = "Game of Life"
    bl_category = "Game"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        BGOL = context.preferences.addons[__package__].preferences
        main_col = layout.column()
        main_col.operator(BGOL_OT_create_new_cell.bl_idname)
        col = main_col.column(align= True)
        col.prop(BGOL, 'grid_location')
        main_col.operator(BGOL_OT_cleanup_cells.bl_idname)
        main_col.operator(BGOL_OT_cleanup_scene.bl_idname)
        row = main_col.row(align= True)
        row.prop(BGOL, 'start_frame', text= "Start")
        row.prop(BGOL, 'end_frame', text= "End")
        row = main_col.row(align= True)
        row.operator(BGOL_OT_load_setup.bl_idname)
        row.operator(BGOL_OT_save_setup.bl_idname)
        col = main_col.column(align= True)
        row2 = col.row(align= True)
        if BGOL.progress == -1:
            row2.operator(BGOL_OT_process.bl_idname)
            row2.prop(BGOL, 'use_3d', text= "", icon= "OUTLINER_DATA_EMPTY")
            col2 = row2.column(align= True)
            col2.active = BGOL.use_3d
            col2.prop(BGOL, 'use_diagonal', text= "", icon= "AXIS_SIDE")
        else:
            row2.active = False
            row2.prop(BGOL, 'progress', slider= True)
classes.append(BGOL_PT_game_of_life)

class BGOL_OT_cleanup_scene(Operator):
    bl_idname = "bgol.cleanup_scene"
    bl_label = "Cleanup Scene"
    bl_description = "Cleanup the selected Scene"

    def execute(self, context: bpy.types.Context):
        scene_name = context.scene.name 
        new_scene = bpy.data.scenes.new('temp')
        bpy.data.scenes.remove(context.scene)
        new_scene.name = scene_name
        while bpy.data.orphans_purge() != 0:
            continue
        return {'FINISHED'}
classes.append(BGOL_OT_cleanup_scene)

class BGOL_OT_create_new_cell(Operator):
    bl_idname = "bgol.create_new_cell"
    bl_label = "Create Cell"
    bl_description = "Create a new cell"

    def execute(self, context: bpy.types.Context):
        new_obj = create_cell((0, 0, 0))
        for obj in context.selected_objects:
            obj.select_set(False)
        new_obj.select_set(True)
        context.view_layer.objects.active = new_obj
        return {'FINISHED'}
classes.append(BGOL_OT_create_new_cell)

class BGOL_OT_append_selection(Operator):
    bl_idname = "bgol.append_selection"
    bl_label = "Append Cell"
    bl_description = "Append the Selection as a Cell"

    def execute(self, context: bpy.types.Context):
        mesh = get_cell_mesh()
        for obj in context.selected_objects:
            obj.location = [int(x) for x in obj.location]
            correct_object(obj, mesh)
            link_to_collection(obj)
        return {'FINISHED'}
classes.append(BGOL_OT_append_selection)

class BGOL_OT_cleanup_cells(Operator):
    bl_idname = "bgol.cleanup_cells"
    bl_label = "Cleanup Cells"
    bl_description = "Removing wrong attributes, duplicates and set the rigth mesh"

    def execute(self, context: bpy.types.Context):
        # cleanup mesh
        mesh = get_cell_mesh(True)
        # cleanup objects
        collection = get_game_collection()
        for obj in collection.objects:
            obj.location = [int(x) for x in obj.location]
        sorted_objects = sorted(collection.objects, key= lambda x: tuple(x.location))
        if len(sorted_objects):
            last_obj = sorted_objects[0]
            correct_object(last_obj, mesh)
            for obj in sorted_objects[1:]:
                if last_obj.location == obj.location:
                    bpy.data.objects.remove(obj)
                    continue
                correct_object(obj, mesh)
                last_obj = obj
        while bpy.data.orphans_purge() != 0:
            continue
        return {'FINISHED'}
classes.append(BGOL_OT_cleanup_cells)

class BGOL_OT_process(Operator):
    bl_idname = "bgol.process"
    bl_label = "Process"
    bl_description = "cleanup, save and process th game"
    
    frame : IntProperty(options= {'HIDDEN'})
    length : IntProperty(options= {'HIDDEN'})

    @classmethod
    def poll(cls, context: bpy.types.Context):
        BGOL = context.preferences.addons[__package__].preferences
        return BGOL.processing_mode == 'pre'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        BGOL = context.preferences.addons[__package__].preferences
        global last_process_data
        bpy.ops.bgol.save_setup()
        collection = get_game_collection()
        self.frame = 0
        last_process_data.clear()
        for obj in collection.objects:
            hide_render = obj.hide_render
            hide_viewport = obj.hide_viewport
            obj.hide_render = False
            obj.hide_viewport = False
            obj.keyframe_insert('hide_render', frame= 1, group= 'Game of Life')
            obj.keyframe_insert('hide_viewport', frame= 1, group= 'Game of Life')
            obj.hide_render = True
            obj.hide_viewport = True
            obj.keyframe_insert('hide_render', frame= 2, group= 'Game of Life')
            obj.keyframe_insert('hide_viewport', frame= 2, group= 'Game of Life')
            obj.hide_render = hide_render
            obj.hide_viewport = hide_viewport
            last_process_data.append(obj.name)
        self.length = BGOL.end_frame - BGOL.start_frame
        self.timer = context.window_manager.event_timer_add(0.001, window= context.window)
        BGOL.progress = 100 * self.frame / self.length
        context.window_manager.modal_handler_add(self)
        bpy.context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        BGOL = context.preferences.addons[__package__].preferences
        global last_process_data
        collection = get_game_collection()
        objects = [collection.objects[name] for name in last_process_data]
        last_process_data = apply_rules(objects, collection, BGOL.value_low, BGOL.value_high, BGOL.use_3d, BGOL.use_diagonal, BGOL.combine_planes, True)
        real_frame = self.frame + 1
        for obj in [collection.objects[name] for name in last_process_data]:
            hide_render = obj.hide_render
            hide_viewport = obj.hide_viewport
            obj.hide_render = False
            obj.hide_viewport = False
            obj.keyframe_insert('hide_render', frame= real_frame, group= 'Game of Life')
            obj.keyframe_insert('hide_viewport', frame= real_frame, group= 'Game of Life')
            obj.hide_render = True
            obj.hide_viewport = True
            obj.keyframe_insert('hide_render', frame= real_frame + 1, group= 'Game of Life')
            obj.keyframe_insert('hide_viewport', frame= real_frame + 1, group= 'Game of Life')
            obj.hide_render = hide_render
            obj.hide_viewport = hide_viewport
        self.frame += 1
        BGOL.progress = 100 * self.frame / self.length
        if self.frame == self.length:
            return self.execute(context)
        bpy.context.area.tag_redraw()
        return {'PASS_THROUGH'}

    def execute(self, context: bpy.types.Context):
        BGOL = context.preferences.addons[__package__].preferences
        collection = get_game_collection()
        for obj in collection.objects:
            obj.keyframe_insert('hide_render', frame= 1, group= 'Game of Life')
            obj.keyframe_insert('hide_viewport', frame= 1, group= 'Game of Life')
        BGOL.progress = -1
        context.window_manager.event_timer_remove(self.timer)
        bpy.context.area.tag_redraw()
        return {'FINISHED'}
classes.append(BGOL_OT_process)

class BGOL_OT_save_setup(Operator):
    bl_idname = "bgol.save_setup"
    bl_label = "Save Setup"
    bl_description = "Save the a clean current setup as base case (only loction of objects in 'Game of Life' collection)"

    def execute(self, context: bpy.types.Context):
        bpy.ops.bgol.cleanup_cells()
        BGOL = context.preferences.addons[__package__].preferences
        collection = get_game_collection()
        global base_case
        base_case = [tuple(int(x) for x in obj.location) for obj in collection.objects if not obj.hide_get()]
        return {'FINISHED'}
classes.append(BGOL_OT_save_setup)

class BGOL_OT_load_setup(Operator):
    bl_idname = "bgol.load_setup"
    bl_label = "Load Setup"
    bl_description = "Load the saved setup"

    def execute(self, context: bpy.types.Context):
        global base_case
        for location in base_case:
            create_cell(location)
        return {'FINISHED'}
classes.append(BGOL_OT_load_setup)

class BGOL_preferences(AddonPreferences):
    bl_idname = __package__

    def get_grid_location(self):
        obj = bpy.context.object
        if obj:
            return tuple(obj.location)
        return (0, 0, 0)
    def set_grid_location(self, value):
        obj = bpy.context.object
        obj.location = [int(i) for i in value]
    grid_location : IntVectorProperty(name= "Gridlocation", description= "positon selected object in an fixed grid", get= get_grid_location, set= set_grid_location)
    progress : IntProperty(name= "Progress", default= -1 ,min= -1, max= 100, soft_min= 0, subtype= 'PERCENTAGE')
    start_frame : IntProperty(name= "Startframe", default= 1)
    end_frame : IntProperty(name= 'Endframe', default= 250)
    use_3d : BoolProperty(default= True, name= "Use 3D", description= "Turn off to only use 2 dimension (normal Conway's Game of Life)")
    use_diagonal : BoolProperty(default= True, name= "Use Diagonal", description= "Also use diagnal plans to calculate the game")
    combine_planes : BoolProperty(default= False, name= "Combine Planes")
    value_low : IntProperty(name= "low value", default= 2)
    value_high : IntProperty(name= "high value", default= 3)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'combine_planes')
        layout.prop(self, 'value_low')
        layout.prop(self, 'value_high')
classes.append(BGOL_preferences)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
