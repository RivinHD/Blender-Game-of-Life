import bpy
from bpy.types import Panel, Operator, AddonPreferences
from bpy.props import IntVectorProperty, EnumProperty, IntProperty, BoolProperty
from bpy.app.handlers import persistent
import bl_math
from numpy import zeros
from operator import itemgetter
from typing import Tuple

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

def apply_rules(objects: list, collection: bpy.types.Collection) -> Tuple[str]:
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
        count_xy = count_xz = count_yz = count_diag_xyz = count_diag_negxyz = 0
        for l in (-1, 1):
            x = playground[i + l][j][k]
            y = playground[i][j + l][k]
            z = playground[i][j][k + l]
            xy = playground[i + l][j + l][k]
            x_y = playground[i + l][j - l][k]
            xz = playground[i + l][j][k + l]
            x_z = playground[i + l][j][k - l]
            yz = playground[i][j + l][k + l]
            y_z = playground[i][j + l][k - l]
            xyz = playground[i + l][j + l][k + l]
            x_yz = playground[i + l][j - l][k + l]
            xy_z = playground[i + l][j + l][k - l]
            x_y_z = playground[i + l][j - l][k - l]

            count_xy += sum((x, y, xy, x_y))
            count_xz += sum((x, z, xz, x_z))
            count_yz += sum((y, z, yz, y_z))
            count_diag_xyz += sum((x, xy, xyz, xy_z))
            count_diag_negxyz += sum((x, x_y, x_yz, x_y_z))

        counts = (count_xy, count_xz, count_yz, count_diag_xyz, count_diag_negxyz)
        alive = False # ignore rule 2, 4 only check for alive cells
        # Rule 1                                                    # Rule 3
        alive = (not(is_alive) and any(x == 3 for x in counts)) or is_alive and any(x == 2 or x == 3 for x in counts)

        location = tuple(map(int, (i + x_min, j + y_min, k + z_min)))
        if alive:
            name = objects_by_location.get(str(location), None)
            if name is None:
                new_obj = create_cell(location)
                new_obj.hide_set(True)
                name = new_obj.name
            alives.append(name) # get existing cell or creat new cell
    return tuple(alives)

@persistent
def run_game(scene):
    BGOL = bpy.context.preferences.addons[__package__].preferences
    current_frame = scene.frame_current
    start_frame = BGOL.start_frame
    if BGOL.activ and current_frame >= start_frame and current_frame <= BGOL.end_frame:
        collection = get_game_collection()
        if BGOL.processing_mode == 'pre':
            global last_shown_objects_name
            last_objects = set(last_shown_objects_name)
            last_shown_objects_name = pre_process_data[current_frame - start_frame]
            show_objects = set(last_shown_objects_name)
            for name in last_objects.difference(show_objects):
                collection.objects[name].hide_set(True)
            for name in show_objects.difference(last_objects):
                collection.objects[name].hide_set(False)
        else:
            frame_diffrence = current_frame - BGOL.last_frame
            if frame_diffrence < 0:
                frame_diffrence = current_frame - start_frame
                bpy.ops.bgol.load_setup()
            for i in range(frame_diffrence):
                alive_objects_name = apply_rules(collection.objects, collection)
                dead_objects_name = set(obj.name for obj in collection.objects).difference(alive_objects_name)
                data_objects = bpy.data.objects
                for name in dead_objects_name:
                    data_objects.remove(data_objects[name])
            BGOL.last_frame = current_frame

classes = []
last_shown_objects_name = []
pre_process_data = []
base_case = []

class BGOL_PT_game_of_life(Panel):
    bl_idname = "BGOL_PT_game_of_life"
    bl_label = "Game of Life"
    bl_category = "Game"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        BGOL = context.preferences.addons[__package__].preferences
        layout.operator(BGOL_OT_create_new_cell.bl_idname)
        col = layout.column(align= True)
        col.prop(BGOL, 'grid_location')
        layout.operator(BGOL_OT_cleanup_cells.bl_idname)
        layout.operator(BGOL_OT_cleanup_scene.bl_idname)
        row = layout.row(align= True)
        row.prop(BGOL, 'start_frame', text= "Start")
        row.prop(BGOL, 'end_frame', text= "End")
        row = layout.row(align= True)
        row.operator(BGOL_OT_load_setup.bl_idname)
        row.operator(BGOL_OT_save_setup.bl_idname)
        col = layout.column(align= True)
        row = col.row(align= True)
        row.prop(BGOL, 'processing_mode', expand= True)
        if BGOL.processing_mode == 'pre':
            if BGOL.progress == -1:
                col.operator(BGOL_OT_process.bl_idname)
            else:
                row2 = col.row(align= True)
                row2.active = False
                row2.prop(BGOL, 'progress', slider= True)
        row = layout.row()
        row.scale_y = 1.5
        row.prop(BGOL, 'activ', toggle= 1)
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
        pre_process_data.clear()
        bpy.ops.bgol.save_setup()
        collection = get_game_collection()
        pre_process_data.append(tuple([obj.name for obj in collection.objects]))
        self.frame = 0
        self.length = BGOL.end_frame - BGOL.start_frame
        self.timer = context.window_manager.event_timer_add(0.001, window= context.window)
        BGOL.progress = 100 * self.frame / self.length
        context.window_manager.modal_handler_add(self)
        bpy.context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        BGOL = context.preferences.addons[__package__].preferences
        collection = get_game_collection()
        objects = [collection.objects[name] for name in pre_process_data[-1]]
        pre_process_data.append(apply_rules(objects, collection))
        self.frame += 1
        BGOL.progress = 100 * self.frame / self.length
        if self.frame == self.length:
            return self.execute(context)
        bpy.context.area.tag_redraw()
        return {'PASS_THROUGH'}

    def execute(self, context: bpy.types.Context):
        BGOL = context.preferences.addons[__package__].preferences
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
        base_case = [tuple(int(x) for x in obj.location) for obj in collection.objects]
        return {'FINISHED'}
classes.append(BGOL_OT_save_setup)

class BGOL_OT_load_setup(Operator):
    bl_idname = "bgol.load_setup"
    bl_label = "Load Setup"
    bl_description = "Load the saved setup"

    def execute(self, context: bpy.types.Context):
        collection = get_game_collection()
        for obj in collection.objects:
            bpy.data.objects.remove(obj)
        global base_case
        for location in base_case:
            create_cell(location)
        while bpy.data.orphans_purge() != 0:
            continue
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
    processing_mode : EnumProperty(items= [
        ("pre", "Pre-Process", "Process the game before launching for better preformance by hiding dead/showing living cells"),
        ("runtime", "Runtime", "Process the game each time with the frame change (backwards slow)")
        ], 
        name= "Processing Mode"
    )
    def min_progress(self):
        return self.start_frame
    progress : IntProperty(name= "Progress", default= -1 ,min= -1, max= 100, soft_min= 0, subtype= 'PERCENTAGE')
    start_frame : IntProperty(name= "Startframe", default= 1)
    end_frame : IntProperty(name= 'Endframe', default= 250)
    last_frame : IntProperty()
    def get_activ(self):
        return self.get('active', False)
    def set_active(self, value):
        self.last_frame = bpy.context.scene.frame_current
        self['active'] = value
        if value and self.processing_mode == 'runtime':
            bpy.ops.bgol.load_setup()
    activ : BoolProperty(default= False, name= "Activ", description= "Activate the Game to change by the frames and set the base case on activation", get= get_activ, set= set_active)
classes.append(BGOL_preferences)

def register():
    bpy.app.handlers.frame_change_pre.append(run_game)
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    bpy.app.handlers.frame_change_pre.remove(run_game)
    for cls in classes:
        bpy.utils.unregister_class(cls)
