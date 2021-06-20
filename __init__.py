bl_info = {
    "name" : "Blender-Game-of-Life",
    "author" : "Rivin",
    "description" : "Conway’s Game of Life for Blender",
    "blender" : (2, 92, 0),
    "version" : (0, 0, 1),
    "location" : "View3D > UI > Game",
    "warning" : "",
    "category" : "3D View"
}

from . import blender_game_of_life

def register():
    blender_game_of_life.register()

def unregister():
    blender_game_of_life.unregister()
